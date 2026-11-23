"""Conversion title helpers (framework-free)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

DEFAULT_CONVERSION_TITLE = "Guitar Tab"


def _safe_upload_name(name: str | None) -> str:
    base = Path(name or "").name.replace("\x00", "").strip()
    if not base or base in {".", ".."}:
        raise ValueError("Invalid upload filename")
    return base


def _clean_display_title(raw: str) -> str:
    text = " ".join(str(raw or "").replace("\x00", "").split()).strip()
    return text


def suggested_conversion_title(
    *,
    filename: str | None = None,
    youtube_title: str | None = None,
    media_url: str | None = None,
) -> str:
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
    suggested = _clean_display_title(suggested)
    if not suggested or not is_default_conversion_title(state.get("tab_pdf_title")):
        return False
    state["tab_pdf_title"] = suggested
    return True
