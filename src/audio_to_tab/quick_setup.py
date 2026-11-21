"""Defaults for the entry Quick setup block."""

from __future__ import annotations

QUICK_SETUP_TUNING = "Standard (EADGBE)"
QUICK_SETUP_FINGERING = "playable"


def apply_quick_setup_defaults(state: dict) -> None:
    state["tab_transcription_preset"] = "solo"
    state["tab_setup_tuning"] = QUICK_SETUP_TUNING
    state["tab_setup_capo"] = 0
    state["tab_setup_fingering"] = QUICK_SETUP_FINGERING
    state["tab_safer_length"] = True
