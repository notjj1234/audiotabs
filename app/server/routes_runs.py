"""Read/delete API for completed runs."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import require_token
from .store import RunRecord, delete_run, get_run, list_runs

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


@router.get("/api/runs")
def api_list_runs(request: Request) -> list[dict]:
    return [_serialize(record) for record in list_runs(_data_dir(request))]


@router.get("/api/runs/{run_id}")
def api_get_run(run_id: str, request: Request) -> dict:
    record = get_run(_data_dir(request), run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _serialize(record)


@router.delete("/api/runs/{run_id}")
def api_delete_run(run_id: str, request: Request) -> dict:
    if not delete_run(_data_dir(request), run_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"deleted": True}
