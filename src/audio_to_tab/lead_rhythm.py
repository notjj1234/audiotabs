"""Lead vs Rhythm guitar post-process for Demucs guitar stems.

Spatial + register (STFT band) candidates, then Basic Pitch role features with a
confidence gate. HPSS spectral pairs are kept for diagnostics only and never
emitted as Lead/Rhythm. Emits lead_guitar / rhythm_guitar only when confident;
always keeps the original guitar stem when attempted.

Root cause (2026-07-17): most real two-guitar mixes are not hard-panned to
opposite channels (that is a stylistic choice, not the norm), yet
``build_spatial_pair``'s admission gate was a single raw L/R sample-correlation
ceiling (``SPATIAL_CORR_MAX``). Raw correlation of a stereo mix of two
*independent* sources panned with coefficients (p, 1-p) is ``2p(1-p) /
(p^2 + (1-p)^2)`` — it rises toward 1.0 as panning approaches center
*regardless of how different the underlying content is* (e.g. two fully
independent tones panned 55/45 already correlate ~0.98). So the old gate
conflated "one guitar duplicated identically into both channels" (corr -> 1.0,
truly inseparable) with "two genuinely distinct guitars mixed with mild/no hard
panning" (corr can also land at 0.92-0.99, but the channels are NOT identical).
Everything short of hard panning was rejected before role classification ever
ran, matching the eval README's documented ambiguous cases.

Published solo/accompaniment guitar research (Foulon et al. 2013, "Automatic
Classification of Guitar Playing Modes"; Pati & Lerch 2017, "A Dataset and
Method for Electric Guitar Solo Detection in Rock Music") shows that
predominant-pitch strength/confidence, computed directly on a signal, reliably
discriminates a foregrounded melodic (lead) voice from denser/chordal
(rhythm) material *without first splitting the audio into two streams* via
panning or spectral means. That evidence is independent of how the mix is
panned, so it can rescue exactly the high-correlation-but-genuinely-distinct
case above: ``build_spatial_pair`` now allows a higher correlation ceiling
(``SPATIAL_CORR_RELAXED_MAX``) only when each channel's dominant spectral peak
("predominant pitch" proxy; no split required) diverges by at least
``PITCH_DIVERGENCE_SEMITONES_MIN`` semitones and at least one channel has a
clear-enough peak (``PITCH_CONFIDENCE_MIN``). Identical/near-identical channels
(mono duplicated into both) always show zero divergence, so they remain
rejected — the existing "prefer ambiguous over wrong" guarantee is unchanged:
this only widens *evidence* for admitting a candidate pair, the separability
floor and role-margin gates downstream still decide whether to actually emit.
No new dependency was added: the peak-picking helper is plain FFT (same style
as ``score_candidate_pair`` / ``_spectral_centroid_hz`` already in this file).
True same-register, fully-simultaneous, dead-centered (identical L=R) overlap
of two guitars remains architecturally unsolvable without a trained source
separator — that case correctly stays ``ambiguous`` (out of scope here; adding
such a model was explicitly excluded).

Role evidence (2026-11 audit against the lead/rhythm role spec): role is recovered
from texture first (notes per attack, F2 pitch-class change per attack, F5
competing salience peaks), then contour, with register/sustain/model-confidence
capped at 10% of the score (``ROLE_WEIGHTS``). Features are always measured on
the two candidate streams, never on the raw channels of the unsplit stem. A tied
score, or streams that differ only in register/timbre (``texture_margin`` below
the role floor), are refused as ``ambiguous`` with no WAVs, in every emit mode.
Every threshold is listed in ``CONSTANT_PROVENANCE`` (all UNCALIBRATED until
fitted on labelled segments) and written into the diagnostics. Not done yet:
segment-level scoring (8-bar windows with hysteresis); features still come from
the first and last ``ANALYZE_WINDOW_SEC`` of the stem.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, replace
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

import numpy as np
import soundfile as sf

Outcome = Literal["lead_rhythm", "ambiguous", "skipped"]
Method = Literal["spatial", "midside", "register", "spectral", "none"]
EmitMode = Literal["confident", "best_effort"]


def resolve_lead_rhythm_mode(
    lead_rhythm_mode: str | None = None,
    *,
    lead_rhythm: bool = False,
) -> EmitMode:
    """Map API/UI flags to emit policy. Default is confident-only emit."""
    if lead_rhythm_mode is not None and str(lead_rhythm_mode).strip():
        mode = str(lead_rhythm_mode).strip().lower()
        if mode not in ("confident", "best_effort"):
            raise ValueError(
                f"lead_rhythm_mode must be 'confident' or 'best_effort', got {lead_rhythm_mode!r}"
            )
        return mode  # type: ignore[return-value]
    if lead_rhythm:
        return "best_effort"
    return "confident"

SEPARABILITY_FLOOR = 0.22
ROLE_MARGIN_MIN = 0.18
# HPSS harmonic/residual is not musically Lead/Rhythm; spectral pairs are
# diagnostics-only (never emitted) unless allow_spectral_emit is explicitly on.
SPECTRAL_SEPARABILITY_FLOOR = 0.55
SPECTRAL_ROLE_MARGIN_MIN = 0.28
REGISTER_SEPARABILITY_FLOOR = 0.28
MIDSIDE_SEPARABILITY_FLOOR = 0.22
ANALYZE_WINDOW_SEC = 90.0
SPATIAL_BALANCE_MIN = 0.12
SPATIAL_CORR_MAX = 0.92
REGISTER_CROSSOVER_HZ = 400.0
# Side channel must carry some energy vs Mid (rejects true mono / L≡R).
MIDSIDE_SIDE_RATIO_MIN = 0.04

# Pitch-divergence evidence (spatial-split-independent) that can rescue a
# mildly-panned-but-genuinely-distinct pair above SPATIAL_CORR_MAX — see the
# module docstring "Root cause" note. Never overrides SPATIAL_CORR_RELAXED_MAX,
# so identical/near-identical channels (mono duplicated) are still rejected.
SPATIAL_CORR_RELAXED_MAX = 0.985
PITCH_DIVERGENCE_SEMITONES_MIN = 3.0
PITCH_CONFIDENCE_MIN = 0.35
PITCH_PROXY_FMIN_HZ = 70.0
PITCH_PROXY_FMAX_HZ = 1500.0

# --- Texture features F2 / F5 (see docs/lead-rhythm-spec in the request brief) ---
# Notes starting within this window are one attack (strum / chord).
ONSET_GROUP_SEC = 0.05
# F5 salience: harmonics summed per candidate f0, and their weights (h=1..5).
SALIENCE_HARMONICS = 5
SALIENCE_HARMONIC_DECAY = 0.8
# A competing salience peak counts when it is within this many dB of the frame max.
SALIENCE_PEAK_DB = 10.0
# Salience frame length (seconds; rounded up to a power-of-two FFT).
SALIENCE_FRAME_SEC = 0.046
# Spectrum interpolation factor and how far apart two salience peaks must be.
SALIENCE_ZERO_PAD = 4
SALIENCE_PEAK_SPAN_SEMIS = 2.0
# Frames quieter than this (dB below the loudest frame) are not scored.
SALIENCE_FRAME_FLOOR_DB = 40.0
# Stems shorter or quieter than this are skipped, not classified.
MIN_ANALYSIS_SEC = 1.0
SILENT_RMS = 1e-4

# Provenance of every threshold/weight in this module (ground rule: no invented
# thresholds). None of them has been fitted to labelled data yet, so all are
# UNCALIBRATED and are written into the diagnostics so they can be tuned later.
CONSTANT_PROVENANCE: dict[str, str] = {
    "SEPARABILITY_FLOOR": "UNCALIBRATED: hand-set guess",
    "ROLE_MARGIN_MIN": "UNCALIBRATED: hand-set guess",
    "SPECTRAL_SEPARABILITY_FLOOR": "UNCALIBRATED: hand-set guess",
    "SPECTRAL_ROLE_MARGIN_MIN": "UNCALIBRATED: hand-set guess",
    "REGISTER_SEPARABILITY_FLOOR": "UNCALIBRATED: hand-set guess",
    "MIDSIDE_SEPARABILITY_FLOOR": "UNCALIBRATED: hand-set guess",
    "SPATIAL_BALANCE_MIN": "UNCALIBRATED: hand-set guess",
    "SPATIAL_CORR_MAX": "UNCALIBRATED: hand-set guess",
    "SPATIAL_CORR_RELAXED_MAX": "UNCALIBRATED: hand-set guess",
    "REGISTER_CROSSOVER_HZ": "UNCALIBRATED: hand-set guess",
    "MIDSIDE_SIDE_RATIO_MIN": "UNCALIBRATED: hand-set guess",
    "PITCH_DIVERGENCE_SEMITONES_MIN": "UNCALIBRATED: hand-set guess",
    "PITCH_CONFIDENCE_MIN": "UNCALIBRATED: share of voiced frames with one dominant salience peak",
    "PITCH_PROXY_FMIN_HZ": "CALIBRATED: F5 band 70-1500 Hz from the role spec (Salamon & Gomez style)",
    "PITCH_PROXY_FMAX_HZ": "CALIBRATED: F5 band 70-1500 Hz from the role spec",
    "ONSET_GROUP_SEC": "UNCALIBRATED: hand-set guess",
    "SALIENCE_HARMONICS": "CALIBRATED: f0..5f0 from the role spec (F5)",
    "SALIENCE_HARMONIC_DECAY": "UNCALIBRATED: hand-set guess",
    "SALIENCE_PEAK_DB": "CALIBRATED: 10 dB from the role spec (F5)",
    "SALIENCE_FRAME_FLOOR_DB": "UNCALIBRATED: hand-set guess",
    "SALIENCE_FRAME_SEC": "UNCALIBRATED: hand-set guess (shorter than a 16th note at 160 BPM)",
    "SALIENCE_ZERO_PAD": "UNCALIBRATED: chosen on synthetic tones only",
    "SALIENCE_PEAK_SPAN_SEMIS": "UNCALIBRATED: chosen on synthetic tones only",
    "MIN_ANALYSIS_SEC": "UNCALIBRATED: hand-set guess",
    "SILENT_RMS": "UNCALIBRATED: hand-set guess",
    "ROLE_WEIGHTS": "UNCALIBRATED: rubric weights ordered by evidence tier, not fitted",
    "NORMALISERS": "UNCALIBRATED: feature ranges from the spec's [cal] guesses",
}


@dataclass
class LeadRhythmThresholds:
    """Tunable gates for eval/CLI ablation (defaults match module constants)."""

    separability_floor: float = SEPARABILITY_FLOOR
    role_margin_min: float = ROLE_MARGIN_MIN
    spectral_separability_floor: float = SPECTRAL_SEPARABILITY_FLOOR
    spectral_role_margin_min: float = SPECTRAL_ROLE_MARGIN_MIN
    register_separability_floor: float = REGISTER_SEPARABILITY_FLOOR
    midside_separability_floor: float = MIDSIDE_SEPARABILITY_FLOOR
    midside_side_ratio_min: float = MIDSIDE_SIDE_RATIO_MIN
    analyze_window_sec: float = ANALYZE_WINDOW_SEC
    # Spectral emit quarantined by default (HPSS ≠ Lead/Rhythm).
    allow_spectral_emit: bool = False
    spatial_balance_min: float = SPATIAL_BALANCE_MIN
    spatial_corr_max: float = SPATIAL_CORR_MAX
    spatial_corr_relaxed_max: float = SPATIAL_CORR_RELAXED_MAX
    pitch_divergence_semitones_min: float = PITCH_DIVERGENCE_SEMITONES_MIN
    pitch_confidence_min: float = PITCH_CONFIDENCE_MIN

    @classmethod
    def from_env(cls, base: LeadRhythmThresholds | None = None) -> LeadRhythmThresholds:
        """Overlay ATT_LR_* environment variables onto defaults or ``base``."""
        t = base or cls()
        mapping = {
            "ATT_LR_SEPARABILITY_FLOOR": ("separability_floor", float),
            "ATT_LR_ROLE_MARGIN_MIN": ("role_margin_min", float),
            "ATT_LR_SPECTRAL_SEPARABILITY_FLOOR": ("spectral_separability_floor", float),
            "ATT_LR_SPECTRAL_ROLE_MARGIN_MIN": ("spectral_role_margin_min", float),
            "ATT_LR_REGISTER_SEPARABILITY_FLOOR": ("register_separability_floor", float),
            "ATT_LR_MIDSIDE_SEPARABILITY_FLOOR": ("midside_separability_floor", float),
            "ATT_LR_MIDSIDE_SIDE_RATIO_MIN": ("midside_side_ratio_min", float),
            "ATT_LR_ANALYZE_WINDOW_SEC": ("analyze_window_sec", float),
            "ATT_LR_ALLOW_SPECTRAL_EMIT": ("allow_spectral_emit", _env_bool),
            "ATT_LR_SPATIAL_CORR_RELAXED_MAX": ("spatial_corr_relaxed_max", float),
            "ATT_LR_PITCH_DIVERGENCE_SEMITONES_MIN": (
                "pitch_divergence_semitones_min",
                float,
            ),
            "ATT_LR_PITCH_CONFIDENCE_MIN": ("pitch_confidence_min", float),
        }
        updates: dict[str, Any] = {}
        for env_key, (field_name, caster) in mapping.items():
            raw = os.environ.get(env_key)
            if raw is None or raw == "":
                continue
            updates[field_name] = caster(raw)
        return replace(t, **updates) if updates else t


def _env_bool(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class LeadRhythmDiagnostics:
    """Diagnostics for an attempted lead/rhythm split."""

    outcome: Outcome
    reason: str
    attempted: bool = True
    separability_score: float | None = None
    role_confidence: float | None = None
    method: Method = "none"
    correlation: float | None = None
    balance_ratio: float | None = None
    # True when Lead/Rhythm WAVs were written despite failed gates (best-effort).
    forced_emit: bool = False
    low_confidence: bool = False
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path


@dataclass
class _CandidatePair:
    method: Method
    a: np.ndarray  # mono float32
    b: np.ndarray
    sr: int
    separability: float
    correlation: float | None = None
    balance_ratio: float | None = None
    detail: str = ""
    pitch_evidence: dict[str, float] | None = None


def _load_stereo(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    return data.astype(np.float32), int(sr)


def _mono_to_stereo(mono: np.ndarray) -> np.ndarray:
    m = np.asarray(mono, dtype=np.float32).reshape(-1)
    return np.column_stack([m, m])


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)) + 1e-12))


@dataclass(frozen=True)
class SalienceStats:
    """F5 per-frame harmonic-summation salience, summarised over frames."""

    concentration: float  # median of max/sum of the salience curve per frame
    peak_count: float  # median count of non-octave peaks within SALIENCE_PEAK_DB of the max
    predominant_hz: float  # median f0 of frames with one dominant peak (0 if none)
    single_peak_share: float  # share of scored frames with exactly one dominant peak
    frames: int


def salience_stats(mono: np.ndarray, sr: int, *, max_sec: float = 60.0) -> SalienceStats:
    """
    F5 ``salience_concentration``: per frame, harmonic summation over f0..5f0 for
    candidate f0 across 70-1500 Hz (Salamon & Gomez, IEEE TASLP 2012 style), then
    ``max / sum`` and the number of comparable peaks. A single foregrounded line
    gives one dominant peak; a chord gives several. Octave-related candidates of
    the winning f0 (its sub-harmonics share its partials) are not counted as
    competitors. Plain numpy FFT, no new dependency.
    """
    x = np.asarray(mono, dtype=np.float32).reshape(-1)[: int(max_sec * sr)]
    # ~46 ms frames so one frame rarely spans two notes of a fast line.
    n_fft = 1 << int(np.ceil(np.log2(max(256, SALIENCE_FRAME_SEC * sr))))
    hop = n_fft // 4
    if len(x) < n_fft or sr <= 0:
        return SalienceStats(0.0, 0.0, 0.0, 0.0, 0)
    window = np.hanning(n_fft).astype(np.float32)
    starts = range(0, len(x) - n_fft + 1, hop)
    frames = np.stack([x[s : s + n_fft] * window for s in starts])
    # Zero-padding interpolates the spectrum so low notes (bins wider than a
    # semitone) don't break into false salience peaks.
    padded = n_fft * SALIENCE_ZERO_PAD
    mag = np.abs(np.fft.rfft(frames, n=padded, axis=1))
    energy = np.sum(mag**2, axis=1)
    if not np.any(energy > 0):
        return SalienceStats(0.0, 0.0, 0.0, 0.0, 0)
    loud = energy >= np.max(energy) * 10 ** (-SALIENCE_FRAME_FLOOR_DB / 10)
    mag = mag[loud]

    # Candidate f0 on a half-semitone grid.
    n_cand = int(np.floor(24 * np.log2(PITCH_PROXY_FMAX_HZ / PITCH_PROXY_FMIN_HZ))) + 1
    f0 = PITCH_PROXY_FMIN_HZ * 2 ** (np.arange(n_cand) / 24.0)
    bin_hz = sr / padded
    harmonics = np.arange(1, SALIENCE_HARMONICS + 1)
    bins = np.clip(np.round(np.outer(f0, harmonics) / bin_hz).astype(int), 0, mag.shape[1] - 1)
    weights = SALIENCE_HARMONIC_DECAY ** (harmonics - 1)
    salience = np.tensordot(mag[:, bins], weights, axes=([2], [0]))  # frames x candidates

    ratio = 10 ** (-SALIENCE_PEAK_DB / 20)
    conc: list[float] = []
    counts: list[int] = []
    winners: list[float] = []
    for row in salience:
        total = float(np.sum(row))
        if total <= 0:
            continue
        top = int(np.argmax(row))
        conc.append(float(row[top] / total))
        # A peak must be the highest candidate within +/- SALIENCE_PEAK_SPAN_SEMIS.
        span = round(SALIENCE_PEAK_SPAN_SEMIS * 2)
        neighbourhood = np.lib.stride_tricks.sliding_window_view(
            np.r_[np.zeros(span), row, np.zeros(span)], 2 * span + 1
        ).max(axis=1)
        is_peak = (row >= neighbourhood) & (row > 0)
        strong = np.flatnonzero(is_peak & (row >= row[top] * ratio))
        semis = np.abs(np.arange(n_cand)[strong] - top) / 2.0
        # Skip the winner itself and its octave relatives (12, 19, 24 semitones away).
        octave_rel = np.min(np.abs(semis[:, None] - np.array([0, 12, 19, 24])[None, :]), axis=1) <= 0.5
        competitors = int(np.sum(~octave_rel)) + 1
        counts.append(competitors)
        if competitors == 1:
            winners.append(float(f0[top]))
    if not conc:
        return SalienceStats(0.0, 0.0, 0.0, 0.0, 0)
    return SalienceStats(
        concentration=float(np.median(conc)),
        peak_count=float(np.median(counts)),
        predominant_hz=float(np.median(winners)) if winners else 0.0,
        single_peak_share=float(len(winners) / len(counts)),
        frames=len(counts),
    )


def _dominant_pitch_estimate(mono: np.ndarray, sr: int) -> tuple[float, float]:
    """
    Predominant pitch + confidence for one channel, from F5 per-frame salience.

    Replaces the old single-FFT-peak proxy, whose "confidence" (peak/total
    magnitude) moved with distortion and level and called power chords
    "confident monophonic". Confidence is now the share of voiced frames with
    exactly one dominant salience peak; a chord has several comparable peaks.

    Returns (predominant_hz, confidence) or (0.0, 0.0) when it can't be estimated.
    """
    stats = salience_stats(mono, sr, max_sec=8.0)
    if stats.frames == 0 or stats.predominant_hz <= 0:
        return 0.0, 0.0
    return stats.predominant_hz, stats.single_peak_share


def _pitch_divergence_semitones(freq_a: float, freq_b: float) -> float:
    if freq_a <= 0.0 or freq_b <= 0.0:
        return 0.0
    return float(abs(12.0 * np.log2(freq_a / freq_b)))


def _harmonic_pitch_pair(
    mono: np.ndarray, sr: int, center_a_hz: float, center_b_hz: float
) -> tuple[np.ndarray, np.ndarray] | None:
    """
    Split a mono signal into two streams via soft log-frequency masks centered
    on two already-detected predominant pitches (from ``_dominant_pitch_estimate``).

    Used only for the mild-pan pitch-divergence-evidence path in
    ``build_spatial_pair``: at near-center panning the per-sample L/R dominance
    heuristic used for hard-panned content degenerates (both channels carry
    comparable amounts of both sources), but the two predominant pitches are
    still known, so a pitch-informed mask separates them far better than
    amplitude alone. Same STFT/soft-mask machinery as ``build_register_pair``,
    just centered on detected pitches instead of a fixed crossover — no new
    dependency. Returns None if librosa is unavailable.
    """
    try:
        import librosa
    except ImportError:
        return None
    if center_a_hz <= 0.0 or center_b_hz <= 0.0:
        return None
    n_fft = 2048
    hop = 512
    stft = librosa.stft(mono, n_fft=n_fft, hop_length=hop)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    def _log_gaussian_mask(center_hz: float, bandwidth_semitones: float = 5.0) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            semitones = 12.0 * np.log2(np.maximum(freqs, 1e-6) / center_hz)
        return np.exp(-0.5 * np.square(semitones / bandwidth_semitones))

    mask_a = _log_gaussian_mask(center_a_hz)
    mask_b = _log_gaussian_mask(center_b_hz)
    total = mask_a + mask_b + 1e-9
    a = librosa.istft((stft * (mask_a / total)[:, None]), hop_length=hop, length=len(mono))
    b = librosa.istft((stft * (mask_b / total)[:, None]), hop_length=hop, length=len(mono))
    return a.astype(np.float32), b.astype(np.float32)


def build_spatial_pair(
    guitar_path: Path,
    *,
    thresholds: LeadRhythmThresholds | None = None,
) -> _CandidatePair | None:
    """L/R dominance pair when stereo gate passes (evolved dual-guitar heuristic)."""
    thr = thresholds or LeadRhythmThresholds()
    if not guitar_path.exists():
        return None
    data, sr = _load_stereo(guitar_path)
    if data.shape[1] < 2 or len(data) < 1024:
        return None

    left = data[:, 0]
    right = data[:, 1]
    rms_l = _rms(left)
    rms_r = _rms(right)
    max_rms = max(rms_l, rms_r, 1e-9)
    balance = min(rms_l, rms_r) / max_rms
    if balance < thr.spatial_balance_min:
        return None
    if np.std(left) < 1e-6 or np.std(right) < 1e-6:
        return None

    corr = float(np.corrcoef(left, right)[0, 1])
    if not np.isfinite(corr):
        return None

    pitch_evidence: dict[str, float] | None = None
    detail = "stereo L/R dominance"
    if corr > thr.spatial_corr_max:
        # Raw correlation alone conflates "one guitar duplicated identically
        # into both channels" (corr -> 1.0) with "two genuinely distinct
        # guitars mixed with mild/no hard panning" (also corr ~0.92-0.99, but
        # NOT identical content). See module docstring "Root cause". Only look
        # for spatial-independent pitch-divergence evidence to rescue the
        # latter — never for correlations near-indistinguishable from a true
        # duplicate.
        if corr > thr.spatial_corr_relaxed_max:
            return None
        freq_l, conf_l = _dominant_pitch_estimate(left, sr)
        freq_r, conf_r = _dominant_pitch_estimate(right, sr)
        divergence = _pitch_divergence_semitones(freq_l, freq_r)
        if (
            divergence < thr.pitch_divergence_semitones_min
            or max(conf_l, conf_r) < thr.pitch_confidence_min
        ):
            return None
        pitch_evidence = {
            "left_hz": freq_l,
            "right_hz": freq_r,
            "divergence_semitones": divergence,
            "left_confidence": conf_l,
            "right_confidence": conf_r,
        }
        detail = (
            "stereo L/R dominance (mild pan; admitted via pitch-divergence "
            f"evidence, Δ={divergence:.1f} semitones)"
        )

    if pitch_evidence is not None:
        # Near-center panning: the per-sample L/R dominance heuristic below
        # degenerates because both channels carry comparable amounts of both
        # sources (that heuristic assumes one channel is ~mostly one source).
        # Use the two already-detected predominant pitches to separate by
        # frequency content instead, which remains meaningful at any pan.
        harmonic = _harmonic_pitch_pair(
            (left + right) * 0.5, sr, pitch_evidence["left_hz"], pitch_evidence["right_hz"]
        )
    else:
        harmonic = None

    if harmonic is not None:
        a, b = harmonic
    else:
        a = np.where(np.abs(left) >= np.abs(right), left, left - 0.5 * right).astype(np.float32)
        b = np.where(np.abs(right) >= np.abs(left), right, right - 0.5 * left).astype(np.float32)
    sep = score_candidate_pair(a, b, sr)
    # Boost spatial score slightly when corr is low (more independent channels).
    sep = min(1.0, sep + max(0.0, (thr.spatial_corr_max - corr) * 0.15))
    return _CandidatePair(
        method="spatial",
        a=a,
        b=b,
        sr=sr,
        separability=sep,
        correlation=corr,
        balance_ratio=balance,
        detail=detail,
        pitch_evidence=pitch_evidence,
    )


def build_midside_pair(
    guitar_path: Path,
    *,
    thresholds: LeadRhythmThresholds | None = None,
    relax_side_floor: bool = False,
) -> _CandidatePair | None:
    """
    Mid/Side pair for centered lead + wide-panned rhythm (common mix layout).

    Mid = (L+R)/2, Side = (L-R)/2. Rejects true mono (L≡R) unless
    ``relax_side_floor`` (last-resort forced emit only).
    """
    thr = thresholds or LeadRhythmThresholds()
    if not guitar_path.exists():
        return None
    data, sr = _load_stereo(guitar_path)
    if data.shape[1] < 2 or len(data) < 1024:
        return None

    left = data[:, 0].astype(np.float32)
    right = data[:, 1].astype(np.float32)
    mid = ((left + right) * 0.5).astype(np.float32)
    side = ((left - right) * 0.5).astype(np.float32)
    rms_mid = _rms(mid)
    rms_side = _rms(side)
    if rms_mid < 1e-6:
        return None
    side_ratio = rms_side / max(rms_mid, 1e-9)
    if not relax_side_floor and side_ratio < thr.midside_side_ratio_min:
        return None
    if rms_side < 1e-6 and not relax_side_floor:
        return None

    # If Side is near-silent (forced mono path), synthesize a quiet complementary
    # stream so we still have two WAVs — labels will be low-confidence.
    if rms_side < 1e-6:
        side = (mid * 0.15).astype(np.float32)

    sep = score_candidate_pair(mid, side, sr)
    return _CandidatePair(
        method="midside",
        a=mid,
        b=side,
        sr=sr,
        separability=sep,
        balance_ratio=side_ratio,
        detail=f"Mid/Side split (side/mid RMS ratio={side_ratio:.3f})",
    )


def build_register_pair(
    guitar_path: Path,
    *,
    thresholds: LeadRhythmThresholds | None = None,
) -> _CandidatePair | None:
    """
    Soft-split mono guitar into low vs high register via STFT band masks.

    Near-term candidate when spatial evidence is absent: aimed at register-
    separated lead/rhythm without claiming centered dual-source separation.
    """
    thr = thresholds or LeadRhythmThresholds()
    if not guitar_path.exists():
        return None
    try:
        import librosa
    except ImportError:
        return None

    data, sr = _load_stereo(guitar_path)
    if len(data) < 1024:
        return None
    mono = data.mean(axis=1).astype(np.float32)
    max_samples = int(thr.analyze_window_sec * sr)
    mono_work = mono[:max_samples] if len(mono) > max_samples else mono

    n_fft = 2048
    hop = 512
    stft = librosa.stft(mono_work, n_fft=n_fft, hop_length=hop)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    low_w = 1.0 / (1.0 + np.exp((freqs - REGISTER_CROSSOVER_HZ) / 40.0))
    high_w = 1.0 - low_w
    low = librosa.istft(stft * low_w[:, None], hop_length=hop, length=len(mono_work))
    high = librosa.istft(stft * high_w[:, None], hop_length=hop, length=len(mono_work))
    low = low.astype(np.float32)
    high = high.astype(np.float32)

    # Pad tails with silence (not duplicated mono) so length matches source.
    if len(mono) > len(mono_work):
        pad = len(mono) - len(mono_work)
        low = np.concatenate([low, np.zeros(pad, dtype=np.float32)])
        high = np.concatenate([high, np.zeros(pad, dtype=np.float32)])

    if _rms(low) < 1e-5 or _rms(high) < 1e-5:
        return None
    sep = score_candidate_pair(high, low, sr)
    return _CandidatePair(
        method="register",
        a=high,
        b=low,
        sr=sr,
        separability=sep,
        detail=f"STFT register split @{REGISTER_CROSSOVER_HZ:.0f}Hz",
    )


def build_spectral_pair(
    guitar_path: Path,
    *,
    thresholds: LeadRhythmThresholds | None = None,
) -> _CandidatePair | None:
    """HPSS harmonic vs residual (diagnostics / research only; not musical Lead/Rhythm)."""
    thr = thresholds or LeadRhythmThresholds()
    if not guitar_path.exists():
        return None
    try:
        import librosa
    except ImportError:
        return None

    data, sr = _load_stereo(guitar_path)
    if len(data) < 1024:
        return None
    mono = data.mean(axis=1).astype(np.float32)
    max_samples = int(thr.analyze_window_sec * sr)
    mono_work = mono[:max_samples] if len(mono) > max_samples else mono
    harm, perc = librosa.effects.hpss(mono_work)
    harm = harm.astype(np.float32)
    perc = perc.astype(np.float32)
    # Do not pad identical mono into both streams (legacy bug). Silence-pad only.
    if len(mono) > max_samples:
        pad = len(mono) - max_samples
        harm = np.concatenate([harm, np.zeros(pad, dtype=np.float32)])
        perc = np.concatenate([perc, np.zeros(pad, dtype=np.float32)])

    if _rms(harm) < 1e-5 or _rms(perc) < 1e-5:
        return None
    sep = score_candidate_pair(harm, perc, sr)
    return _CandidatePair(
        method="spectral",
        a=harm,
        b=perc,
        sr=sr,
        separability=sep,
        detail="HPSS harmonic vs residual (quarantined emit)",
    )


def score_candidate_pair(a: np.ndarray, b: np.ndarray, sr: int) -> float:
    """Cheap separability in [0, 1]: residual energy, centroid gap, onset-rate gap."""
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    n = min(len(a), len(b))
    if n < 512:
        return 0.0
    a = a[:n]
    b = b[:n]
    ra, rb = _rms(a), _rms(b)
    if ra < 1e-6 or rb < 1e-6:
        return 0.0

    proj = (np.dot(a, b) / (np.dot(b, b) + 1e-12)) * b
    residual = a - proj
    residual_ratio = min(1.0, _rms(residual) / (ra + 1e-12))

    win = min(n, sr * 4)
    aa = np.abs(np.fft.rfft(a[:win] * np.hanning(win)))
    bb = np.abs(np.fft.rfft(b[:win] * np.hanning(win)))
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    ca = float(np.sum(freqs * aa) / (np.sum(aa) + 1e-12))
    cb = float(np.sum(freqs * bb) / (np.sum(bb) + 1e-12))
    centroid_gap = min(1.0, abs(ca - cb) / 2000.0)

    hop = max(1, sr // 100)
    ea = np.array([_rms(a[i : i + hop]) for i in range(0, n - hop, hop)])
    eb = np.array([_rms(b[i : i + hop]) for i in range(0, n - hop, hop)])
    flux_a = float(np.mean(np.maximum(0.0, np.diff(ea, prepend=ea[:1]))))
    flux_b = float(np.mean(np.maximum(0.0, np.diff(eb, prepend=eb[:1]))))
    onset_gap = min(1.0, abs(flux_a - flux_b) / (max(flux_a, flux_b, 1e-9)))

    score = 0.45 * residual_ratio + 0.35 * centroid_gap + 0.20 * onset_gap
    return float(max(0.0, min(1.0, score)))


# One score toward "lead" (rhythm = 1 - lead). Each weight is annotated with its
# evidence tier from the role spec (texture > contour > salience > timbre).
# Tiers 9-11 (register, sustain/gain, model confidence) are capped at 10% combined.
# UNCALIBRATED: ordered by evidence tier, not fitted to labelled segments.
ROLE_WEIGHTS: dict[str, tuple[float, str]] = {
    "polyphony": (0.35, "tier 1 High: notes sounding per attack"),
    "pitch_class_change_rate": (0.30, "tier 2 High: pitch-class set change per attack"),
    "salience_peaks": (0.15, "tier 5 Medium: competing salience peaks per frame"),
    "pitch_iqr": (0.10, "tier 4 Medium-high proxy: melodic range of the line"),
    "pitch_median": (0.04, "tier 10 Low: absolute register (tie-breaker only)"),
    "sustain": (0.03, "tier 11 Low: note length / sustain"),
    "mean_velocity": (0.03, "tier 11 Low: Basic Pitch velocity is model confidence"),
}
LOW_TIER_FEATURES = ("pitch_median", "sustain", "mean_velocity")
# Texture-tier features: a split must differ on these, not just on timbre/register.
TEXTURE_FEATURES = ("polyphony", "pitch_class_change_rate", "salience_peaks", "pitch_iqr")


@dataclass
class RoleFeatures:
    pitch_median: float
    pitch_iqr: float
    note_density: float
    polyphony: float
    mean_velocity: float
    sustain: float
    # F2: share of consecutive attacks whose pitch-class set changes (None = not measured).
    pitch_class_change_rate: float | None = None
    # F5: median competing salience peaks per frame and max/sum concentration (None = no audio).
    salience_peaks: float | None = None
    salience_concentration: float | None = None

    def normalised(self) -> dict[str, float | None]:
        """Each measured feature mapped to 0..1 toward "lead" (None = not measured).

        Ranges are the spec's [cal] guesses (UNCALIBRATED): lead polyphony ~1-1.5 vs
        rhythm ~2.5-4; lead pc-change > 0.55 vs rhythm < 0.35.
        """
        sal = None
        if self.salience_peaks is not None and self.salience_peaks > 0:
            sal = 1.0 - min(1.0, max(0.0, (self.salience_peaks - 1.0) / 2.0))
        pcc = self.pitch_class_change_rate
        return {
            "polyphony": 1.0 - min(1.0, max(0.0, (self.polyphony - 1.0) / 2.0)),
            "pitch_class_change_rate": None if pcc is None else min(1.0, max(0.0, pcc)),
            "salience_peaks": sal,
            "pitch_iqr": min(1.0, self.pitch_iqr / 18.0),
            "pitch_median": min(1.0, max(0.0, (self.pitch_median - 50.0) / 30.0)),
            "sustain": min(1.0, self.sustain / 0.6),
            "mean_velocity": min(1.0, max(0.0, (self.mean_velocity - 40.0) / 60.0)),
        }

    def lead_score(self, *, use: frozenset[str] | set[str] | None = None) -> float:
        """Weighted lead-ness over measured features (weights renormalised); ``use`` limits them."""
        norm = self.normalised()
        total = 0.0
        weight_sum = 0.0
        for name, (weight, _tier) in ROLE_WEIGHTS.items():
            if use is not None and name not in use:
                continue
            value = norm.get(name)
            if value is None:
                continue
            total += weight * value
            weight_sum += weight
        return total / weight_sum if weight_sum > 0 else 0.5

    def rhythm_score(self) -> float:
        return 1.0 - self.lead_score()

    def to_dict(self) -> dict[str, float | None]:
        return {
            "pitch_median": self.pitch_median,
            "pitch_iqr": self.pitch_iqr,
            "note_density": self.note_density,
            "polyphony": self.polyphony,
            "mean_velocity": self.mean_velocity,
            "sustain": self.sustain,
            "pitch_class_change_rate": self.pitch_class_change_rate,
            "salience_peaks": self.salience_peaks,
            "salience_concentration": self.salience_concentration,
        }


def pitch_class_change_rate(notes: list[Any]) -> float | None:
    """F2: over consecutive attacks, the share whose pitch-class set differs from the last.

    Strumming repeats the same set ({E, G, B}, {E, G, B}...); a lead line changes
    note almost every attack. None when there are fewer than two attacks.
    """
    ordered = sorted(notes, key=lambda n: (n.start, n.pitch))
    attacks: list[set[int]] = []
    first = 0.0
    for note in ordered:
        if attacks and note.start - first <= ONSET_GROUP_SEC:
            attacks[-1].add(int(note.pitch) % 12)
        else:
            attacks.append({int(note.pitch) % 12})
            first = note.start
    if len(attacks) < 2:
        return None
    changes = sum(1 for a, b in pairwise(attacks) if a != b)
    return changes / (len(attacks) - 1)


def extract_role_features_from_notes(
    notes: list[Any],
    duration_sec: float,
) -> RoleFeatures:
    """Feature extraction from pretty_midi-like notes (testable without Basic Pitch)."""
    if not notes or duration_sec <= 0:
        return RoleFeatures(60.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    pitches = np.array([n.pitch for n in notes], dtype=np.float64)
    velocities = np.array([n.velocity for n in notes], dtype=np.float64)
    durs = np.array([max(0.0, n.end - n.start) for n in notes], dtype=np.float64)
    starts = np.array([n.start for n in notes], dtype=np.float64)

    overlaps = []
    for s in starts:
        overlaps.append(sum(1 for n in notes if n.start <= s < n.end))
    poly = float(np.mean(overlaps)) if overlaps else 0.0

    return RoleFeatures(
        pitch_median=float(np.median(pitches)),
        pitch_iqr=float(np.subtract(*np.percentile(pitches, [75, 25]))),
        note_density=float(len(notes) / duration_sec),
        polyphony=poly,
        mean_velocity=float(np.mean(velocities)),
        sustain=float(np.mean(durs)),
        pitch_class_change_rate=pitch_class_change_rate(notes),
    )


def _mean_optional(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return float(sum(present) / len(present)) if present else None


def _average_role_features(feats: list[RoleFeatures]) -> RoleFeatures:
    if not feats:
        return RoleFeatures(60.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    n = float(len(feats))
    return RoleFeatures(
        pitch_median=sum(f.pitch_median for f in feats) / n,
        pitch_iqr=sum(f.pitch_iqr for f in feats) / n,
        note_density=sum(f.note_density for f in feats) / n,
        polyphony=sum(f.polyphony for f in feats) / n,
        mean_velocity=sum(f.mean_velocity for f in feats) / n,
        sustain=sum(f.sustain for f in feats) / n,
        pitch_class_change_rate=_mean_optional([f.pitch_class_change_rate for f in feats]),
        salience_peaks=_mean_optional([f.salience_peaks for f in feats]),
        salience_concentration=_mean_optional([f.salience_concentration for f in feats]),
    )


def _with_salience(feat: RoleFeatures, clip: np.ndarray, sr: int) -> RoleFeatures:
    """Attach F5 salience measured on the same audio clip."""
    stats = salience_stats(clip, sr)
    if stats.frames == 0:
        return feat
    return replace(
        feat,
        salience_peaks=stats.peak_count,
        salience_concentration=stats.concentration,
    )


def extract_role_features(
    audio_mono: np.ndarray,
    sr: int,
    *,
    thresholds: LeadRhythmThresholds | None = None,
) -> RoleFeatures:
    """Run Basic Pitch on mono (first + last analyze windows) and extract features."""
    thr = thresholds or LeadRhythmThresholds()
    import pretty_midi
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    window = int(thr.analyze_window_sec * sr)
    n = len(audio_mono)
    if n < sr // 4:
        return RoleFeatures(60.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    starts = [0]
    if n > window + sr:
        starts.append(max(0, n - window))

    feats: list[RoleFeatures] = []
    for start in starts:
        clip = audio_mono[start : start + window].astype(np.float32)
        if len(clip) < sr // 4:
            continue
        stereo = _mono_to_stereo(clip)
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "clip.wav"
            sf.write(str(wav_path), stereo, sr, subtype="PCM_16")
            _, midi_data, _ = predict(
                str(wav_path),
                model_or_model_path=ICASSP_2022_MODEL_PATH,
                onset_threshold=0.5,
                frame_threshold=0.3,
                minimum_note_length=58.0,
            )
            mid_path = Path(tmp) / "clip.mid"
            midi_data.write(str(mid_path))
            pm = pretty_midi.PrettyMIDI(str(mid_path))
            notes = [note for inst in pm.instruments for note in inst.notes]
            feats.append(
                _with_salience(
                    extract_role_features_from_notes(notes, duration_sec=len(clip) / sr),
                    clip,
                    sr,
                )
            )
    return _average_role_features(feats)


def classify_lead_rhythm_roles(
    feat_a: RoleFeatures,
    feat_b: RoleFeatures,
    *,
    margin_min: float | None = None,
) -> tuple[Literal["a_lead", "b_lead", "ambiguous"], float, dict[str, Any]]:
    """
    Assign which stream is lead vs rhythm.

    Returns (assignment, confidence_margin, detail).
    """
    floor = ROLE_MARGIN_MIN if margin_min is None else float(margin_min)
    # Score both streams over the features measured on BOTH, so a missing feature
    # on one side never tilts the comparison.
    norm_a, norm_b = feat_a.normalised(), feat_b.normalised()
    shared = {name for name in ROLE_WEIGHTS if norm_a.get(name) is not None and norm_b.get(name) is not None}
    lead_a = feat_a.lead_score(use=shared)
    lead_b = feat_b.lead_score(use=shared)
    s1 = 0.5 * (lead_a + (1.0 - lead_b))
    s2 = 0.5 * (lead_b + (1.0 - lead_a))
    margin = abs(s1 - s2)
    texture = shared & set(TEXTURE_FEATURES)
    texture_margin = abs(feat_a.lead_score(use=texture) - feat_b.lead_score(use=texture)) if texture else 0.0
    detail = {
        "stream_a": feat_a.to_dict(),
        "stream_b": feat_b.to_dict(),
        "normalised_a": norm_a,
        "normalised_b": norm_b,
        "weights": {name: {"weight": w, "tier": tier} for name, (w, tier) in ROLE_WEIGHTS.items()},
        "features_used": sorted(shared),
        "score_a_lead": s1,
        "score_b_lead": s2,
        "margin": margin,
        "texture_margin": texture_margin,
        "margin_min": floor,
    }
    if margin < floor or margin < 1e-9:
        return "ambiguous", float(margin), detail
    if s1 > s2:
        return "a_lead", float(margin), detail
    return "b_lead", float(margin), detail


def split_lead_rhythm_guitar(
    guitar_path: Path,
    output_dir: Path,
    *,
    use_basic_pitch: bool = True,
    thresholds: LeadRhythmThresholds | None = None,
    emit_mode: EmitMode = "confident",
) -> tuple[dict[str, Path], LeadRhythmDiagnostics]:
    """
    Attempt lead/rhythm split of a Demucs guitar stem.

    Writes ``guitar_split_diagnostics.json`` whenever a guitar stem exists.
    Emits ``lead_guitar.wav`` + ``rhythm_guitar.wav`` when separability and role
    gates pass, or when ``emit_mode`` is ``best_effort`` (legacy always-emit).
    In ``confident`` mode, low-confidence / forced splits write diagnostics only
    with ``outcome=ambiguous``. Spectral candidates never emit unless
    ``thresholds.allow_spectral_emit``.
    """
    thr = LeadRhythmThresholds.from_env(thresholds)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    diag_path = out_dir / "guitar_split_diagnostics.json"

    if not guitar_path.exists():
        diag = LeadRhythmDiagnostics(
            outcome="skipped",
            reason="guitar stem missing",
            attempted=False,
        )
        diag.write_json(diag_path)
        return {"guitar_split_diagnostics": diag_path}, diag

    try:
        probe, probe_sr = _load_stereo(guitar_path)
    except Exception as exc:
        diag = LeadRhythmDiagnostics(
            outcome="skipped",
            reason=f"guitar stem unreadable: {exc}",
            attempted=False,
            features={"constants": CONSTANT_PROVENANCE},
        )
        diag.write_json(diag_path)
        return {"guitar_split_diagnostics": diag_path}, diag
    if len(probe) < MIN_ANALYSIS_SEC * probe_sr or _rms(probe) < SILENT_RMS:
        diag = LeadRhythmDiagnostics(
            outcome="skipped",
            reason="guitar stem empty or too short to judge roles",
            attempted=False,
            features={
                "duration_sec": len(probe) / max(1, probe_sr),
                "constants": CONSTANT_PROVENANCE,
            },
        )
        diag.write_json(diag_path)
        return {"guitar_split_diagnostics": diag_path}, diag
    del probe

    candidates: list[_CandidatePair] = []
    spatial = build_spatial_pair(guitar_path, thresholds=thr)
    if spatial is not None:
        candidates.append(spatial)
    midside = build_midside_pair(guitar_path, thresholds=thr)
    if midside is not None:
        candidates.append(midside)
    register = build_register_pair(guitar_path, thresholds=thr)
    if register is not None:
        candidates.append(register)
    # Spectral kept for diagnostics / optional research emit only.
    spectral = build_spectral_pair(guitar_path, thresholds=thr)
    if spectral is not None:
        candidates.append(spectral)

    musical = [c for c in candidates if c.method != "spectral" or thr.allow_spectral_emit]
    if not musical:
        if emit_mode == "best_effort":
            # Last resort: force Mid/Side or register so WAVs always exist.
            forced_pair = build_midside_pair(guitar_path, thresholds=thr, relax_side_floor=True)
            if forced_pair is None:
                forced_pair = build_register_pair(guitar_path, thresholds=thr)
            if forced_pair is None:
                diag = LeadRhythmDiagnostics(
                    outcome="ambiguous",
                    reason=(
                        "no lead/rhythm candidate could be built "
                        "(guitar too short or unreadable)"
                    ),
                    method="none",
                    features={"emit_mode": emit_mode},
                )
                diag.write_json(diag_path)
                return {"guitar_split_diagnostics": diag_path}, diag
            musical = [forced_pair]
            candidates = [forced_pair]
        else:
            diag = LeadRhythmDiagnostics(
                outcome="ambiguous",
                reason=(
                    "no confident lead/rhythm candidate "
                    "(parts too similar, centered, or unreadable)"
                ),
                method="none",
                features={"emit_mode": emit_mode, "skipped_emit": True},
            )
            diag.write_json(diag_path)
            return {"guitar_split_diagnostics": diag_path}, diag

    best = _pick_best_candidate(musical, thr)
    if best.method == "spectral" and not thr.allow_spectral_emit:
        non_spectral = [c for c in musical if c.method != "spectral"]
        if non_spectral:
            best = _pick_best_candidate(non_spectral, thr)
        else:
            forced = build_midside_pair(guitar_path, thresholds=thr, relax_side_floor=True)
            if forced is None:
                forced = build_register_pair(guitar_path, thresholds=thr)
            if forced is None:
                diag = LeadRhythmDiagnostics(
                    outcome="ambiguous",
                    reason=(
                        "spectral (HPSS) candidate quarantined and no fallback pair"
                    ),
                    separability_score=best.separability,
                    method=best.method,
                    features={
                        "quarantined": True,
                        "detail": best.detail,
                        "emit_mode": emit_mode,
                        "skipped_emit": emit_mode == "confident",
                    },
                )
                diag.write_json(diag_path)
                return {"guitar_split_diagnostics": diag_path}, diag
            best = forced

    sep_floor = _separability_floor_for(best.method, thr)
    low_sep = best.separability < sep_floor

    # Role features always describe the two candidate streams themselves. Raw L/R
    # of the unsplit stem can each hold both guitars, so their polyphony and
    # density would describe the sum, not a source.
    analyze_a, analyze_b, analyze_sr = best.a, best.b, best.sr

    if use_basic_pitch:
        feat_a = extract_role_features(analyze_a, analyze_sr, thresholds=thr)
        feat_b = extract_role_features(analyze_b, analyze_sr, thresholds=thr)
    else:
        feat_a = _features_from_audio_stats(analyze_a, analyze_sr, thresholds=thr)
        feat_b = _features_from_audio_stats(analyze_b, analyze_sr, thresholds=thr)

    role_floor = _role_floor_for(best.method, thr)
    # Zero floor gives the direction of the evidence; confidence is judged
    # against the real floor below.
    assignment, margin, feat_detail = classify_lead_rhythm_roles(
        feat_a, feat_b, margin_min=0.0
    )
    feat_detail["constants"] = CONSTANT_PROVENANCE
    if best.pitch_evidence is not None:
        feat_detail["pitch_evidence"] = best.pitch_evidence
    if best.method == "spatial" and best.pitch_evidence is None:
        # Per-sample L/R dominance is a distortion, not a separation; only hard-panned
        # content comes out clean.
        feat_detail["approximate_separation"] = True

    # Tied evidence or a split that differs only in register/timbre is not a role
    # difference: refuse rather than guess (prefer ambiguous over wrong), even in
    # best-effort mode.
    texture_margin = float(feat_detail.get("texture_margin") or 0.0)
    refusal = None
    if assignment == "ambiguous" or margin < 1e-9:
        refusal = "role evidence is tied between the two streams"
    elif texture_margin < role_floor:
        refusal = (
            f"streams differ mainly in register/timbre, not texture "
            f"(texture margin {texture_margin:.3f} below {role_floor})"
        )
    if refusal is not None:
        feat_detail["emit_mode"] = emit_mode
        feat_detail["skipped_emit"] = True
        diag = LeadRhythmDiagnostics(
            outcome="ambiguous",
            reason=f"Lead/Rhythm not emitted: {refusal}; combined Guitar kept",
            separability_score=best.separability,
            role_confidence=margin,
            method=best.method,
            correlation=best.correlation,
            balance_ratio=best.balance_ratio,
            low_confidence=True,
            features=feat_detail,
        )
        diag.write_json(diag_path)
        return {"guitar_split_diagnostics": diag_path}, diag

    low_role = margin < role_floor
    forced = low_sep or low_role
    if assignment == "a_lead":
        lead_audio, rhythm_audio = best.a, best.b
    else:
        lead_audio, rhythm_audio = best.b, best.a

    feat_detail["emit_mode"] = emit_mode
    should_emit = emit_mode == "best_effort" or not forced

    if forced:
        reasons = []
        if low_sep:
            reasons.append(
                f"separability {best.separability:.3f} below floor {sep_floor}"
            )
        if low_role:
            reasons.append(f"role margin {margin:.3f} below {role_floor}")
        gate_detail = " ; ".join(reasons)
        feat_detail["forced_emit"] = True
        feat_detail["low_confidence"] = True
    else:
        gate_detail = ""
        reason = f"split via {best.method}; role margin {margin:.3f}"

    if not should_emit:
        reason = (
            f"Lead/Rhythm not emitted (confident mode): {best.method} candidate "
            f"failed gates ({gate_detail}); combined Guitar kept"
        )
        feat_detail["skipped_emit"] = True
        diag = LeadRhythmDiagnostics(
            outcome="ambiguous",
            reason=reason,
            separability_score=best.separability,
            role_confidence=margin,
            method=best.method,
            correlation=best.correlation,
            balance_ratio=best.balance_ratio,
            forced_emit=True,
            low_confidence=True,
            features=feat_detail,
        )
        diag.write_json(diag_path)
        return {"guitar_split_diagnostics": diag_path}, diag

    lead_path = out_dir / "lead_guitar.wav"
    rhythm_path = out_dir / "rhythm_guitar.wav"
    sf.write(str(lead_path), _mono_to_stereo(lead_audio), best.sr, subtype="PCM_16")
    sf.write(str(rhythm_path), _mono_to_stereo(rhythm_audio), best.sr, subtype="PCM_16")

    if forced:
        reason = (
            f"best-effort split via {best.method} "
            f"({gate_detail}); labels may be inaccurate"
        )
    else:
        reason = f"split via {best.method}; role margin {margin:.3f}"

    diag = LeadRhythmDiagnostics(
        outcome="lead_rhythm",
        reason=reason,
        separability_score=best.separability,
        role_confidence=margin,
        method=best.method,
        correlation=best.correlation,
        balance_ratio=best.balance_ratio,
        forced_emit=forced,
        low_confidence=forced,
        features=feat_detail,
    )
    diag.write_json(diag_path)
    return {
        "lead_guitar": lead_path,
        "rhythm_guitar": rhythm_path,
        "guitar_split_diagnostics": diag_path,
    }, diag


def _separability_floor_for(method: Method, thr: LeadRhythmThresholds) -> float:
    if method == "spectral":
        return thr.spectral_separability_floor
    if method == "register":
        return thr.register_separability_floor
    if method == "midside":
        return thr.midside_separability_floor
    return thr.separability_floor


def _role_floor_for(method: Method, thr: LeadRhythmThresholds) -> float:
    if method == "spectral":
        return thr.spectral_role_margin_min
    return thr.role_margin_min


def _pick_best_candidate(
    candidates: list[_CandidatePair],
    thr: LeadRhythmThresholds,
) -> _CandidatePair:
    """Prefer hard-panned spatial; then midside; then register; spectral last."""
    spatial = [
        c
        for c in candidates
        if c.method == "spatial"
        and c.separability >= thr.separability_floor
        and c.correlation is not None
        and c.correlation < 0.35
    ]
    if spatial:
        return max(spatial, key=lambda c: c.separability)
    spatial_any = [c for c in candidates if c.method == "spatial"]
    if spatial_any:
        return max(spatial_any, key=lambda c: c.separability)
    midside = [c for c in candidates if c.method == "midside"]
    if midside:
        return max(midside, key=lambda c: c.separability)
    register = [c for c in candidates if c.method == "register"]
    if register:
        return max(register, key=lambda c: c.separability)
    return max(candidates, key=lambda c: c.separability)


def _spectral_centroid_hz(mono: np.ndarray, sr: int) -> float:
    win = min(len(mono), sr * 2)
    if win < 64:
        return 0.0
    x = mono[:win] * np.hanning(win)
    mag = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    return float(np.sum(freqs * mag) / (np.sum(mag) + 1e-12))


def _features_from_audio_stats(
    mono: np.ndarray,
    sr: int,
    *,
    thresholds: LeadRhythmThresholds | None = None,
) -> RoleFeatures:
    """Map centroid/flux into RoleFeatures when Basic Pitch is skipped (tests/fallback)."""
    thr = thresholds or LeadRhythmThresholds()
    window = int(thr.analyze_window_sec * sr)
    n = len(mono)
    starts = [0]
    if n > window + sr:
        starts.append(max(0, n - window))

    feats: list[RoleFeatures] = []
    for start in starts:
        clip = mono[start : start + window]
        if len(clip) < 64:
            continue
        c = _spectral_centroid_hz(clip, sr)
        pitch = 12.0 * np.log2(max(c, 80.0) / 440.0) + 69.0
        hop = max(1, sr // 100)
        energy = np.array(
            [_rms(clip[i : i + hop]) for i in range(0, max(1, len(clip) - hop), hop)]
        )
        flux = (
            float(np.mean(np.maximum(0.0, np.diff(energy, prepend=energy[:1]))))
            if len(energy)
            else 0.0
        )
        dens = min(8.0, flux * 40.0)
        poly = 1.0 + min(2.0, dens / 4.0)
        feats.append(
            _with_salience(
                RoleFeatures(
                    pitch_median=float(pitch),
                    pitch_iqr=6.0,
                    note_density=float(dens),
                    polyphony=float(poly),
                    mean_velocity=80.0,
                    sustain=0.2,
                ),
                clip,
                sr,
            )
        )
    return _average_role_features(feats)
