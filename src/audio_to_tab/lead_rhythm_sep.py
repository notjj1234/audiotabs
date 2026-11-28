"""Lead/Rhythm guitar split stage (Mel-Band RoFormer by listra92).

2026-11-19: the pipeline's first genuine *lead vs rhythm* separator. The
existing ``lead_rhythm.py`` is a post-hoc heuristic classifier on one
combined Demucs guitar stem — useful, but not a separator. This module
integrates the community checkpoint trained for exactly two stems:

- **Mel-Band RoFormer Lead-Rhythm Guitar by listra92** — stems
  ``[Lead, Rhythm]`` (``training.instruments``), ``target_instrument: Lead``,
  44.1 kHz. One-target inference: Lead comes from the model, Rhythm is the
  residual of the guitar mixture (same pattern as the becruily MelBand
  guitar model; see ``roformer._run_inprocess``).

Checkpoint hosting: ``noblebarkrr/mvsepless_resources`` on Hugging Face is a
community mirror aggregating many trainers' models. **No license is stated
for this checkpoint — treat it as all-rights-reserved, same posture as
BS-RoFormer-SW (see ``roformer.py``).** Weights are SHA256-pinned, cached
under ``separator_cache_dir()``, and never committed.

Runtime: the in-process ``bs_roformer`` package (optional extra
``[roformer]``) — the same route ``run_melband_guitar`` prefers. The
``audio_separator`` UVR stack cannot load this checkpoint unchanged: its
``load_model`` only accepts filenames from its own registry
(``separator.py:873`` raises for unknown files; verified 2026-11-19 against
audio-separator 0.48.0), and this checkpoint is not in that registry.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_to_tab import roformer

logger = logging.getLogger(__name__)

LEAD_RHYTHM_SPLIT_ID = "lead_rhythm_split"

LEAD_RHYTHM_MODEL_DIR = "mbr_lead_rhythm_guitar_listra92"
MBR_LEAD_RHYTHM_CKPT_NAME = "mbr_lead_rhythm_guitar_listra92.ckpt"
MBR_LEAD_RHYTHM_CONFIG_NAME = "mbr_lead_rhythm_guitar_listra92_config.yaml"

MBR_LEAD_RHYTHM_HF_REPO = "noblebarkrr/mvsepless_resources"
MBR_LEAD_RHYTHM_CKPT_URL = (
    f"https://huggingface.co/{MBR_LEAD_RHYTHM_HF_REPO}/resolve/main/"
    f"mel_band_roformer/{MBR_LEAD_RHYTHM_CKPT_NAME}"
)
MBR_LEAD_RHYTHM_CONFIG_URL = (
    f"https://huggingface.co/{MBR_LEAD_RHYTHM_HF_REPO}/resolve/main/"
    f"mel_band_roformer/{MBR_LEAD_RHYTHM_CONFIG_NAME}"
)

# Phase 0 verification (2026-11-19): 337,073,664 bytes, computed locally.
MBR_LEAD_RHYTHM_CKPT_SHA256 = (
    "b3c47bca33609ca1ba0bb2d2076410bfd1eb941b051b72afc1f3e24d12b17eef"
)
MBR_LEAD_RHYTHM_CONFIG_SHA256 = (
    "a26685bc9ab10aab4dc153b74ec3559f1b4bd2251d129a13b6b22fe3a27d382d"
)

LEAD_RHYTHM_STEM_NAMES = ("lead_guitar", "rhythm_guitar")

class LeadRhythmSplitError(RuntimeError):
    """User-facing lead/rhythm split failure. Raised as-is, never wrapped."""


INSTALL_HINT = (
    "Lead/Rhythm split needs torch, einops, beartype, rotary-embedding-torch and librosa: "
    "pip install -e \".[demucs,roformer]\""
)


def mbr_lead_rhythm_paths() -> tuple[Path, Path]:
    root = roformer.separator_cache_dir() / LEAD_RHYTHM_MODEL_DIR
    return root / MBR_LEAD_RHYTHM_CKPT_NAME, root / MBR_LEAD_RHYTHM_CONFIG_NAME


def download_mbr_lead_rhythm_weights(*, force: bool = False) -> tuple[Path, Path]:
    """Download checkpoint + config (urllib, SHA256-pinned), unless verified cached."""
    ckpt, yaml_path = mbr_lead_rhythm_paths()
    if force:
        ckpt.unlink(missing_ok=True)
        yaml_path.unlink(missing_ok=True)
    roformer.download_sha256_file(
        MBR_LEAD_RHYTHM_CKPT_URL, ckpt, MBR_LEAD_RHYTHM_CKPT_SHA256
    )
    roformer.download_sha256_file(
        MBR_LEAD_RHYTHM_CONFIG_URL, yaml_path, MBR_LEAD_RHYTHM_CONFIG_SHA256
    )
    return ckpt, yaml_path


def load_mbr_lead_rhythm_config(yaml_path: Path) -> dict:
    """Load the model YAML and validate it is the verified Lead/Rhythm config."""
    config = roformer._load_yaml(Path(yaml_path))
    training = config.get("training") or {}
    instruments = list(training.get("instruments") or [])
    if instruments != ["Lead", "Rhythm"]:
        raise RuntimeError(
            f"Expected Lead/Rhythm instruments in {yaml_path}, got {instruments!r}"
        )
    audio = config.get("audio") or {}
    sample_rate = audio.get("sample_rate")
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise RuntimeError(f"Missing audio.sample_rate in {yaml_path}")
    return config


def is_lead_rhythm_split_available() -> bool:
    """True when the bundled Mel-Band RoFormer code's dependencies are installed.

    Checked with ``find_spec`` only, so torch is never imported by a probe.
    """
    import importlib.util

    from audio_to_tab.vendor.mel_band_roformer import REQUIRED_MODULES

    return all(importlib.util.find_spec(name) is not None for name in REQUIRED_MODULES)


def build_lead_rhythm_model(config: dict, ckpt_path: Path, device):
    """Build the bundled MelBandRoformer and load the checkpoint strictly.

    Strict loading matters: a shape or key mismatch means the wrong architecture,
    which would otherwise produce a silent garbage split.
    """
    import inspect

    import torch

    from audio_to_tab.vendor.mel_band_roformer.model import MelBandRoformer

    params = inspect.signature(MelBandRoformer.__init__).parameters
    model_cfg = {k: v for k, v in (config.get("model") or {}).items() if k in params}
    for key in ("multi_stft_resolutions_window_sizes",):
        if isinstance(model_cfg.get(key), list):
            model_cfg[key] = tuple(model_cfg[key])
    model = MelBandRoformer(**model_cfg)
    state = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    if isinstance(state, dict):
        for key in ("state", "state_dict", "model_state_dict"):
            if isinstance(state.get(key), dict):
                state = state[key]
                break
    model.load_state_dict(state, strict=True)
    model.eval()
    model.to(device)
    return model


# ---------------------------------------------------------------------------
# Split diagnostics
# ---------------------------------------------------------------------------

ENVELOPE_WIN_SEC = 0.05
NEAR_SILENT_DBFS = -60.0
CORRELATION_WARN = 0.85
MIN_INPUT_SEC = 5.0
CLIP_SAMPLE_THRESHOLD = 0.99
CLIP_FRACTION_MIN = 1e-4
SILENCE_FRAME_DBFS = -60.0

# BS.1770 K-weighting, standard (48 kHz) coefficients — an approximation at
# other rates, documented as such in integrated_loudness_lufs.
_K_SHELF_B = (1.53512485958697, -2.69169618940638, 1.19839281085285)
_K_SHELF_A = (1.0, -1.69065929318241, 0.73248077421585)
_K_HP_B = (1.0, -2.0, 1.0)
_K_HP_A = (1.0, -1.99004745483398, 0.99007225036621)


def _to_mono(data: np.ndarray) -> np.ndarray:
    return data.mean(axis=1) if data.ndim == 2 else data


def _frame_rms_db(mono: np.ndarray, sr: int, win_sec: float) -> np.ndarray:
    win = max(1, int(sr * win_sec))
    n_frames = max(0, len(mono) // win)
    if n_frames == 0:
        return np.array([], dtype=np.float64)
    frames = mono[: n_frames * win].reshape(n_frames, win)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    return 20.0 * np.log10(np.maximum(rms, 1e-10))


def _spectral_centroid_hz(mono: np.ndarray, sr: int) -> float:
    if mono.size == 0 or float(np.max(np.abs(mono))) == 0.0:
        return 0.0
    spec = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    freqs = np.fft.rfftfreq(mono.size, d=1.0 / sr)
    total = float(spec.sum())
    return float((spec * freqs).sum() / total) if total > 0 else 0.0


def integrated_loudness_lufs(mono: np.ndarray, sr: int) -> float:
    """BS.1770-style gated integrated loudness (approximation, documented).

    Method: mono downmix → K-weighting (Stage-1 high-shelf + Stage-2 high-pass
    biquads, standard 48 kHz coefficients applied at any rate) → 400 ms blocks
    with 75 % overlap → block loudness ``-0.691 + 10*log10(mean square)`` →
    absolute gate at -70 LUFS, then relative gate at (gated mean - 10 LU).
    This is a numpy/scipy implementation of the BS.1770 procedure, not an
    ITU-certified measurement.
    """
    from scipy.signal import lfilter

    x = np.asarray(mono, dtype=np.float64)
    if x.size == 0:
        return -70.0
    x = lfilter(_K_SHELF_B, _K_SHELF_A, x)
    x = lfilter(_K_HP_B, _K_HP_A, x)

    block = int(0.400 * sr)
    hop = int(0.100 * sr)
    if x.size < block:
        blocks = [x]
    else:
        starts = range(0, x.size - block + 1, hop)
        blocks = [x[s : s + block] for s in starts]
    energies = np.array([float(np.mean(b * b)) for b in blocks], dtype=np.float64)
    with np.errstate(divide="ignore"):
        loudness = -0.691 + 10.0 * np.log10(np.maximum(energies, 1e-20))

    kept = energies[loudness > -70.0]
    if kept.size == 0:
        return -70.0
    relative_gate = -0.691 + 10.0 * math.log10(max(float(np.mean(kept)), 1e-20)) - 10.0
    kept = energies[(loudness > -70.0) & (loudness > relative_gate)]
    if kept.size == 0:
        return -70.0
    return float(-0.691 + 10.0 * math.log10(max(float(np.mean(kept)), 1e-20)))


def pearson_rms_correlation(
    lead: np.ndarray, rhythm: np.ndarray, sr: int
) -> float | None:
    """Pearson r of the two stems' 50 ms RMS envelopes. None if too short."""
    a = _frame_rms_db(_to_mono(np.asarray(lead, dtype=np.float64)), sr, ENVELOPE_WIN_SEC)
    b = _frame_rms_db(_to_mono(np.asarray(rhythm, dtype=np.float64)), sr, ENVELOPE_WIN_SEC)
    n = min(a.size, b.size)
    if n < 2:
        return None
    a, b = a[:n], b[:n]
    sa, sb = float(a.std()), float(b.std())
    if sa == 0.0 and sb == 0.0:
        # Degenerate flat envelopes (e.g. steady test tones): equal loudness
        # tracks perfectly, different loudness does not co-vary at all.
        return 1.0 if abs(float(a[0]) - float(b[0])) < 1e-6 else 0.0
    if sa == 0.0 or sb == 0.0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


