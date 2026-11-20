"""Minimal guitar-engine helpers for Tab PDF (no Isolation UI state)."""

from __future__ import annotations

from typing import Any

LEAD_RHYTHM_SPLIT_ENGINE_ID = "guitar_lead_rhythm_split"

TRACK_OPTIONS: dict[str, dict[str, Any]] = {
    "guitar_demucs_6s": {
        "label": "Guitar (Demucs 6-stem, weaker). Other instruments still bleed in.",
        "stem": "guitar",
    },
    "guitar_roformer": {
        "label": "Guitar (BS-RoFormer, better, slower). Some bleed remains.",
        "stem": "guitar",
    },
    "guitar_roformer_refine": {
        "label": "Guitar (BS-RoFormer + MelBand refine, best, slowest). Some bleed remains.",
        "stem": "guitar",
    },
    LEAD_RHYTHM_SPLIT_ENGINE_ID: {
        "label": (
            "Lead + Rhythm (Mel-Band RoFormer split by listra92). Best on dual-guitar mixes; "
            "runs guitar-ft isolation first, then a Lead/Rhythm model split."
        ),
        "stem": "lead_rhythm",
    },
}

GUITAR_TRACK_OPTION_IDS = frozenset(TRACK_OPTIONS)
GUITAR_TRACK_RADIO_ORDER = (
    "guitar_demucs_6s",
    "guitar_roformer",
    "guitar_roformer_refine",
    LEAD_RHYTHM_SPLIT_ENGINE_ID,
)
ROFORMER_GUITAR_OPTION_IDS = frozenset({"guitar_roformer", "guitar_roformer_refine"})


def guitar_track_radio_ids(*, roformer_available: bool, lead_rhythm_available: bool = True) -> tuple[str, ...]:
    ids = [oid for oid in GUITAR_TRACK_RADIO_ORDER if oid != LEAD_RHYTHM_SPLIT_ENGINE_ID]
    if not roformer_available:
        ids = [oid for oid in ids if oid in ("guitar_demucs_6s",)]
    if lead_rhythm_available:
        ids.append(LEAD_RHYTHM_SPLIT_ENGINE_ID)
    return tuple(ids)


def normalize_guitar_track_selection(
    guitar: str,
    *,
    roformer_available: bool,
    lead_rhythm_available: bool = True,
) -> str:
    pick = (guitar or "guitar_demucs_6s").strip()
    if pick in ROFORMER_GUITAR_OPTION_IDS and not roformer_available:
        return "guitar_demucs_6s"
    if pick == LEAD_RHYTHM_SPLIT_ENGINE_ID and not lead_rhythm_available:
        return "guitar_demucs_6s"
    if pick in GUITAR_TRACK_OPTION_IDS:
        return pick
    return "guitar_demucs_6s"


def default_guitar_track_option(*, roformer_available: bool, prefer_roformer: bool = True) -> str:
    if prefer_roformer and roformer_available:
        return "guitar_roformer"
    return "guitar_demucs_6s"
