"""FastAPI application factory (module-level singleton app).

Run locally: ``uvicorn logicforge_api.main:app --reload --port 8000``
The service is stateless (ENGINEERING_DECISIONS D5): every endpoint is a pure
function of its request body.
"""

from __future__ import annotations

import os
import time

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from logic_engine import ENGINE_VERSION
from sequential_engine import SEQUENTIAL_ENGINE_VERSION
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from logicforge_api import API_VERSION
from logicforge_api.logging_setup import configure_logging
from logicforge_api.routers import (
    assistant,
    backup,
    circuits,
    cpu8086,
    curriculum,
    explain,
    faults,
    optimize,
    projects,
    sequential,
    verify,
)

app = FastAPI(
    title="LogicForge API",
    description=(
        "Deterministic digital-system engineering engines. "
        "All results are computed by the engines; scope labels state exactly "
        "what was explored."
    ),
    version=ENGINE_VERSION,
)

configure_logging()

root = APIRouter(prefix="/api", tags=["meta"])


@root.get("/health")
def health() -> dict[str, str | bool]:
    """Liveness plus versions and persistence mode, for monitoring."""
    from logicforge_api import auth as auth_module
    from logicforge_api.persistence import _DB_PATH  # noqa: PLC2701 — health introspects its own module

    return {
        "status": "ok",
        "api_version": API_VERSION,
        "engine_version": ENGINE_VERSION,
        "sequential_engine_version": SEQUENTIAL_ENGINE_VERSION,
        "auth_enabled": auth_module.auth_is_enabled(),
        "database": _DB_PATH,
    }


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Monitoring hooks: per-request latency + API version on every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        process_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Process-Time-Ms"] = f"{process_ms:.2f}"
        response.headers["X-API-Version"] = API_VERSION
        return response


app.add_middleware(ObservabilityMiddleware)

from logicforge_api.hardening import (  # noqa: E402  — after app creation, before routes
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
)

app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """Never leak stack traces to clients; keep the standard envelope shape."""
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "INTERNAL_ERROR", "message": "unexpected server error — the request was rejected"}},
    )


app.include_router(root)
app.include_router(circuits.router)
app.include_router(sequential.router)
app.include_router(verify.router)
app.include_router(faults.router)
app.include_router(optimize.router)
app.include_router(cpu8086.router)
app.include_router(explain.router)
app.include_router(curriculum.router)
app.include_router(assistant.router)
app.include_router(projects.router)
app.include_router(projects.runs_router)
app.include_router(backup.router)

# Single-origin production mode: when SERVE_WEB_DIST points at a built frontend,
# the API process serves it too (one container, one origin — used by Dockerfile.full).
# Mounted after all API routers, so /api/* always takes precedence. SPA routes
# (deep links like /fsm) fall back to index.html via the catch-all below.
_web_dist = os.environ.get("SERVE_WEB_DIST", "")
if _web_dist and os.path.isdir(_web_dist):
    _assets_dir = os.path.join(_web_dist, "assets")
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="web-assets")

    @app.get("/{spa_path:path}", include_in_schema=False)
    def spa_fallback(spa_path: str) -> Response:
        """Serve index.html for client-side routes; 404 for missing asset files."""
        if spa_path.startswith("api/") or spa_path.startswith("docs"):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        candidate = os.path.join(_web_dist, spa_path)
        if spa_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_web_dist, "index.html"))