@dataclass
class StemAudioStats:
    rms_dbfs: float
    peak: float
    spectral_centroid_hz: float
    silence_ratio: float
    integrated_loudness_lufs: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LeadRhythmSplitDiagnostics:
    """Diagnostics for a lead/rhythm model split (warn-only, never blocks)."""

    attempted: bool
    reason: str
    model_sample_rate: int = 44100
    input_sample_rate: int | None = None
    input_channels: int | None = None
    resampled: bool = False
    input_duration_sec: float | None = None
    lead: StemAudioStats | None = None
    rhythm: StemAudioStats | None = None
    envelope_correlation: float | None = None
    warnings: list[str] = field(default_factory=list)
    vocal_suppression: dict | None = None  # vocal_debleed.guitar_for_split report
    stereo_presplit: dict | None = None  # guitar_roles_stereo report when ATT_STEREO_PRESPLIT=1

    def to_dict(self) -> dict:
        return {
            "attempted": self.attempted,
            "reason": self.reason,
            "model_sample_rate": self.model_sample_rate,
            "input_sample_rate": self.input_sample_rate,
            "input_channels": self.input_channels,
            "resampled": self.resampled,
            "input_duration_sec": self.input_duration_sec,
            "lead": self.lead.to_dict() if self.lead else None,
            "rhythm": self.rhythm.to_dict() if self.rhythm else None,
            "envelope_correlation": self.envelope_correlation,
            "warnings": list(self.warnings),
            "vocal_suppression": self.vocal_suppression,
            "stereo_presplit": self.stereo_presplit,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LeadRhythmSplitDiagnostics:
        def stats(raw: dict | None) -> StemAudioStats | None:
            return StemAudioStats(**raw) if isinstance(raw, dict) else None

        return cls(
            attempted=bool(data.get("attempted")),
            reason=str(data.get("reason") or ""),
            model_sample_rate=int(data.get("model_sample_rate") or 44100),
            input_sample_rate=data.get("input_sample_rate"),
            input_channels=data.get("input_channels"),
            resampled=bool(data.get("resampled")),
            input_duration_sec=data.get("input_duration_sec"),
            lead=stats(data.get("lead")),
            rhythm=stats(data.get("rhythm")),
            envelope_correlation=data.get("envelope_correlation"),
            warnings=[str(w) for w in (data.get("warnings") or [])],
            vocal_suppression=data.get("vocal_suppression"),
            stereo_presplit=data.get("stereo_presplit"),
        )

    def write_json(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path


def _stem_stats(path: Path, sr: int) -> StemAudioStats:
    data, _ = sf.read(str(path), always_2d=True)
    mono = _to_mono(data.astype(np.float64))
    rms = float(np.sqrt(np.mean(mono * mono))) if mono.size else 0.0
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    frame_db = _frame_rms_db(mono, sr, ENVELOPE_WIN_SEC)
    if frame_db.size:
        silence_ratio = float(np.mean(frame_db < SILENCE_FRAME_DBFS))
    else:
        # Shorter than one analysis frame: judge the whole signal instead.
        silence_ratio = (
            1.0 if 20.0 * math.log10(max(rms, 1e-10)) < SILENCE_FRAME_DBFS else 0.0
        )
    return StemAudioStats(
        rms_dbfs=20.0 * math.log10(max(rms, 1e-10)),
        peak=peak,
        spectral_centroid_hz=_spectral_centroid_hz(mono, sr),
        silence_ratio=silence_ratio,
        integrated_loudness_lufs=integrated_loudness_lufs(mono, sr),
    )


def _input_info(path: Path) -> tuple[int, int, float, float]:
    """(channels, sample_rate, duration_sec, clipped_fraction)."""
    data, sr = sf.read(str(path), always_2d=True)
    duration = float(data.shape[0]) / float(sr) if sr else 0.0
    clipped = 0.0
    if data.size:
        clipped = float(np.mean(np.abs(data) > CLIP_SAMPLE_THRESHOLD))
    return int(data.shape[1]), int(sr), duration, clipped


def analyze_lead_rhythm_stems(
    lead_path: Path,
    rhythm_path: Path,
    *,
    input_path: Path | None = None,
    model_sample_rate: int = 44100,
    resampled: bool = False,
) -> LeadRhythmSplitDiagnostics:
    """Per-stem stats + pair correlation + warn-only input quality flags."""
    lead_path, rhythm_path = Path(lead_path), Path(rhythm_path)
    lead_data, lead_sr = sf.read(str(lead_path), always_2d=True)
    rhythm_data, rhythm_sr = sf.read(str(rhythm_path), always_2d=True)

    warnings: list[str] = []
    diag = LeadRhythmSplitDiagnostics(
        attempted=True,
        reason="model split completed",
        model_sample_rate=model_sample_rate,
        resampled=resampled,
    )

    diag.lead = _stem_stats(lead_path, lead_sr)
    diag.rhythm = _stem_stats(rhythm_path, rhythm_sr)
    if diag.lead.rms_dbfs < NEAR_SILENT_DBFS:
        warnings.append(
            f"Lead stem is near-silent ({diag.lead.rms_dbfs:.1f} dBFS "
            f"< {NEAR_SILENT_DBFS} dBFS)."
        )
    if diag.rhythm.rms_dbfs < NEAR_SILENT_DBFS:
        warnings.append(
            f"Rhythm stem is near-silent ({diag.rhythm.rms_dbfs:.1f} dBFS "
            f"< {NEAR_SILENT_DBFS} dBFS)."
        )

    corr = pearson_rms_correlation(
        _to_mono(lead_data.astype(np.float64)),
        _to_mono(rhythm_data.astype(np.float64)),
        lead_sr,
    )
    diag.envelope_correlation = corr
    if corr is not None and corr > CORRELATION_WARN:
        warnings.append(
            f"Lead/rhythm envelope correlation is high (r={corr:.2f} > "
            f"{CORRELATION_WARN}); the split may not be separable on this input."
        )

    probe = Path(input_path) if input_path is not None else lead_path
    try:
        channels, in_sr, duration, clipped_frac = _input_info(probe)
    except Exception:
        channels, in_sr, duration, clipped_frac = (None, None, None, 0.0)  # type: ignore[assignment]
    diag.input_channels = channels
    diag.input_sample_rate = in_sr
    diag.input_duration_sec = duration
    if clipped_frac > CLIP_FRACTION_MIN:
        warnings.append(
            f"Input appears clipped ({clipped_frac:.2%} of samples near full scale)."
        )
    if channels == 1:
        warnings.append("Input is mono; stereo panning cues are unavailable to the split.")
    if duration is not None and duration < MIN_INPUT_SEC:
        warnings.append(
            f"Input is very short ({duration:.1f}s < {MIN_INPUT_SEC:.0f}s); split stats are unreliable."
        )

    diag.warnings = warnings
    return diag


# ---------------------------------------------------------------------------
# Split runner
# ---------------------------------------------------------------------------


def run_lead_rhythm_split(
    guitar_path: Path,
    output_dir: Path,
    *,
    device: str = "cpu",
    on_progress: Callable[[str, float], None] | None = None,
) -> tuple[dict[str, Path], LeadRhythmSplitDiagnostics]:
    """Split an isolated guitar stem into lead_guitar / rhythm_guitar WAVs.

    Lead comes from the model (``target_instrument: Lead``); Rhythm is the
    mixture residual. Sample rate, chunk size, and overlap are read from the
    model YAML — never hardcoded. Fails loudly; there is no fallback to a
    combined guitar stem inside this mode.
    """
    if not is_lead_rhythm_split_available():
        raise LeadRhythmSplitError(f"Lead/rhythm split is not available. {INSTALL_HINT}")

    def _prog(message: str, fraction: float) -> None:
        if on_progress is not None:
            on_progress(message, fraction)

    guitar_path = Path(guitar_path)
    output_dir = Path(output_dir)
    roformer._refuse_long_roformer_audio(guitar_path)

    _prog("Preparing lead/rhythm model", 0.10)
    ckpt_path, yaml_path = download_mbr_lead_rhythm_weights()
    config = load_mbr_lead_rhythm_config(yaml_path)
    audio_cfg = config.get("audio") or {}
    infer_cfg = config.get("inference") or {}
    model_sr = int(audio_cfg["sample_rate"])
    chunk_size = int(audio_cfg.get("chunk_size") or 132300)
    n_overlap = int(infer_cfg.get("num_overlap") or 2)

    try:
        input_sr = int(sf.info(str(guitar_path)).samplerate)
    except Exception:
        input_sr = None
    resampled = bool(input_sr is not None and input_sr != model_sr)

    try:
        _prog("Splitting lead and rhythm guitars", 0.35)
        mix = roformer._load_audio_stereo(guitar_path, model_sr)
        model_input, presplit = _centre_for_split(mix)
        dev = roformer._torch_device(device)
        roformer._cap_cpu_threads(device)
        model = build_lead_rhythm_model(config, ckpt_path, dev)
        sources = roformer._demix_track(
            model,
            model_input,
            device=dev,
            chunk_size=chunk_size,
            n_overlap=n_overlap,
            num_stems=1,
        )
        lead = sources[0]
        # Residual of the full input, so side content the model never saw stays in rhythm.
        rhythm = mix - lead
        _prog("Writing lead and rhythm stems", 0.85)
        artifacts = roformer._write_stems(
            [lead, rhythm], list(LEAD_RHYTHM_STEM_NAMES), output_dir, model_sr
        )
    except Exception as exc:
        raise LeadRhythmSplitError(f"Lead/rhythm split failed: {exc}") from exc

    missing = [name for name in LEAD_RHYTHM_STEM_NAMES if name not in artifacts]
    if missing:
        raise LeadRhythmSplitError(f"Lead/rhythm split failed: missing stems {missing}")

    diag = analyze_lead_rhythm_stems(
        artifacts["lead_guitar"],
        artifacts["rhythm_guitar"],
        input_path=guitar_path,
        model_sample_rate=model_sr,
        resampled=resampled,
    )
    diag.stereo_presplit = presplit
    _prog("Lead/rhythm split complete", 0.99)
    return artifacts, diag


def _centre_for_split(mix: np.ndarray) -> tuple[np.ndarray, dict | None]:
    """The model input: the stereo centre candidate when ATT_STEREO_PRESPLIT is on, else ``mix``.

    ``mix`` is (channels, samples). Returns the input and the pre-split report (None when off).
    """
    from audio_to_tab.guitar_roles_stereo import presplit_array, stereo_presplit_enabled

    if not stereo_presplit_enabled():
        return mix, None
    centre, _side, result = presplit_array(mix.T)
    logger.info("Stereo pre-split before the Lead/Rhythm model: %s", result.reason)
    if centre is None:
        return mix, result.to_dict()
    return np.ascontiguousarray(centre.T, dtype=np.float32), result.to_dict()
