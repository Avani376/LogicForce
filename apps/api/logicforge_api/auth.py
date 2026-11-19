"""Optional bearer-token auth for write endpoints (D5, Phase 7).

Mode is driven by the environment:
- LOGICFORGE_AUTH_TOKEN unset → single-user local mode: writes are allowed
  (the API binds localhost by default; production deployments set the token).
- LOGICFORGE_AUTH_TOKEN set → every write requires `Authorization: Bearer <token>`.
  The token is compared with constant-time comparison and never logged.
"""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Request

_TOKEN_ENV = "LOGICFORGE_AUTH_TOKEN"


def auth_is_enabled() -> bool:
    return bool(os.environ.get(_TOKEN_ENV, "").strip())


def require_write_auth(request: Request) -> None:
    expected = os.environ.get(_TOKEN_ENV, "").strip()
    if not expected:
        return  # single-user local mode
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            detail={"code": "AUTH_REQUIRED", "message": "write requests require Authorization: Bearer <token>"},
        )
    if not secrets.compare_digest(token.strip(), expected):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            detail={"code": "AUTH_INVALID", "message": "invalid token"},
        )
