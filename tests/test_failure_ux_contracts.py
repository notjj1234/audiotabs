"""Source-contract locks for Tab PDF failure-mode UX (no Streamlit runtime)."""

from __future__ import annotations

from pathlib import Path

from audio_to_tab.pipeline import EMPTY_TRANSCRIPTION_MESSAGE
from audio_to_tab.separate import GUITAR_FT_CACHE_HINT


def _tab_pdf_source() -> str:
    return (Path(__file__).resolve().parents[1] / "ui" / "pages" / "tab_pdf.py").read_text(
        encoding="utf-8"
    )


def test_failure_ux_contract_strings_present():
    source = _tab_pdf_source()
    assert "ffmpeg is required for conversion" in source
    assert "ffmpeg_install_hint" in source
    assert "disabled=convert_disabled" in source or "disabled=not has_ffmpeg" in source or "convert_disabled" in source
    assert "RoFormer limit on this machine" in source
    assert "Use Demucs instead" in source
    assert "Paste media URL" in source
    assert "guitar_ft_weights_cached()" in source
    assert 'key="tab_expert_options"' in source
    assert "Solo / fingerstyle" in source
    assert "tab_pdf_empty_recovery" in source
    assert "user_facing_message" in source
    assert "Best results: clean solo guitar" in source
    assert 'key="tab_full_track_confirm"' in source


def test_empty_transcription_message_lists_actions():
    msg = EMPTY_TRANSCRIPTION_MESSAGE.lower()
    assert "mix-aware" in msg or "mix aware" in msg
    assert "onset" in msg or "threshold" in msg or "expert" in msg
    assert "solo" in msg


def test_guitar_ft_cache_hint_mentions_ui_not_missing_cli():
    assert "audio-isolate" not in GUITAR_FT_CACHE_HINT
    assert "Tab PDF" in GUITAR_FT_CACHE_HINT or "Expert" in GUITAR_FT_CACHE_HINT
