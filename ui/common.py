"""Shared helpers for the Tab PDF Streamlit UI."""

from __future__ import annotations

import base64
import json
import logging
import sys
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from app.server.store import (  # noqa: E402
    _META_FILENAME,
    default_data_dir,
    delete_run_path,
    resolve_run_dir,
)
from app.server.store import (  # noqa: E402
    write_run_metadata as write_run_metadata,
)

DATA_DIR = default_data_dir()
DEFAULT_CONVERSION_TITLE = "Guitar Tab"


def _clean_display_title(raw: str) -> str:
    text = " ".join(str(raw or "").replace("\x00", "").split()).strip()
    return text


def suggested_conversion_title(
    *,
    filename: str | None = None,
    youtube_title: str | None = None,
    media_url: str | None = None,
) -> str:
    """Display-safe conversion name from the best available source.

    Prefer YouTube title, then upload filename stem, then media-URL basename.
    Does not use ingest ``_title_stem`` (alnum-only matching form).
    """
    yt = _clean_display_title(youtube_title or "")
    if yt:
        return yt
    if filename:
        try:
            stem = Path(_safe_upload_name(filename)).stem
        except ValueError:
            stem = ""
        stem = _clean_display_title(stem)
        if stem:
            return stem
    url = str(media_url or "").strip()
    if url:
        path_name = unquote(Path(urlparse(url).path).name)
        stem = _clean_display_title(Path(path_name).stem if path_name else "")
        if stem:
            return stem
    return ""


def is_default_conversion_title(title: str | None) -> bool:
    return _clean_display_title(title or "") in {"", DEFAULT_CONVERSION_TITLE}


def maybe_autofill_conversion_title(state: dict, suggested: str) -> bool:
    """Write ``tab_pdf_title`` only when it is still the default. Returns True if set."""
    suggested = _clean_display_title(suggested)
    if not suggested or not is_default_conversion_title(state.get("tab_pdf_title")):
        return False
    state["tab_pdf_title"] = suggested
    return True

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


def cached_upload_preview(state: dict, uploaded_file) -> Path:
    """Save an upload once per (name, size); reuse the path across Streamlit reruns."""
    name = _safe_upload_name(getattr(uploaded_file, "name", None))
    size = getattr(uploaded_file, "size", None)
    signature = (name, int(size) if size is not None else None)
    cached_sig = state.get("_tab_upload_preview_sig")
    cached_path = state.get("_tab_upload_preview_path")
    if cached_sig == signature and cached_path:
        path = Path(str(cached_path))
        if path.is_file():
            return path
    path = save_upload(uploaded_file)
    state["_tab_upload_preview_sig"] = signature
    state["_tab_upload_preview_path"] = str(path)
    return path


def run_output_dir() -> Path:
    out = DATA_DIR / str(uuid.uuid4())
    out.mkdir(parents=True, exist_ok=True)
    return out


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


def _resolved_run_dir(run_dir: str | Path) -> Path | None:
    """Return a run directory only if it resolves inside DATA_DIR."""
    return resolve_run_dir(DATA_DIR, run_dir)


def delete_run(run_dir: str | Path) -> bool:
    """Permanently remove a run folder under DATA_DIR. Returns True if deleted."""
    return delete_run_path(DATA_DIR, run_dir)


def delete_runs(run_dirs: list[str | Path]) -> int:
    """Hard-delete each run dir; returns how many were removed."""
    return sum(1 for run_dir in run_dirs if delete_run(run_dir))


def max_upload_mb() -> int:
    import streamlit as st

    try:
        return int(st.get_option("server.maxUploadSize"))
    except Exception:
        return 200


def max_upload_caption() -> str:
    return f"Maximum file size: {max_upload_mb()} MB."
