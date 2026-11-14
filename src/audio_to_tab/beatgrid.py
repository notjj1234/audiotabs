"""Beat, downbeat, meter, and anacrusis estimation."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MIN_BEAT_MODEL_BPM = 40.0
MAX_BEAT_MODEL_BPM = 240.0


@dataclass(frozen=True)
class BeatGrid:
    bpm: float
    beats: tuple[float, ...]
    downbeats: tuple[float, ...]
    beats_per_measure: int = 4
    anacrusis_sec: float = 0.0


def beat_grid_from_events(
    *,
    beats: Iterable[float],
    downbeats: Iterable[float],
) -> BeatGrid | None:
    beat_times = np.unique(np.asarray(list(beats), dtype=float))
    beat_times = beat_times[np.isfinite(beat_times)]
    if len(beat_times) < 2:
        return None

    intervals = np.diff(beat_times)
    intervals = intervals[intervals > 0]
    if not len(intervals):
        return None
    beat_interval = float(np.median(intervals))
    bpm = float(np.clip(60.0 / beat_interval, MIN_BEAT_MODEL_BPM, MAX_BEAT_MODEL_BPM))

    downbeat_times = np.unique(np.asarray(list(downbeats), dtype=float))
    downbeat_times = downbeat_times[np.isfinite(downbeat_times)]
    downbeat_indices: list[int] = []
    tolerance = max(0.08, beat_interval * 0.25)
    for downbeat in downbeat_times:
        index = int(np.argmin(np.abs(beat_times - downbeat)))
        if abs(float(beat_times[index] - downbeat)) <= tolerance:
            downbeat_indices.append(index)
    downbeat_indices = sorted(set(downbeat_indices))

    beats_per_measure = 4
    if len(downbeat_indices) >= 2:
        spacing = float(np.median(np.diff(downbeat_indices)))
        if round(spacing) == 3:
            beats_per_measure = 3

    anacrusis_sec = float(downbeat_times[0]) if len(downbeat_times) else 0.0
    if anacrusis_sec < tolerance or (downbeat_indices and downbeat_indices[0] == 0):
        anacrusis_sec = 0.0

    return BeatGrid(
        bpm=bpm,
        beats=tuple(float(value) for value in beat_times),
        downbeats=tuple(float(value) for value in downbeat_times),
        beats_per_measure=beats_per_measure,
        anacrusis_sec=anacrusis_sec,
    )


def estimate_beat_grid(
    audio_path: str | Path,
    *,
    model: str = "beat_this",
    device: str = "cpu",
) -> BeatGrid | None:
    path = Path(audio_path)
    if model != "beat_this" or not path.is_file():
        return None
    try:
        from beat_this.inference import File2Beats

        tracker = File2Beats(checkpoint_path="final0", device=device, dbn=False)
        beats, downbeats = tracker(str(path))
        return beat_grid_from_events(beats=beats, downbeats=downbeats)
    except Exception as exc:
        logger.debug("Beat This estimation failed: %s", exc)
        return None
