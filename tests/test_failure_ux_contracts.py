"""Failure-mode UX contracts against the web Entry screen + user_errors."""

from __future__ import annotations

from pathlib import Path

from audio_to_tab.pipeline import EMPTY_TRANSCRIPTION_MESSAGE
from audio_to_tab.separate import GUITAR_FT_CACHE_HINT


def _entry_source() -> str:
    return (
        Path(__file__).resolve().parents[1] / "app" / "web" / "src" / "lib" / "screens" / "Entry.svelte"
    ).read_text(encoding="utf-8")


def test_entry_offers_only_the_three_sources_and_the_ffmpeg_gate():
    """First screen: upload, YouTube search or a link. Settings live on the picker."""
    source = _entry_source()
    assert "ffmpeg" in source
    assert "Upload a file" in source
    assert "Search YouTube" in source
    assert "Paste a link" in source
    for setting in ("Safer length", "Tuning", "Capo", "Advanced", "Solo guitar"):
        assert setting not in source
    flow = (Path(__file__).resolve().parents[1] / "app" / "web" / "src" / "lib" / "convertFlow.ts").read_text(
        encoding="utf-8"
    )
    assert "full_mix" in flow and "fullTrackConfirm" in flow


def test_empty_transcription_message_lists_actions():
    msg = EMPTY_TRANSCRIPTION_MESSAGE.lower()
    assert "mix-aware" in msg or "mix aware" in msg
    assert "onset" in msg or "threshold" in msg or "expert" in msg
    assert "solo" in msg


def test_guitar_ft_cache_hint_mentions_ui_not_missing_cli():
    assert "audio-isolate" not in GUITAR_FT_CACHE_HINT
    assert "Tab PDF" in GUITAR_FT_CACHE_HINT or "Expert" in GUITAR_FT_CACHE_HINT


def test_failure_kind_and_actions_table():
    from audio_to_tab.ingest import YouTubeDownloadError
    from audio_to_tab.pipeline import EmptyTranscriptionError
    from audio_to_tab.user_errors import failure_actions, failure_kind

    assert failure_kind(EmptyTranscriptionError("x")) == "empty"
    assert failure_actions("empty") == ("solo_preset", "open_expert")
    assert failure_kind(YouTubeDownloadError("blocked")) == "youtube"
    assert failure_actions("youtube") == ("use_upload",)
    assert failure_kind(RuntimeError("Guitar stem separation failed: boom")) == "separate"
    assert failure_actions("separate") == ("retry_without_separation",)
    assert failure_actions("generic") == ()


def test_failure_ux_youtube_kind_has_upload_action_only():
    from audio_to_tab.user_errors import failure_actions

    assert failure_actions("youtube") == ("use_upload",)
    assert "solo_preset" not in failure_actions("youtube")


def test_library_load_failure_reads_as_one_plain_sentence_with_a_short_detail():
    from audio_to_tab.user_errors import DETAIL_MAX_CHARS, LIBRARY_MESSAGE, user_facing_message

    raw = (
        "Guitar stem separation failed: Guitar-FT separation failed; not falling back to stock: "
        "Could not load libtorchcodec. Likely causes: 1. FFmpeg is not properly installed... "
        "[start of libtorchcodec loading traceback] FFmpeg version 8: Traceback (most recent call last): "
        + "x" * 4000
    )
    message, detail = user_facing_message(RuntimeError(raw))
    assert message == LIBRARY_MESSAGE
    assert detail is not None and len(detail) <= DETAIL_MAX_CHARS
    assert "Traceback" not in detail and "Likely causes" not in detail


def test_youtube_error_keeps_plain_text_up_front_and_details_apart():
    from audio_to_tab.ingest import YouTubeDownloadError
    from audio_to_tab.user_errors import user_facing_message

    message, detail = user_facing_message(
        YouTubeDownloadError(
            "Could not download this YouTube video. Upload the audio file instead. "
            "Details: \x1b[0;31mERROR:\x1b[0m [youtube] abc: Requested format is not available."
        )
    )
    assert message.endswith("Upload the audio file instead.")
    assert "Details" not in message
    assert detail is not None and "\x1b" not in detail and "Requested format" in detail
