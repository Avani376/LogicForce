"""Backend hardening middleware (OWASP API Top 10: API4 resource consumption, API8 security misconfiguration).

- Per-client sliding-window rate limits (429 + Retry-After), stricter on /assistant/*.
- Request body-size cap (413) before parsing.
- A global exception handler lives in main.py; this module provides the middleware.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip().lower()
    if raw in ("off", "0", "disabled"):
        return 0
    return max(0, int(raw))


DEFAULT_RATE_LIMIT_PER_MINUTE = _env_int("LOGICFORGE_RATE_LIMIT", 240)
ASSISTANT_RATE_LIMIT_PER_MINUTE = _env_int("LOGICFORGE_ASSISTANT_RATE_LIMIT", 30)
MAX_BODY_BYTES = _env_int("LOGICFORGE_MAX_BODY_BYTES", 1_000_000)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before parsing (413)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        length_header = request.headers.get("content-length")
        if length_header is not None and length_header.isdigit() and int(length_header) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": f"request body exceeds the {MAX_BODY_BYTES}-byte limit",
                    }
                },
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client sliding-window rate limiter (in-memory, per process).

    /assistant/* endpoints get a stricter budget because they trigger upstream
    work. Limits are per process — horizontal deployments rate-limit per replica,
    which is the intended conservative default (OWASP API4). Set
    LOGICFORGE_RATE_LIMIT=off to disable (the test suite does this in conftest).
    """

    def __init__(self, app: object, limit: int | None = None, assistant_limit: int | None = None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        disabled = DEFAULT_RATE_LIMIT_PER_MINUTE <= 0  # env kill-switch (suite conftest)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = time.monotonic()
        self._limit = (
            0 if disabled and limit is None else (limit if limit is not None else DEFAULT_RATE_LIMIT_PER_MINUTE)
        )
        self._assistant_limit = (
            0
            if disabled and assistant_limit is None
            else (assistant_limit if assistant_limit is not None else ASSISTANT_RATE_LIMIT_PER_MINUTE)
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client is not None else "unknown"
        is_assistant = request.url.path.startswith("/api/assistant")
        limit = self._assistant_limit if is_assistant else self._limit
        if limit <= 0:
            return await call_next(request)
        now = time.monotonic()
        window_start = now - 60.0
        # Separate buckets: the assistant budget is not consumed by general traffic.
        bucket = f"{client_ip}|{'a' if is_assistant else 'g'}"

        hits = self._hits[bucket]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(60 - (now - hits[0])))
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "detail": {
                        "code": "RATE_LIMITED",
                        "message": f"too many requests from this client — limit is {limit}/min",
                    }
                },
            )
        hits.append(now)

        # Periodic sweep so idle clients do not pin memory.
        if now - self._last_sweep > 300.0:
            for key in [k for k, dq in self._hits.items() if not dq or dq[-1] < window_start]:
                del self._hits[key]
            self._last_sweep = now

        return await call_next(request)
