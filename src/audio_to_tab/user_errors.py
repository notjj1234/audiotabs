"""Map domain exceptions to short user-facing primary + optional detail."""

from __future__ import annotations

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


def failure_actions(kind: str) -> tuple[str, ...]:
    return _ACTIONS.get(str(kind or ""), ())


def user_facing_message(exc: BaseException) -> tuple[str, str | None]:
    """Return (primary message, optional technical detail)."""
    # Local imports avoid circular deps with pipeline/roformer at module load.
    from audio_to_tab.pipeline import EmptyTranscriptionError
    from audio_to_tab.roformer import RoFormerTooLongError

    if isinstance(exc, FFmpegMissingError):
        return str(exc), None
    if isinstance(exc, YouTubeDownloadError):
        return str(exc), None
    if isinstance(exc, YouTubeSearchError):
        return str(exc), None
    if isinstance(exc, EmptyTranscriptionError):
        return str(exc), None
    if isinstance(exc, RoFormerTooLongError):
        return str(exc), None
    if isinstance(exc, (FileNotFoundError, OSError)):
        return "Could not read that audio file.", str(exc)
    if isinstance(exc, ValueError):
        return str(exc), None
    return "Conversion failed unexpectedly. Check that the audio file is valid.", str(exc)
