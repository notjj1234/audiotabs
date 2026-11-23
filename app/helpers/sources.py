"""Source-selection and failure helpers (framework-free)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from audio_to_tab.user_errors import failure_kind, user_facing_message

from .guitar_engines import LEAD_RHYTHM_SPLIT_ENGINE_ID


def tab_model_from_guitar_engine(engine: str) -> tuple[str, bool]:
    if engine == "guitar_roformer":
        return "bs_roformer_sw", False
    if engine == "guitar_roformer_refine":
        return "bs_roformer_sw", True
    if engine == LEAD_RHYTHM_SPLIT_ENGINE_ID:
        return "lead_rhythm_split", False
    return "htdemucs_6s", False


# Back-compat alias used by older tests.
_tab_model_from_guitar_engine = tab_model_from_guitar_engine


def active_source(
    source_tab: str,
    *,
    upload_path: Path | None,
    selected_url: str,
    media_url: str,
) -> tuple[Path | None, str]:
    if source_tab == "upload":
        return upload_path, ""
    if source_tab == "youtube":
        return None, (selected_url or "").strip()
    return None, (media_url or "").strip()


_active_source = active_source


def entry_source_selected(
    *,
    has_upload: bool,
    media_url: str = "",
    youtube_url: str = "",
) -> bool:
    return bool(has_upload or (media_url or "").strip() or (youtube_url or "").strip())


def unique_chords(chords: list[Any]) -> list[Any]:
    unique: dict[tuple[str, tuple[Any, ...]], Any] = {}
    for hit in chords:
        unique.setdefault((str(hit.name), tuple(hit.frets)), hit)
    return list(unique.values())


_unique_chords = unique_chords


def record_failure(state: dict, exc: BaseException, *, message: str | None = None) -> None:
    state.pop("tab_pdf_artifacts", None)
    state.pop("tab_pdf_flash", None)
    state.pop("tab_pdf_export_sig", None)
    kind = failure_kind(exc)
    state["tab_pdf_failure_kind"] = kind
    state["tab_pdf_empty_recovery"] = kind == "empty"
    if message is None:
        primary, detail = user_facing_message(exc)
        state["tab_pdf_error"] = primary
        if detail and detail != primary:
            state["tab_pdf_error_detail"] = detail
        else:
            state.pop("tab_pdf_error_detail", None)
        return
    state["tab_pdf_error"] = message
    detail = str(exc)
    if detail and detail != message:
        state["tab_pdf_error_detail"] = detail
    else:
        state.pop("tab_pdf_error_detail", None)
