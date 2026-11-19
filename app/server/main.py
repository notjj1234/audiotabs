"""FastAPI application: token gate, health probe, static front end."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .auth import resolve_token
from .paths import web_dist_dir
from .routes_runs import router as runs_router
from .store import default_data_dir

try:
    _VERSION = version("audio-to-tab-pdf")
except PackageNotFoundError:  # pragma: no cover - package always installed in practice
    _VERSION = "0.1.6"


def create_app(*, data_dir: Path | None = None, token: str | None = None) -> FastAPI:
    app = FastAPI(title="Tab PDF")
    app.state.tab_token = resolve_token(token)
    app.state.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": _VERSION}

    app.include_router(runs_router)

    dist = web_dist_dir()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    else:

        @app.get("/", response_class=HTMLResponse)
        def dist_placeholder() -> str:
            return "Run make ui-build"

    return app
