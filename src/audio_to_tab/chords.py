"""Chord names from the note groups this pipeline already forms."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pretty_midi

from audio_to_tab.tab_generate import (
    TabNote,
    _group_notes_into_events,
    _pick_chord_positions,
)
from audio_to_tab.tuning import tuning_preset

PC_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Longer shapes first so a seventh is not reported as the triad inside it.
_TEMPLATES: tuple[tuple[frozenset[int], str], ...] = (
    (frozenset({0, 4, 7, 11}), "maj7"),
    (frozenset({0, 4, 7, 10}), "7"),
    (frozenset({0, 3, 7, 10}), "m7"),
    (frozenset({0, 3, 6, 10}), "m7b5"),
    (frozenset({0, 3, 6, 9}), "dim7"),
    (frozenset({0, 4, 7, 9}), "6"),
    (frozenset({0, 3, 7, 9}), "m6"),
    (frozenset({0, 4, 7}), ""),
    (frozenset({0, 3, 7}), "m"),
    (frozenset({0, 3, 6}), "dim"),
    (frozenset({0, 4, 8}), "aug"),
    (frozenset({0, 5, 7}), "sus4"),
    (frozenset({0, 2, 7}), "sus2"),
    (frozenset({0, 7}), "5"),
)

_MAJOR = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_MINOR = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)


@dataclass(frozen=True)
class ChordHit:
    start: float
    end: float
    name: str
    frets: tuple[int | None, ...]


def name_chord(pitches: list[int]) -> str | None:
    """Name a pitch set when it is exactly a known guitar chord. Otherwise None."""
    if len({pitch % 12 for pitch in pitches}) < 2:
        return None
    pcs = frozenset(pitch % 12 for pitch in pitches)
    lowest = min(pitches) % 12
    matches: list[tuple[int, int, str]] = []
    for root in range(12):
        intervals = frozenset((pc - root) % 12 for pc in pcs)
        for template, quality in _TEMPLATES:
            if intervals == template:
                matches.append((len(template), root, quality))
                break
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], 0 if item[1] == lowest else 1, item[1]))
    _size, root, quality = matches[0]
    return f"{PC_NAMES[root]}{quality}"


def _correlate(left: list[float], right: tuple[float, ...]) -> float:
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    num = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right, strict=True))
    den_left = sum((a - mean_left) ** 2 for a in left) ** 0.5
    den_right = sum((b - mean_right) ** 2 for b in right) ** 0.5
    if den_left == 0 or den_right == 0:
        return 0.0
    return num / (den_left * den_right)


def detect_key(pitches: list[int]) -> str:
    """Key name from the sounding pitches. Empty input is Unknown."""
    if not pitches:
        return "Unknown"
    histogram = [0.0] * 12
    for pitch in pitches:
        histogram[pitch % 12] += 1.0
    histogram[min(pitches) % 12] += 1.0
    best_name = "Unknown"
    best_score = -2.0
    for root, name in enumerate(PC_NAMES):
        rotated = histogram[root:] + histogram[:root]
        major_score = _correlate(rotated, _MAJOR)
        minor_score = _correlate(rotated, _MINOR)
        if major_score > best_score:
            best_score = major_score
            best_name = f"{name} major"
        if minor_score > best_score:
            best_score = minor_score
            best_name = f"{name} minor"
    return best_name


def sounding_semitones(*, transpose: int, capo: int) -> int:
    return int(transpose) + int(capo)


def shifted_midi(path: str | Path, semitones: int) -> pretty_midi.PrettyMIDI:
    music = pretty_midi.PrettyMIDI(str(path))
    for instrument in music.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            note.pitch = min(127, max(0, int(note.pitch) + int(semitones)))
    return music


def _capo_tuning(tuning_name: str, capo: int) -> tuple[tuple[int, ...], tuple[str, ...]]:
    opens, names = tuning_preset(tuning_name)
    shifted = tuple(min(127, note + int(capo)) for note in opens)
    return shifted, names


def placed_note(
    path: str | Path,
    *,
    transpose: int = 0,
    capo: int = 0,
    tuning_name: str = "Standard (EADGBE)",
) -> TabNote:
    """First sounding tab note after capo and transpose."""
    from audio_to_tab.tab_bundle import tab_document_for

    document = tab_document_for(
        Path(path),
        tempo_bpm=120.0,
        tempo_confidence="high",
        beats_per_measure=4,
        tuning_name=tuning_name,
        capo=capo,
        transpose=transpose,
    )
    if not document.events or not document.events[0].notes:
        raise ValueError("No playable note at that pitch")
    return document.events[0].notes[0]


def _frets_for(pitches: list[int], tuning: tuple[int, ...]) -> tuple[int | None, ...]:
    frets: list[int | None] = [None] * 6
    for position in _pick_chord_positions(pitches, tuning, 5.0, 15):
        if 0 <= position.string < 6:
            frets[position.string] = position.fret
    return tuple(frets)


def _collapse(hits: list[ChordHit]) -> list[ChordHit]:
    collapsed: list[ChordHit] = []
    for hit in hits:
        if collapsed and collapsed[-1].name == hit.name:
            previous = collapsed[-1]
            collapsed[-1] = ChordHit(
                start=previous.start,
                end=max(previous.end, hit.end),
                name=previous.name,
                frets=previous.frets,
            )
            continue
        collapsed.append(hit)
    return collapsed


def chords_from_midi(
    path: str | Path,
    *,
    transpose: int = 0,
    capo: int = 0,
    tuning_name: str = "Standard (EADGBE)",
) -> list[ChordHit]:
    """Name each simultaneous group, in order, after the sounding shift."""
    music = shifted_midi(path, sounding_semitones(transpose=transpose, capo=capo))
    notes: list[pretty_midi.Note] = []
    for instrument in music.instruments:
        if not instrument.is_drum:
            notes.extend(instrument.notes)
    tuning, _names = _capo_tuning(tuning_name, capo)
    hits: list[ChordHit] = []
    for group in _group_notes_into_events(notes):
        pitches = [note.pitch for note in group]
        name = name_chord(pitches)
        if name is None:
            continue
        hits.append(
            ChordHit(
                start=float(group[0].start),
                end=max(float(note.end) for note in group),
                name=name,
                frets=_frets_for(pitches, tuning),
            )
        )
    return _collapse(hits)


def pitches_in_midi(path: str | Path, *, semitones: int) -> list[int]:
    music = shifted_midi(path, semitones)
    pitches: list[int] = []
    for instrument in music.instruments:
        if instrument.is_drum:
            continue
        pitches.extend(int(note.pitch) for note in instrument.notes)
    return pitches


__all__ = [
    "ChordHit",
    "chords_from_midi",
    "detect_key",
    "name_chord",
    "pitches_in_midi",
    "placed_note",
    "shifted_midi",
    "sounding_semitones",
]
