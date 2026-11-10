"""Guitar tuning and fretboard utilities."""

from __future__ import annotations

from dataclasses import dataclass

STANDARD_TUNING_MIDI = (40, 45, 50, 55, 59, 64)  # E2 A2 D3 G3 B3 E4
STANDARD_TUNING_NAMES = ("E", "A", "D", "G", "B", "e")
GUITAR_PITCH_MIN = 40  # E2
GUITAR_PITCH_MAX = 88  # E6

TUNING_PRESETS: dict[str, tuple[tuple[int, ...], tuple[str, ...]]] = {
    "Standard (EADGBE)": (STANDARD_TUNING_MIDI, STANDARD_TUNING_NAMES),
    "Drop D": ((38, 45, 50, 55, 59, 64), ("D", "A", "D", "G", "B", "e")),
    "Half-step down": ((39, 44, 49, 54, 58, 63), ("Eb", "Ab", "Db", "Gb", "Bb", "eb")),
}


def tuning_preset(name: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Return ``(open-string MIDI, display names)`` for a tuning that changes frets."""
    try:
        return TUNING_PRESETS[name]
    except KeyError as exc:
        known = ", ".join(TUNING_PRESETS)
        raise ValueError(f"Unknown tuning {name!r}. Choose from: {known}") from exc


@dataclass(frozen=True)
class FretPosition:
    string: int  # 0 = low E, 5 = high e
    fret: int
    pitch: int


def positions_for_pitch(pitch: int, tuning: tuple[int, ...] = STANDARD_TUNING_MIDI, max_fret: int = 24) -> list[FretPosition]:
    """All valid (string, fret) pairs for a MIDI pitch on a fretted instrument."""
    positions: list[FretPosition] = []
    for string_idx, open_pitch in enumerate(tuning):
        fret = pitch - open_pitch
        if 0 <= fret <= max_fret:
            positions.append(FretPosition(string=string_idx, fret=fret, pitch=pitch))
    return positions


def midi_note_name(pitch: int) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return f"{names[pitch % 12]}{pitch // 12 - 1}"
