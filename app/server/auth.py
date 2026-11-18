"""Launch-token gate for the local API."""

from __future__ import annotations

import hmac
import os
import secrets

from fastapi import HTTPException, Request

TOKEN_ENV_VAR = "TABPDF_TOKEN"


def resolve_token(explicit: str | None = None) -> str:
    """Launch token: explicit argument, then ``TABPDF_TOKEN``, then random."""
    if explicit:
        return explicit
    env = os.environ.get(TOKEN_ENV_VAR)
    if env:
        return env
    return secrets.token_urlsafe(32)


def require_token(request: Request) -> None:
    expected = request.app.state.tab_token
    provided = request.headers.get("X-Tab-Token", "")
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="missing or invalid token")
