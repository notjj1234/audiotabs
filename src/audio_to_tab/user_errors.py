"""Map domain exceptions to short user-facing primary + optional detail."""

from __future__ import annotations

import re

from audio_to_tab.ingest import FFmpegMissingError, YouTubeDownloadError, YouTubeSearchError

_ACTIONS: dict[str, tuple[str, ...]] = {
    "empty": ("solo_preset", "open_expert"),
    "youtube": ("use_upload",),
    "roformer": ("use_demucs",),
    "separate": ("retry_without_separation",),
    "ffmpeg": (),
    "read": (),
    "generic": (),
}


def failure_kind(exc: BaseException) -> str:
    """Classify an exception for recovery CTAs."""
    from audio_to_tab.pipeline import EmptyTranscriptionError
    from audio_to_tab.roformer import RoFormerTooLongError

    if isinstance(exc, EmptyTranscriptionError):
        return "empty"
    if isinstance(exc, YouTubeDownloadError):
        return "youtube"
    if isinstance(exc, FFmpegMissingError):
        return "ffmpeg"
    if isinstance(exc, RoFormerTooLongError):
        return "roformer"
    if isinstance(exc, (FileNotFoundError, OSError)):
        return "read"
    if "Guitar stem separation failed" in str(exc):
        return "separate"
    return "generic"


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
DETAIL_MAX_CHARS = 300

# Native audio libraries that failed to load (torchcodec / FFmpeg shared libs).
_LIBRARY_MARKERS = ("libtorchcodec", "library not loaded", "could not load this library", "dlopen(")

LIBRARY_MESSAGE = (
    "The instrument separator couldn't start because an audio library on this computer "
    "is missing or the wrong version. Reinstall FFmpeg (on a Mac: brew reinstall ffmpeg), "
    "then try again."
)
SEPARATION_MESSAGE = "Separating the instruments failed. Try again, or upload a different file."


def short_detail(text: str | None) -> str | None:
    """One readable line of technical detail: no colour codes, no traceback, capped."""
    if not text:
        return None
    clean = _ANSI.sub("", str(text))
    # Tracebacks and library dumps: keep the first sentence-ish line only.
    for cut in (" [start of ", " Traceback (most recent call last)", "\nTraceback", "Likely causes:"):
        index = clean.find(cut)
        if index > 0:
            clean = clean[:index]
    line = " ".join(clean.split())
    if len(line) > DETAIL_MAX_CHARS:
        line = line[: DETAIL_MAX_CHARS - 1].rstrip() + "…"
    return line or None


def _split_details(text: str) -> tuple[str, str | None]:
    """Messages that end in "Details: …" keep the plain part up front."""
    clean = _ANSI.sub("", text)
    head, sep, tail = clean.partition(" Details:")
    if not sep:
        return clean.strip(), None
    return head.strip(), short_detail(tail)


def failure_actions(kind: str) -> tuple[str, ...]:
    return _ACTIONS.get(str(kind or ""), ())


def user_facing_message(exc: BaseException) -> tuple[str, str | None]:
    """Return (primary message, optional technical detail)."""
    # Local imports avoid circular deps with pipeline/roformer at module load.
    from audio_to_tab.pipeline import EmptyTranscriptionError
    from audio_to_tab.roformer import RoFormerTooLongError

    raw = str(exc)
    lowered = raw.lower()
    if isinstance(exc, FFmpegMissingError):
        return str(exc), None
    if isinstance(exc, YouTubeDownloadError):
        return _split_details(raw)
    if any(marker in lowered for marker in _LIBRARY_MARKERS):
        return LIBRARY_MESSAGE, short_detail(raw)
    if "stem separation failed" in lowered or "separation failed" in lowered:
        return SEPARATION_MESSAGE, short_detail(raw)
    if isinstance(exc, YouTubeSearchError):
        return str(exc), None
    if isinstance(exc, EmptyTranscriptionError):
        return str(exc), None
    if isinstance(exc, RoFormerTooLongError):
        return str(exc), None
    if isinstance(exc, (FileNotFoundError, OSError)):
        return "Could not read that audio file.", short_detail(raw)
    if isinstance(exc, ValueError):
        return short_detail(raw) or "That input couldn't be used.", None
    return "Something went wrong while making the tab. Try again.", short_detail(raw)
