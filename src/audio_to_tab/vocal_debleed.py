"""Vocal de-bleed: drop guitar notes that are the singer leaking into the guitar stem.

Separators leave an attenuated copy of the vocal in the guitar stem, and pitch
detection turns it into guitar notes. A guitar note is treated as bleed when,
over its first half second:

* the vocal stem's pitch matches it (same pitch class within ±0.5 semitone,
  in unison or one octave away) for at least ``match_min`` of the frames, and
* the guitar stem is much weaker than the vocal at that pitch
  (``ratio < ratio_max``), and
* it fails the unison guard: a guitar really playing that note attacks it, so
  in the note's first 80 ms the guitar stem's energy *at that pitch* rises at
  least ``attack_excess`` times above what bleed explains (the stems' measured
  bleed gain × the vocal's energy). A broadband onset is not evidence: every
  other guitar note and every sung attack produce one.

The audio is never changed, so guitar notes away from the vocal pitch cannot be
lost. Diagnostics list every removed note with the numbers behind the decision.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

ANALYSIS_SR = 22050
HOP = 256
CQT_MIN_MIDI = 21
CQT_BINS = 88
EPS = 1e-9


@dataclass(frozen=True)
class DebleedThresholds:
    match_min: float = 0.6
    ratio_max: float = 0.5
    attack_excess: float = 2.0
    attack_window_sec: float = 0.08
    window_max_sec: float = 0.5
    semitone_tol: float = 0.5
    bleed_gain_floor: float = 0.02
    attack_floor: float = 0.01  # × the window's vocal peak, so tiny vocal values can't inflate it

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


DEFAULT_THRESHOLDS = DebleedThresholds()


@dataclass
class DebleedFeatures:
    """Frame-aligned evidence: vocal f0 (MIDI, NaN unvoiced) and per-pitch magnitudes."""

    hop_sec: float
    vocal_midi: np.ndarray  # (frames,)
    guitar_mag: np.ndarray  # (frames, 128) magnitude by MIDI pitch
    vocal_mag: np.ndarray  # (frames, 128)
    onset: np.ndarray  # (frames,) guitar-stem onset strength (diagnostics only)
    bleed_gain: float | None = None  # guitar-stem / vocal-stem level at the sung pitch

    @property
    def voiced_fraction(self) -> float:
        return float(np.mean(np.isfinite(self.vocal_midi))) if self.vocal_midi.size else 0.0

    @classmethod
    def from_audio(cls, guitar_stem: Path, vocals_stem: Path) -> DebleedFeatures:
        import librosa

        from audio_to_tab.vocal_notes import vocal_pitch_track

        track = vocal_pitch_track(vocals_stem)
        guitar, _ = librosa.load(str(guitar_stem), sr=ANALYSIS_SR, mono=True)
        vocals, _ = librosa.load(str(vocals_stem), sr=ANALYSIS_SR, mono=True)

        def mag(y: np.ndarray) -> np.ndarray:
            if y.size == 0:
                return np.zeros((0, 128))
            c = np.abs(
                librosa.cqt(
                    y,
                    sr=ANALYSIS_SR,
                    hop_length=HOP,
                    fmin=librosa.midi_to_hz(CQT_MIN_MIDI),
                    n_bins=CQT_BINS,
                    bins_per_octave=12,
                )
            ).T
            out = np.zeros((c.shape[0], 128))
            out[:, CQT_MIN_MIDI : CQT_MIN_MIDI + CQT_BINS] = c
            return out

        g = mag(guitar)
        v = _vocal_cqt(vocals_stem, lambda: mag(vocals))
        onset = librosa.onset.onset_strength(y=guitar, sr=ANALYSIS_SR, hop_length=HOP)
        midi = track.midi()
        n = min(len(midi), len(g), len(v), len(onset))
        feats = cls(
            hop_sec=HOP / ANALYSIS_SR,
            vocal_midi=midi[:n],
            guitar_mag=g[:n],
            vocal_mag=v[:n],
            onset=onset[:n],
        )
        feats.bleed_gain = estimate_bleed_gain(feats)
        return feats


_VOCAL_CQT: dict[tuple[int, str], np.ndarray] = {}


def _vocal_cqt(path: Path, compute: Any) -> np.ndarray:
    """Vocal CQT once per stem content: lead and rhythm de-bleed share it."""
    from audio_to_tab.vocal_notes import content_key

    key = content_key(path)
    if key not in _VOCAL_CQT:
        if len(_VOCAL_CQT) >= 2:
            _VOCAL_CQT.pop(next(iter(_VOCAL_CQT)))
        _VOCAL_CQT[key] = compute()
    return _VOCAL_CQT[key]


def estimate_bleed_gain(feats: DebleedFeatures) -> float | None:
    """Median guitar/vocal magnitude at the sung pitch over voiced frames.

    Real guitar notes rarely sit on the sung pitch for long, so the median is
    dominated by the vocal copy the separator left in the guitar stem.
    """
    voiced = np.flatnonzero(np.isfinite(feats.vocal_midi))
    if voiced.size == 0:
        return None
    pitch = np.clip(np.round(feats.vocal_midi[voiced]).astype(int), 0, 127)
    v = feats.vocal_mag[voiced, pitch]
    g = feats.guitar_mag[voiced, pitch]
    ok = v > (np.max(v) * 0.05 if v.size else 0.0)
    if not np.any(ok):
        return None
    return float(np.median(g[ok] / v[ok]))


@dataclass
class PartDebleedReport:
    notes_in: int
    notes_removed: int
    removed: list[dict[str, Any]] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VocalDebleedDiagnostics:
    attempted: bool
    reason: str
    enabled_by: str = ""
    parts: dict[str, dict[str, Any]] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=lambda: DEFAULT_THRESHOLDS.to_dict())
    vocal_voiced_fraction: float = 0.0
    bleed_gain: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path


def _note_evidence(
    note: Any, feats: DebleedFeatures, th: DebleedThresholds
) -> tuple[float, float, float]:
    """(match fraction, guitar/vocal ratio, attack excess over bleed) for one note."""
    n = len(feats.vocal_midi)
    a = int(max(0.0, float(note.start)) / feats.hop_sec)
    end = min(float(note.end), float(note.start) + th.window_max_sec)
    b = max(a + 1, int(end / feats.hop_sec))
    a, b = min(a, n), min(b, n)
    if b <= a:
        return 0.0, float("inf"), False
    pitch = int(note.pitch)
    vm = feats.vocal_midi[a:b]
    voiced = np.isfinite(vm)
    matched = np.zeros(b - a, dtype=bool)
    for k in (-12, 0, 12):
        matched |= voiced & (np.abs(np.where(voiced, vm, 0.0) - (pitch + k)) <= th.semitone_tol)
    match = float(np.mean(matched))
    ratio = float("inf")
    if np.any(matched):
        frames = np.arange(a, b)[matched]
        vocal_pitch = np.clip(np.round(feats.vocal_midi[frames]).astype(int), 0, 127)
        g = feats.guitar_mag[frames, pitch]
        v = feats.vocal_mag[frames, vocal_pitch]
        ratio = float(np.median(g / (v + EPS)))
    # Unison guard: guitar energy at this pitch right at the onset, against the
    # bleed the vocal alone would leave there.
    w = max(1, round(th.attack_window_sec / feats.hop_sec))
    lo, hi = a, min(n, a + w)
    gain = max(float(feats.bleed_gain or 0.0), th.bleed_gain_floor)
    vm_win = feats.vocal_midi[lo:hi]
    vocal_pitch = np.where(np.isfinite(vm_win), np.round(np.nan_to_num(vm_win)), pitch)
    vocal_pitch = np.clip(vocal_pitch.astype(int), 0, 127)
    # Frame by frame: the vocal often keeps swelling after the pluck has peaked.
    v_win = feats.vocal_mag[np.arange(lo, hi), vocal_pitch]
    floor = th.attack_floor * float(np.max(v_win)) + EPS
    attack = float(np.max(feats.guitar_mag[lo:hi, pitch] / (gain * v_win + floor)))
    return match, ratio, attack


def reject_vocal_bleed(
    notes: list[Any],
    features: DebleedFeatures,
    *,
    thresholds: DebleedThresholds = DEFAULT_THRESHOLDS,
) -> tuple[list[Any], PartDebleedReport]:
    """Return the notes to keep and a report of the ones removed (objects need pitch/start/end)."""
    kept: list[Any] = []
    removed: list[dict[str, Any]] = []
    for note in notes:
        match, ratio, attack = _note_evidence(note, features, thresholds)
        is_bleed = (
            match >= thresholds.match_min
            and ratio < thresholds.ratio_max
            and attack < thresholds.attack_excess
        )
        if is_bleed:
            removed.append(
                {
                    "start": round(float(note.start), 4),
                    "pitch": int(note.pitch),
                    "match": round(match, 3),
                    "ratio": round(ratio, 3),
                    "attack": round(min(attack, 1e6), 3),
                }
            )
        else:
            kept.append(note)
    return kept, PartDebleedReport(
        notes_in=len(notes),
        notes_removed=len(removed),
        removed=removed,
        thresholds=thresholds.to_dict(),
    )


def resolve_vocal_debleed(
    cfg: Any, vocals_path: Path | None, *, vocals_present: bool | None = None
) -> tuple[bool, str]:
    """Whether the stage runs, and why (recorded in diagnostics)."""
    mode = str(getattr(cfg, "vocal_debleed", "auto") or "auto").lower()
    if mode == "off":
        return False, "turned off in settings"
    if vocals_path is None or not Path(vocals_path).is_file():
        return False, "no vocals stem (solo or unseparated input)"
    if vocals_present is False:
        return False, "no singing detected in the vocals stem"
    if mode == "on":
        return True, "turned on in settings"
    if getattr(cfg, "separate_stems", False) and getattr(cfg, "mix_aware_filtering", False):
        return True, "auto: separated full mix with a vocals stem"
    return False, "auto: not a separated full mix"


# --- Vocal suppression before the Lead/Rhythm split -------------------------------------
# The split model files singing as "Lead" (a vocals-only input went ~99% to Lead in our
# measurements), so the vocal copy the separator left in the guitar stem lands in the Lead
# stem. Before the split, that copy is subtracted from the guitar stem the splitter sees.

SUPPRESS_N_FFT = 2048
SUPPRESS_HOP = 512
SUPPRESS_MASK_FLOOR = 0.1  # never cut a time-frequency cell by more than 20 dB


def subtract_vocal_bleed(
    guitar: np.ndarray, vocals: np.ndarray, bleed_gain: float
) -> tuple[np.ndarray, float]:
    """Power spectral subtraction of ``bleed_gain`` × |vocals| from each guitar channel.

    ``guitar`` is (samples, channels), ``vocals`` mono at the same rate. Only about the bleed
    level is removed wherever the vocal sounds, so guitar energy above it (a guitar note in
    unison with the voice) stays. Returns the cleaned audio and the mean gain applied, in dB.
    """
    import librosa

    n = guitar.shape[0]
    vocals = np.pad(vocals[:n], (0, max(0, n - len(vocals))))
    v_mag = np.abs(librosa.stft(vocals, n_fft=SUPPRESS_N_FFT, hop_length=SUPPRESS_HOP))
    out = np.empty_like(guitar)
    gains_db: list[float] = []
    for c in range(guitar.shape[1]):
        spec = librosa.stft(guitar[:, c], n_fft=SUPPRESS_N_FFT, hop_length=SUPPRESS_HOP)
        ratio = bleed_gain * v_mag / np.maximum(np.abs(spec), EPS)
        mask = np.sqrt(np.clip(1.0 - ratio**2, SUPPRESS_MASK_FLOOR**2, 1.0))
        out[:, c] = librosa.istft(mask * spec, hop_length=SUPPRESS_HOP, length=n)
        power = np.abs(spec) ** 2
        gains_db.append(
            float(10.0 * np.log10(np.sum(power * mask**2) / max(float(np.sum(power)), EPS)))
        )
    return out, float(np.mean(gains_db))


def guitar_for_split(
    cfg: Any, guitar_stem: Path, vocals_stem: Path | None, dest: Path
) -> tuple[Path, dict[str, Any]]:
    """The audio to feed the Lead/Rhythm splitter, and a report of what was done.

    Follows the vocal de-bleed setting. With a vocals stem and measurable bleed, ``dest`` gets
    the guitar stem with the vocal copy subtracted; otherwise, or if that fails, the guitar
    stem itself is returned and the report says why.
    """
    enabled, reason = resolve_vocal_debleed(cfg, vocals_stem)
    if not enabled:
        return Path(guitar_stem), {"applied": False, "reason": reason}
    try:
        return _subtract_into(Path(guitar_stem), Path(vocals_stem), Path(dest))
    except Exception as exc:  # the split still runs, on the unmodified guitar stem
        logger.warning("Vocal suppression before the Lead/Rhythm split failed: %s", exc)
        return Path(guitar_stem), {"applied": False, "reason": f"failed: {exc}"[:300]}


def _subtract_into(guitar_stem: Path, vocals_stem: Path, dest: Path) -> tuple[Path, dict[str, Any]]:
    import soundfile as sf

    feats = DebleedFeatures.from_audio(guitar_stem, vocals_stem)
    gain = feats.bleed_gain
    report: dict[str, Any] = {
        "applied": False,
        "bleed_gain": None if gain is None else round(float(gain), 4),
        "vocal_voiced_fraction": round(feats.voiced_fraction, 4),
    }
    if gain is None or gain < DEFAULT_THRESHOLDS.bleed_gain_floor:
        report["reason"] = "no measurable vocal bleed in the guitar stem"
        return guitar_stem, report
    import librosa

    guitar, sr = sf.read(str(guitar_stem), always_2d=True, dtype="float32")
    vocals, _ = librosa.load(str(vocals_stem), sr=sr, mono=True)
    cleaned, gain_db = subtract_vocal_bleed(guitar, vocals.astype(np.float32), float(gain))
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), cleaned, sr, subtype="FLOAT")
    report.update(applied=True, reason="vocal copy subtracted", guitar_gain_db=round(gain_db, 2))
    return dest, report
