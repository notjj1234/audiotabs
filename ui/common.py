"""Shared helpers for the Tab PDF Streamlit UI."""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _resolve_data_dir() -> Path:
    override = os.environ.get("AUDIO_TOOLS_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _REPO_ROOT / "data" / "ui_runs"


DATA_DIR = _resolve_data_dir()
_META_FILENAME = "meta.json"

AUDIO_UPLOAD_TYPES: list[str] = [
    "audio",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/flac",
    "audio/x-flac",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
]


def ensure_src_path() -> None:
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))


def app_version() -> str:
    ensure_src_path()
    try:
        from audio_to_tab import __version__

        return str(__version__)
    except Exception:
        logger.warning("Could not determine app version from audio_to_tab.__version__")
        return "unknown"


def app_icon_png() -> Path:
    return _REPO_ROOT / "assets" / "app-icon.png"


def app_icon_data_uri() -> str | None:
    path = app_icon_png()
    if not path.is_file():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _safe_upload_name(name: str | None) -> str:
    base = Path(name or "").name.replace("\x00", "").strip()
    if not base or base in {".", ".."}:
        raise ValueError("Invalid upload filename")
    return base


def save_upload(uploaded_file) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = DATA_DIR / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / _safe_upload_name(getattr(uploaded_file, "name", None))
    dest.write_bytes(uploaded_file.getvalue())
    return dest


def run_output_dir() -> Path:
    out = DATA_DIR / str(uuid.uuid4())
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_run_metadata(
    run_dir: Path,
    *,
    page: str,
    title: str,
    artifacts: dict[str, str],
) -> None:
    meta = {
        "page": page,
        "title": title,
        "created_at": time.time(),
        "artifacts": {k: str(v) for k, v in artifacts.items()},
    }
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    (Path(run_dir) / _META_FILENAME).write_text(json.dumps(meta), encoding="utf-8")


def list_recent_runs(page: str, limit: int = 10) -> list[dict]:
    if not DATA_DIR.is_dir():
        return []
    runs: list[dict] = []
    for run_dir in DATA_DIR.iterdir():
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


def max_upload_mb() -> int:
    import streamlit as st

    try:
        return int(st.get_option("server.maxUploadSize"))
    except Exception:
        return 200


def max_upload_caption() -> str:
    return f"Maximum file size: {max_upload_mb()} MB."
