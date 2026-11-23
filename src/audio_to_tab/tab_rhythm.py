"""Snap note durations and group beams for Songsterr-style tab rhythm glyphs."""

from __future__ import annotations

from dataclasses import dataclass

from audio_to_tab.tab_generate import TabEvent

# Relative to a quarter note. Matches MusicXML nearest-type idea.
_BASE_TYPES: tuple[tuple[float, str, int], ...] = (
    (4.0, "whole", 0),
    (2.0, "half", 0),
    (1.0, "quarter", 0),
    (0.5, "eighth", 1),
    (0.25, "16th", 2),
    (0.125, "32nd", 3),
)


@dataclass(frozen=True)
class RhythmValue:
    type_name: str
    flags: int
    dotted: bool
    beats: float  # length in quarter-note beats (including dot)


def _sec_per_quarter(tempo_bpm: float) -> float:
    tempo = float(tempo_bpm) if tempo_bpm and tempo_bpm > 0 else 120.0
    return 60.0 / tempo


def snap_duration(seconds: float, *, tempo_bpm: float) -> RhythmValue:
    """Nearest note type (and optional dot) for a sounding length in seconds."""
    sec = max(0.01, float(seconds))
    beats = sec / _sec_per_quarter(tempo_bpm)

    best: RhythmValue | None = None
    best_err = float("inf")
    for base, name, flags in _BASE_TYPES:
        for dotted in (False, True):
            candidate = base * (1.5 if dotted else 1.0)
            err = abs(beats - candidate)
            # Prefer undotted on ties; slight bias against dots.
            if dotted:
                err += 1e-6
            if err < best_err:
                best_err = err
                best = RhythmValue(type_name=name, flags=flags, dotted=dotted, beats=candidate)
    assert best is not None
    return best


def _event_duration_sec(event: TabEvent) -> float:
    if not event.notes:
        return 0.25
    return max(note.end for note in event.notes) - float(event.start)


def beam_groups(
    events: list[TabEvent],
    *,
    tempo_bpm: float,
    beats_per_measure: int = 4,
) -> list[list[int]]:
    """Original-list index lists for events that share a beam (time-ordered).

    Songsterr pattern: consecutive same-subdivision ≤8th notes within one beat.
    ``beats_per_measure`` is reserved for measure-aware beaming; unused in v1.
    """
    del beats_per_measure  # reserved
    if len(events) < 2:
        return []

    sec_per_beat = _sec_per_quarter(tempo_bpm)
    ordered = sorted(enumerate(events), key=lambda item: item[1].start)
    values = {
        idx: snap_duration(_event_duration_sec(ev), tempo_bpm=tempo_bpm) for idx, ev in ordered
    }

    groups: list[list[int]] = []
    run_start = 0
    while run_start < len(ordered):
        start_idx, start_ev = ordered[run_start]
        start_val = values[start_idx]
        if start_val.flags < 1:
            run_start += 1
            continue
        beat_bucket = int(start_ev.start / sec_per_beat) if sec_per_beat > 0 else 0
        run_end = run_start
        for cursor in range(run_start + 1, len(ordered)):
            idx, ev = ordered[cursor]
            val = values[idx]
            if val.flags < 1 or val.type_name != start_val.type_name:
                break
            if int(ev.start / sec_per_beat) != beat_bucket:
                break
            run_end = cursor
        if run_end > run_start:
            groups.append([ordered[i][0] for i in range(run_start, run_end + 1)])
            run_start = run_end + 1
        else:
            run_start += 1
    return groups
