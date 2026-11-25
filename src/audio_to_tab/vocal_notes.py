"""Monophonic vocal melody → notes (librosa pyin), for the Vocals notation part.

Shared with vocal de-bleed: ``vocal_pitch_track`` is computed once per stem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

PYIN_SR = 22050
PYIN_FMIN = 65.0
PYIN_FMAX = 1100.0
PYIN_FRAME = 2048
PYIN_HOP = 256
VOICED_PROB_MIN = 0.5
MEDIAN_FRAMES = 5
SILENCE_RMS = 1e-4


@dataclass
class Note:
    pitch: int
    start: float
    end: float
    velocity: int


@dataclass
class VocalPitchTrack:
    """Frame-wise f0 (Hz, NaN when unvoiced) and voicing probability."""

    times: np.ndarray
    f0: np.ndarray
    voiced_prob: np.ndarray
    rms: np.ndarray
    hop_sec: float

    def midi(self) -> np.ndarray:
        import librosa

        out = np.full(self.f0.shape, np.nan)
        ok = np.isfinite(self.f0) & (self.voiced_prob >= VOICED_PROB_MIN)
        out[ok] = librosa.hz_to_midi(self.f0[ok])
        return out


_CACHE: dict[tuple[int, str], VocalPitchTrack] = {}
_CACHE_MAX = 4


def clear_cache() -> None:
    _CACHE.clear()


def content_key(path: str | Path) -> tuple[int, str]:
    """(size, sha1) of a file, so copies of the same stem share one analysis."""
    import hashlib

    p = Path(path)
    digest = hashlib.sha1()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return p.stat().st_size, digest.hexdigest()


def vocal_pitch_track(path: str | Path) -> VocalPitchTrack:
    """pyin on a vocals stem, computed once per audio content (shared by de-bleed and notes)."""
    key = content_key(path)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    track = _compute_pitch_track(path)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = track
    return track


def _compute_pitch_track(path: str | Path) -> VocalPitchTrack:
    import librosa

    y, sr = librosa.load(str(path), sr=PYIN_SR, mono=True)
    hop_sec = PYIN_HOP / sr
    if y.size == 0 or float(np.sqrt(np.mean(y**2))) < SILENCE_RMS:
        n = max(1, int(np.ceil(y.size / PYIN_HOP)))
        empty = np.zeros(n)
        return VocalPitchTrack(
            times=np.arange(n) * hop_sec,
            f0=np.full(n, np.nan),
            voiced_prob=empty,
            rms=empty,
            hop_sec=hop_sec,
        )
    f0, _voiced, prob = librosa.pyin(
        y,
        sr=sr,
        fmin=PYIN_FMIN,
        fmax=PYIN_FMAX,
        frame_length=PYIN_FRAME,
        hop_length=PYIN_HOP,
    )
    rms = librosa.feature.rms(y=y, frame_length=PYIN_FRAME, hop_length=PYIN_HOP)[0]
    n = min(len(f0), len(rms))
    return VocalPitchTrack(
        times=np.arange(n) * hop_sec,
        f0=np.asarray(f0[:n], dtype=float),
        voiced_prob=np.nan_to_num(np.asarray(prob[:n], dtype=float)),
        rms=np.asarray(rms[:n], dtype=float),
        hop_sec=hop_sec,
    )


def notes_from_track(
    track: VocalPitchTrack, *, min_dur: float = 0.10, merge_gap: float = 0.05
) -> list[Note]:
    from scipy.ndimage import median_filter

    midi = track.midi()
    if not np.any(np.isfinite(midi)):
        return []
    rounded = np.where(np.isfinite(midi), np.round(midi), -1.0)
    smoothed = median_filter(rounded, size=MEDIAN_FRAMES, mode="nearest")
    segments: list[list[float]] = []  # [pitch, start_frame, end_frame]
    current = None
    for i, value in enumerate(smoothed):
        if value < 0:
            current = None
            continue
        if current is not None and current[0] == value and current[2] == i:
            current[2] = i + 1
        else:
            current = [value, i, i + 1]
            segments.append(current)
    hop = track.hop_sec
    merged: list[list[float]] = []
    for seg in segments:
        if merged and merged[-1][0] == seg[0] and (seg[1] - merged[-1][2]) * hop <= merge_gap:
            merged[-1][2] = seg[2]
        else:
            merged.append(list(seg))
    peak = float(np.max(track.rms)) if track.rms.size else 0.0
    notes: list[Note] = []
    for pitch, a, b in merged:
        start, end = a * hop, b * hop
        if end - start < min_dur:
            continue
        level = float(np.mean(track.rms[int(a) : int(b)])) if peak > 0 else 0.0
        velocity = int(np.clip(40 + 80 * (level / peak if peak > 0 else 0), 1, 127))
        notes.append(Note(pitch=int(pitch), start=round(start, 4), end=round(end, 4), velocity=velocity))
    return notes


def pyin_notes(path: str | Path, *, min_dur: float = 0.10, merge_gap: float = 0.05) -> list[Note]:
    return notes_from_track(vocal_pitch_track(path), min_dur=min_dur, merge_gap=merge_gap)
