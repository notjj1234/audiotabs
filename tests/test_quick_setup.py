"""Quick setup defaults and fingering wiring."""

from __future__ import annotations

from pathlib import Path


def test_quick_setup_defaults_values():
    from audio_to_tab.quick_setup import apply_quick_setup_defaults

    state: dict = {
        "tab_transcription_preset": "full_mix",
        "tab_setup_tuning": "Drop D",
        "tab_setup_capo": 4,
        "tab_setup_fingering": "position",
        "tab_safer_length": False,
    }
    apply_quick_setup_defaults(state)
    assert state["tab_transcription_preset"] == "solo"
    assert state["tab_setup_tuning"] == "Standard (EADGBE)"
    assert state["tab_setup_capo"] == 0
    assert state["tab_setup_fingering"] == "playable"
    assert state["tab_safer_length"] is True


def test_entry_wires_fingering_preference():
    source = (
        Path(__file__).resolve().parents[1] / "app" / "web" / "src" / "lib" / "screens" / "Entry.svelte"
    ).read_text(encoding="utf-8")
    assert "fingering" in source
    assert "fingering_preference" in source
