"""Rough drum hits from a drums stem: kick, snare, hi-hat only.

Heuristic (no model, no new dependency): rise of linear band energy in
three bands, each band normalised and peak-picked on its own. A hi-hat peak
that coincides with a snare peak is dropped (snares are broadband). Labelled
"rough" in the UI; toms and cymbal types are not detected.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

Piece = Literal["kick", "snare", "hihat"]

DRUM_SR = 22050
N_FFT = 1024
HOP = 128
BANDS: dict[str, tuple[float, float]] = {
    "kick": (20.0, 150.0),
    "snare": (150.0, 2500.0),
    "hihat": (6000.0, 11000.0),
}
PEAK_DELTA = 0.15
MIN_GAP_SEC = 0.06
COINCIDE_SEC = 0.03
SILENCE_RMS = 1e-4
GM_NOTES: dict[str, int] = {"kick": 36, "snare": 38, "hihat": 42}


@dataclass
class DrumHit:
    start: float
    piece: Piece
    velocity: int


def _band_flux(mag: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Positive rise of linear band energy; linear keeps leakage from other bands small."""
    rows = (freqs >= lo) & (freqs < hi)
    energy = np.sum(mag[rows] ** 2, axis=0)
    return np.maximum(0.0, np.diff(energy, prepend=energy[:1]))


def transcribe_drums(path: str | Path) -> list[DrumHit]:
    import librosa

    y, sr = librosa.load(str(path), sr=DRUM_SR, mono=True)
    if y.size == 0 or float(np.sqrt(np.mean(y**2))) < SILENCE_RMS:
        return []
    mag = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    wait = max(1, int(MIN_GAP_SEC * sr / HOP))

    peaks: dict[str, list[tuple[float, float]]] = {}
    for piece, (lo, hi) in BANDS.items():
        flux = _band_flux(mag, freqs, lo, min(hi, sr / 2))
        top = float(np.percentile(flux, 99.5)) if flux.size else 0.0
        if top <= 1e-9:
            peaks[piece] = []
            continue
        norm = np.clip(flux / top, 0.0, 1.5)
        idx = librosa.util.peak_pick(
            norm, pre_max=3, post_max=3, pre_avg=12, post_avg=12, delta=PEAK_DELTA, wait=wait
        )
        peaks[piece] = [
            (float(librosa.frames_to_time(i, sr=sr, hop_length=HOP)), float(norm[i]))
            for i in idx
            if norm[i] >= 0.25
        ]

    snare_times = [t for t, _ in peaks.get("snare", [])]
    hits: list[DrumHit] = []
    for piece, found in peaks.items():
        for t, strength in found:
            if piece == "hihat" and any(abs(t - s) <= COINCIDE_SEC for s in snare_times):
                continue
            velocity = int(np.clip(40 + 80 * min(1.0, strength), 1, 127))
            hits.append(DrumHit(start=round(t, 4), piece=piece, velocity=velocity))  # type: ignore[arg-type]
    hits.sort(key=lambda h: (h.start, h.piece))
    return hits
