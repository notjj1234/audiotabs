"""Failure-mode UX contracts against the web Entry screen + user_errors."""

from __future__ import annotations

from pathlib import Path

from audio_to_tab.pipeline import EMPTY_TRANSCRIPTION_MESSAGE
from audio_to_tab.separate import GUITAR_FT_CACHE_HINT


def _entry_source() -> str:
    return (
        Path(__file__).resolve().parents[1] / "app" / "web" / "src" / "lib" / "screens" / "Entry.svelte"
    ).read_text(encoding="utf-8")


def test_entry_wires_ffmpeg_gate_and_advanced_controls():
    source = _entry_source()
    assert "ffmpeg" in source
    assert "Safer length" in source
    assert "fullTrackConfirm" in source
    assert "onset" in source
    assert "YouTube" in source
    assert "solo" in source and "full_mix" in source


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
