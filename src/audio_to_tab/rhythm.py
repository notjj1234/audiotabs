"""Beat-grid quantization for tab events."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Iterable
from itertools import pairwise

from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote


def sec_per_sixteenth(tempo_bpm: float, beats_per_measure: int = 4) -> float:
    """Duration of one 16th note in seconds."""
    return 60.0 / tempo_bpm / 4.0


def quantize_time(t: float, grid_sec: float) -> float:
    if grid_sec <= 0:
        return t
    return round(t / grid_sec) * grid_sec


def _clean_beat_times(beats: Iterable[float] | None) -> tuple[float, ...]:
    if beats is None:
        return ()
    values = sorted({float(beat) for beat in beats if math.isfinite(float(beat))})
    if len(values) < 2 or any(b <= a for a, b in pairwise(values)):
        return ()
    return tuple(values)


def _beat_grid_step(t: float, beats: tuple[float, ...], subdivisions: int) -> float:
    index = max(0, min(bisect_right(beats, t) - 1, len(beats) - 2))
    return (beats[index + 1] - beats[index]) / subdivisions


def _quantize_beat_time(t: float, beats: tuple[float, ...], subdivisions: int) -> float:
    index = max(0, min(bisect_right(beats, t) - 1, len(beats) - 2))
    step = (beats[index + 1] - beats[index]) / subdivisions
    return beats[index] + round((t - beats[index]) / step) * step


def quantize_tab_document(
    doc: TabDocument,
    *,
    beats_per_measure: int = 4,
    subdivisions_per_beat: int = 4,
    beats: Iterable[float] | None = None,
) -> TabDocument:
    """Snap note timing to detected beats, or a constant-tempo 16th-note grid."""
    beat_times = _clean_beat_times(beats)
    grid_sec = 60.0 / doc.tempo_bpm / subdivisions_per_beat

    new_events: list[TabEvent] = []
    for event in doc.events:
        if beat_times:
            q_start = max(
                0.0,
                _quantize_beat_time(event.start, beat_times, subdivisions_per_beat),
            )
            min_duration = _beat_grid_step(q_start, beat_times, subdivisions_per_beat)
        else:
            q_start = quantize_time(event.start, grid_sec)
            min_duration = grid_sec
        new_notes: list[TabNote] = []
        for note in event.notes:
            if beat_times:
                q_end = _quantize_beat_time(note.end, beat_times, subdivisions_per_beat)
            else:
                q_end = quantize_time(note.end, grid_sec)
            q_end = max(q_start + min_duration, q_end)
            new_notes.append(
                TabNote(
                    start=q_start,
                    end=q_end,
                    string=note.string,
                    fret=note.fret,
                    pitch=note.pitch,
                )
            )
        new_events.append(TabEvent(start=q_start, notes=new_notes))

    return TabDocument(
        events=new_events,
        tuning_names=doc.tuning_names,
        tempo_bpm=doc.tempo_bpm,
        tempo_confidence=doc.tempo_confidence,
        beats_per_measure=beats_per_measure,
    )
