"""Recent-run listing helpers over the shared store."""

from __future__ import annotations

import json
from pathlib import Path

from app.server.store import (
    default_data_dir,
    delete_run_path,
    resolve_run_dir,
    write_run_metadata,
)

_META_FILENAME = "meta.json"
DATA_DIR = default_data_dir()


def list_recent_runs(page: str, limit: int = 10, *, data_dir: Path | None = None) -> list[dict]:
    root = Path(data_dir) if data_dir is not None else DATA_DIR
    if not root.is_dir():
        return []
    runs: list[dict] = []
    for run_dir in root.iterdir():
        meta_path = run_dir / _META_FILENAME
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if meta.get("page") != page:
            continue
        meta["run_dir"] = str(run_dir)
        runs.append(meta)
    runs.sort(key=lambda m: m.get("created_at", 0), reverse=True)
    return runs[:limit]


def delete_run(run_dir: str | Path, *, data_dir: Path | None = None) -> bool:
    root = Path(data_dir) if data_dir is not None else DATA_DIR
    return delete_run_path(root, run_dir)


def delete_runs(run_dirs: list[str | Path], *, data_dir: Path | None = None) -> int:
    return sum(1 for run_dir in run_dirs if delete_run(run_dir, data_dir=data_dir))


__all__ = [
    "DATA_DIR",
    "delete_run",
    "delete_runs",
    "list_recent_runs",
    "resolve_run_dir",
    "write_run_metadata",
]
