"""Canonical run persistence.

Runs are folders under ``DATA_DIR`` named by UUID, each holding
``meta.json`` (see ``_META_FILENAME``) plus artifact files. This module is
framework-free so both the FastAPI server and the legacy Streamlit UI can
share one implementation.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

_META_FILENAME = "meta.json"


@dataclass
class RunRecord:
    id: str
    dir: Path
    title: str
    created_at: float
    artifacts: dict[str, Path]
    details: dict
    feedback: dict | None
    source: dict | None
    config: dict | None
    view: dict | None = None


def default_data_dir() -> Path:
    """Run storage root: ``AUDIO_TOOLS_DATA_DIR`` override, else repo default."""
    override = os.environ.get("AUDIO_TOOLS_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "ui_runs"


def _read_meta(meta_path: Path) -> dict | None:
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def _record_from_dir(run_dir: Path) -> RunRecord | None:
    meta = _read_meta(run_dir / _META_FILENAME)
    if meta is None:
        return None
    try:
        created_at = float(meta.get("created_at") or 0.0)
    except (TypeError, ValueError):
        created_at = 0.0
    artifacts: dict[str, Path] = {}
    for name, value in (meta.get("artifacts") or {}).items():
        path = Path(str(value))
        artifacts[str(name)] = path if path.is_absolute() else run_dir / path
    return RunRecord(
        id=run_dir.name,
        dir=run_dir,
        title=str(meta.get("title") or ""),
        created_at=created_at,
        artifacts=artifacts,
        details=meta.get("details") if isinstance(meta.get("details"), dict) else {},
        feedback=meta.get("feedback") if isinstance(meta.get("feedback"), dict) else None,
        source=meta.get("source") if isinstance(meta.get("source"), dict) else None,
        config=meta.get("config") if isinstance(meta.get("config"), dict) else None,
        view=meta.get("view") if isinstance(meta.get("view"), dict) else None,
    )


def list_runs(data_dir: Path) -> list[RunRecord]:
    """Completed runs under ``data_dir``, newest first."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return []
    records = []
    for child in data_dir.iterdir():
        if not child.is_dir():
            continue
        record = _record_from_dir(child)
        if record is not None:
            records.append(record)
    records.sort(key=lambda r: r.created_at, reverse=True)
    return records


def _guarded_run_dir(data_dir: Path, run_id: str) -> Path | None:
    """Resolve ``data_dir / run_id`` only when it stays inside ``data_dir``."""
    run_id = str(run_id or "")
    if not run_id or run_id in {".", ".."} or Path(run_id).name != run_id:
        return None
    try:
        root = Path(data_dir).resolve()
        candidate = (Path(data_dir) / run_id).resolve()
    except OSError:
        return None
    if candidate.parent != root or not candidate.is_dir():
        return None
    return candidate


def get_run(data_dir: Path, run_id: str) -> RunRecord | None:
    run_dir = _guarded_run_dir(data_dir, run_id)
    if run_dir is None:
        return None
    return _record_from_dir(run_dir)


def delete_run(data_dir: Path, run_id: str) -> bool:
    """Remove a run folder by id. Refuses anything outside ``data_dir``."""
    run_dir = _guarded_run_dir(data_dir, run_id)
    if run_dir is None:
        return False
    shutil.rmtree(run_dir)
    return True


def resolve_run_dir(data_dir: Path, run_dir: str | Path) -> Path | None:
    """Return ``run_dir`` only if it resolves inside ``data_dir``."""
    try:
        root = Path(data_dir).resolve()
        candidate = Path(run_dir).expanduser().resolve()
    except OSError:
        return None
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def delete_run_path(data_dir: Path, run_dir: str | Path) -> bool:
    """Path-based variant of :func:`delete_run` for legacy UI callers."""
    candidate = resolve_run_dir(data_dir, run_dir)
    if candidate is None or not candidate.is_dir():
        return False
    shutil.rmtree(candidate)
    return True


def write_run_metadata(
    run_dir: Path,
    *,
    page: str,
    title: str,
    artifacts: dict[str, str] | dict[str, Path],
    details: dict | None = None,
    source: dict | None = None,
    config: dict | None = None,
    feedback: dict | None = None,
    view: dict | None = None,
) -> None:
    """Write ``meta.json`` atomically, preserving keys this call does not set.

    Existing ``created_at`` is kept so later updates (e.g. feedback) do not
    rewrite a run's birth time; unknown legacy keys survive the round trip.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = _read_meta(run_dir / _META_FILENAME) or {}
    meta["page"] = page
    meta["title"] = title
    meta.setdefault("created_at", time.time())
    meta["artifacts"] = {k: str(v) for k, v in artifacts.items()}
    if details is not None:
        meta["details"] = details
    if source is not None:
        meta["source"] = source
    if config is not None:
        meta["config"] = config
    if feedback is not None:
        meta["feedback"] = feedback
    if view is not None:
        meta["view"] = view

    fd, tmp_name = tempfile.mkstemp(dir=run_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(meta, handle)
        os.replace(tmp_name, run_dir / _META_FILENAME)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
