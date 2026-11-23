"""Read/delete API for completed runs, plus score/export/audio/feedback."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .auth import require_token
from .errors import http_error
from .schemas import ExportRequest, FeedbackRequest
from .store import RunRecord, delete_run, get_run, list_runs, write_run_metadata

router = APIRouter(dependencies=[Depends(require_token)])


def _load_diagnostics(record: RunRecord) -> dict | None:
    """Parsed lead/rhythm split diagnostics when the run produced them."""
    path = record.artifacts.get("lead_rhythm_split_diagnostics")
    if path is None:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _serialize(record: RunRecord) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "created_at": record.created_at,
        "artifacts": {
            name: path.is_file() for name, path in sorted(record.artifacts.items())
        },
        "details": record.details,
        "feedback": record.feedback,
        "source": record.source,
        "config": record.config,
        "diagnostics": _load_diagnostics(record),
    }


def _data_dir(request: Request) -> Path:
    return Path(request.app.state.data_dir)


def _require_run(request: Request, run_id: str) -> RunRecord:
    record = get_run(_data_dir(request), run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@router.get("/api/runs")
def api_list_runs(request: Request) -> list[dict]:
    return [_serialize(record) for record in list_runs(_data_dir(request))]


@router.get("/api/runs/{run_id}")
def api_get_run(run_id: str, request: Request) -> dict:
    return _serialize(_require_run(request, run_id))


@router.delete("/api/runs/{run_id}")
def api_delete_run(run_id: str, request: Request) -> dict:
    if not delete_run(_data_dir(request), run_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"deleted": True}


@router.get("/api/runs/{run_id}/score")
def api_run_score(
    run_id: str,
    request: Request,
    view: str = Query("staff"),
    tuning: str | None = None,
    capo: int | None = None,
    transpose: int | None = None,
    bars: int | None = None,
) -> dict:
    from .score import build_score

    record = _require_run(request, run_id)
    return build_score(
        record,
        view=view,
        tuning=tuning,
        capo=capo,
        transpose=transpose,
        bars=bars,
    )


@router.post("/api/runs/{run_id}/export")
def api_run_export(run_id: str, body: ExportRequest, request: Request) -> FileResponse:
    from .score import export_run

    record = _require_run(request, run_id)
    exports_root = _data_dir(request) / "exports"
    try:
        path = export_run(
            record,
            fmt=body.format,
            tuning=body.tuning,
            capo=body.capo,
            transpose=body.transpose,
            bars=body.bars,
            exports_root=exports_root,
        )
    except FileNotFoundError as exc:
        raise http_error(404, code="export_missing", message=str(exc)) from exc
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, filename=path.name, media_type=media_type)


@router.post("/api/runs/{run_id}/feedback")
def api_run_feedback(run_id: str, body: FeedbackRequest, request: Request) -> dict:
    record = _require_run(request, run_id)
    write_run_metadata(
        record.dir,
        page="tab_pdf",
        title=record.title,
        artifacts=record.artifacts,
        feedback={"answer": body.answer},
    )
    updated = get_run(_data_dir(request), run_id)
    assert updated is not None
    return _serialize(updated)


@router.get("/api/runs/{run_id}/audio")
def api_run_audio(
    run_id: str,
    request: Request,
    kind: str = Query("original"),
) -> FileResponse:
    record = _require_run(request, run_id)
    key = "guitar_stem" if kind == "stem" else "playback"
    path = record.artifacts.get(key)
    if path is None or not Path(path).is_file():
        # Original listen often uses playback; fall back
        if kind == "original":
            path = record.artifacts.get("playback")
        if path is None or not Path(path).is_file():
            raise http_error(404, code="audio_missing", message="Audio not available for this run.")
    media_type = mimetypes.guess_type(Path(path).name)[0] or "audio/wav"
    return FileResponse(path, media_type=media_type, filename=Path(path).name)
