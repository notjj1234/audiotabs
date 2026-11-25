"""Instrument analysis: start, poll, cancel, delete."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response

from .analyses import AnalysisManager
from .auth import require_token
from .errors import http_error
from .routes_jobs import build_config, resolve_source_or_response
from .schemas import JobRequest

router = APIRouter(dependencies=[Depends(require_token)])


def _analyses(request: Request) -> AnalysisManager:
    manager = getattr(request.app.state, "analyses", None)
    if manager is None:
        manager = AnalysisManager(Path(request.app.state.data_dir))
        request.app.state.analyses = manager
    return manager


def _missing():
    return http_error(
        404,
        code="analysis_missing",
        message="This analysis is no longer available. Go back and convert again.",
    )


@router.post("/api/analyses", status_code=202, response_model=None)
def api_create_analysis(body: JobRequest, request: Request):
    config, config_meta = build_config(body)
    resolved, failure = resolve_source_or_response(body, Path(request.app.state.data_dir))
    if failure is not None:
        return failure
    audio_path, youtube_url, source = resolved
    rec = _analyses(request).start(
        title=config.title,
        audio_path=audio_path,
        youtube_url=youtube_url,
        config=config,
        source=source,
        config_meta=config_meta,
        trim_start_sec=float(body.trim_start_sec or 0.0),
    )
    return {"analysis_id": rec.id, "state": rec.state}


@router.get("/api/analyses/{analysis_id}")
def api_get_analysis(analysis_id: str, request: Request) -> dict:
    snap = _analyses(request).snapshot(analysis_id)
    if snap is None:
        raise _missing()
    return snap


@router.post("/api/analyses/{analysis_id}/cancel", status_code=202)
def api_cancel_analysis(analysis_id: str, request: Request) -> dict:
    rec = _analyses(request).cancel(analysis_id)
    if rec is None:
        raise _missing()
    return {"analysis_id": rec.id, "state": rec.state}


@router.delete("/api/analyses/{analysis_id}", status_code=204)
def api_delete_analysis(analysis_id: str, request: Request) -> Response:
    if not _analyses(request).delete(analysis_id):
        raise _missing()
    return Response(status_code=204)
