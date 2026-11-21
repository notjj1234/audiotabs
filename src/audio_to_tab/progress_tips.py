"""Elapsed clock and stage tips for the studio progress card."""

from __future__ import annotations

_TIPS: dict[str, str] = {
    "ingest": "Large or remote files take longer to load.",
    "separate": "Full-band mixes take longer than clean solo guitar.",
    "transcribe": "Busy mixes may need the Solo / fingerstyle preset.",
    "tab": "Fret positions are a draft — check them before you trust them.",
    "chords": "Chord names follow the sounding pitch after capo and transpose.",
    "lyrics": "Lyrics appear only when a vocal stem and transcriber are available.",
    "pdf": "Writing the PDF and download files.",
}


def format_elapsed(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def progress_tip_for(stage_id: str) -> str:
    return _TIPS.get(str(stage_id or ""), "")
