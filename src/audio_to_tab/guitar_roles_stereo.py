"""Stereo pre-split of a guitar stem into a centre (lead candidate) and sides (rhythm candidate).

A common band-mix convention puts the lead guitar near the centre and double-tracked rhythm
guitars to the sides. Per STFT bin, the pan index ``p = (|R| - |L|) / (|R| + |L|)`` says where
that bin's energy sits; soft masks split the stem into a centre and a side part. This is a
*candidate* split, not a separator: a mix that doesn't follow the convention gives a
meaningless split, so callers use it as one piece of evidence among others.

Near-mono stems (global L/R correlation above ``mono_corr``) carry no pan information and
are passed through untouched; the decision is logged and returned.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

EPS = 1e-9
STEREO_PRESPLIT_ENV = "ATT_STEREO_PRESPLIT"


@dataclass(frozen=True)
class StereoSplitConfig:
    n_fft: int = 4096
    hop: int = 1024
    centre_full: float = 0.2  # |p| up to here is fully centre
    centre_zero: float = 0.6  # centre weight has fallen to 0 by here
    mono_corr: float = 0.95  # global L/R correlation above this = near-mono, pass through
    # Pan alone files two equally loud, hard-panned, independent guitars as centre (|L| ≈ |R|
    # in the bins they share, so p ≈ 0) — exactly the double-tracked rhythm case. A real
    # centre source is also phase-coherent between channels, so the centre weight is
    # multiplied by a short-time inter-channel coherence weight (cf. Avendano & Jot, 2004).
    use_coherence: bool = True
    coherence_frames: int = 8  # time smoothing of the cross-spectrum, in STFT frames
    coherence_low: float = 0.5  # coherence at or below this counts as fully decorrelated
    coherence_high: float = 0.9  # coherence at or above this counts as fully coherent


DEFAULT_CONFIG = StereoSplitConfig()


@dataclass
class StereoSplitResult:
    skipped: bool
    reason: str
    lr_correlation: float
    centre_energy_share: float | None = None  # centre-mask energy / total stem energy
    lead_candidate: Path | None = None
    rhythm_candidate: Path | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        for key in ("lead_candidate", "rhythm_candidate"):
            d[key] = None if d[key] is None else str(d[key])
        return d


def lr_correlation(stereo: np.ndarray) -> float:
    """Pearson correlation of the left and right channels (1.0 for silent or mono input)."""
    left, right = stereo[:, 0].astype(np.float64), stereo[:, 1].astype(np.float64)
    if left.std() == 0 or right.std() == 0:
        return 1.0
    return float(np.corrcoef(left, right)[0, 1])


def pan_index(mag_left: np.ndarray, mag_right: np.ndarray) -> np.ndarray:
    """-1 = hard left, 0 = centre, +1 = hard right, per bin."""
    return (mag_right - mag_left) / (mag_right + mag_left + EPS)


def centre_weight(pan: np.ndarray, cfg: StereoSplitConfig = DEFAULT_CONFIG) -> np.ndarray:
    """1 for |p| <= centre_full, falling linearly to 0 at |p| = centre_zero."""
    span = max(cfg.centre_zero - cfg.centre_full, EPS)
    return np.clip((cfg.centre_zero - np.abs(pan)) / span, 0.0, 1.0)


def coherence(spec_left: np.ndarray, spec_right: np.ndarray, frames: int) -> np.ndarray:
    """Per-bin |E[L R*]| / sqrt(E|L|^2 E|R|^2), expectations smoothed over ``frames`` frames."""
    from scipy.ndimage import uniform_filter1d

    def smooth(x: np.ndarray) -> np.ndarray:
        return uniform_filter1d(x, size=max(1, frames), axis=1, mode="nearest")

    cross = spec_left * np.conj(spec_right)
    num = np.abs(smooth(cross.real) + 1j * smooth(cross.imag))
    den = np.sqrt(smooth(np.abs(spec_left) ** 2) * smooth(np.abs(spec_right) ** 2))
    return num / (den + EPS)


def centre_mask(
    spec_left: np.ndarray, spec_right: np.ndarray, cfg: StereoSplitConfig = DEFAULT_CONFIG
) -> np.ndarray:
    weight = centre_weight(pan_index(np.abs(spec_left), np.abs(spec_right)), cfg)
    if cfg.use_coherence:
        span = max(cfg.coherence_high - cfg.coherence_low, EPS)
        coh = coherence(spec_left, spec_right, cfg.coherence_frames)
        weight = weight * np.clip((coh - cfg.coherence_low) / span, 0.0, 1.0)
    return weight


def split_centre_side(
    stereo: np.ndarray, cfg: StereoSplitConfig = DEFAULT_CONFIG
) -> tuple[np.ndarray, np.ndarray]:
    """Soft-mask ``stereo`` (samples x 2) into (centre, side), each samples x 2; they sum to the input."""
    import librosa

    n = stereo.shape[0]
    specs = [
        librosa.stft(stereo[:, ch].astype(np.float32), n_fft=cfg.n_fft, hop_length=cfg.hop)
        for ch in (0, 1)
    ]
    weight = centre_mask(specs[0], specs[1], cfg)
    centre = np.stack(
        [librosa.istft(s * weight, hop_length=cfg.hop, length=n) for s in specs], axis=1
    )
    side = np.stack(
        [librosa.istft(s * (1.0 - weight), hop_length=cfg.hop, length=n) for s in specs], axis=1
    )
    return centre.astype(np.float32), side.astype(np.float32)


def stereo_presplit_enabled() -> bool:
    """Opt-in (``ATT_STEREO_PRESPLIT=1``): the Lead/Rhythm splitter gets the centre candidate."""
    return os.environ.get(STEREO_PRESPLIT_ENV, "").strip().lower() in {"1", "true", "on", "yes"}


def presplit_array(
    stereo: np.ndarray, cfg: StereoSplitConfig = DEFAULT_CONFIG
) -> tuple[np.ndarray | None, np.ndarray | None, StereoSplitResult]:
    """(centre, side, result) for ``stereo`` (samples x 2); centre/side are None when skipped."""
    if stereo.ndim != 2 or stereo.shape[1] < 2:
        return None, None, StereoSplitResult(skipped=True, reason="mono file", lr_correlation=1.0)
    stereo = stereo[:, :2]
    corr = lr_correlation(stereo)
    if corr > cfg.mono_corr:
        reason = f"near-mono (L/R correlation {corr:.3f} > {cfg.mono_corr})"
        return None, None, StereoSplitResult(skipped=True, reason=reason, lr_correlation=round(corr, 4))
    centre, side = split_centre_side(stereo, cfg)
    total = float(np.sum(stereo.astype(np.float64) ** 2))
    share = float(np.sum(centre.astype(np.float64) ** 2)) / total if total > 0 else None
    result = StereoSplitResult(
        skipped=False,
        reason="split",
        lr_correlation=round(corr, 4),
        centre_energy_share=None if share is None else round(share, 4),
    )
    return centre, side, result


def stereo_presplit(
    guitar_wav: Path, out_dir: Path, cfg: StereoSplitConfig = DEFAULT_CONFIG
) -> StereoSplitResult:
    """Write ``lead_candidate.wav`` (centre) and ``rhythm_candidate.wav`` (sides) unless near-mono."""
    import soundfile as sf

    data, sr = sf.read(str(guitar_wav), always_2d=True)
    centre, side, result = presplit_array(data, cfg)
    if centre is None or side is None:
        logger.info("Stereo pre-split skipped for %s: %s", guitar_wav, result.reason)
        return result
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result.lead_candidate = out_dir / "lead_candidate.wav"
    result.rhythm_candidate = out_dir / "rhythm_candidate.wav"
    sf.write(str(result.lead_candidate), centre, sr)
    sf.write(str(result.rhythm_candidate), side, sr)
    logger.info(
        "Stereo pre-split of %s: L/R correlation %.3f, centre share %.2f",
        guitar_wav, result.lr_correlation, result.centre_energy_share or 0.0,
    )
    return result
