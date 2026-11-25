"""Shared fakes: run the real analysis code against synthetic stems (no models)."""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 22050
STEMS = ("vocals", "drums", "bass", "guitar", "piano", "other")


def tone(path: Path, amp: float, freq: float = 220.0, seconds: float = 1.0) -> Path:
    t = np.arange(int(SR * seconds)) / SR
    sf.write(path, (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32), SR)
    return path


def patch_analysis_engine(
    monkeypatch,
    *,
    split_ok: bool = True,
    silent: tuple[str, ...] = ("piano",),
    gate: threading.Event | None = None,
    calls: list | None = None,
) -> None:
    import audio_to_tab.analysis as analysis
    from audio_to_tab.lead_rhythm_sep import LeadRhythmSplitDiagnostics, LeadRhythmSplitError

    def fake_normalize(src, dest):
        return tone(Path(dest), 0.3)

    def fake_download(url, out_dir):
        return tone(Path(out_dir) / "yt.wav", 0.3)

    def fake_sep(src, out_dir, **kwargs):
        if calls is not None:
            calls.append("separate")
        if gate is not None:
            gate.wait(5)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        return {n: tone(out_dir / f"{n}.wav", 0.0 if n in silent else 0.3) for n in STEMS}

    def fake_split(guitar_path, out_dir, *, device="cpu", on_progress=None):
        if not split_ok:
            raise LeadRhythmSplitError("Lead/rhythm split failed: test")
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        return (
            {
                "lead_guitar": tone(out_dir / "lead_guitar.wav", 0.3, 440.0),
                "rhythm_guitar": tone(out_dir / "rhythm_guitar.wav", 0.3, 110.0),
            },
            LeadRhythmSplitDiagnostics(attempted=True, reason="ok"),
        )

    monkeypatch.setattr(analysis, "normalize_audio", fake_normalize)
    monkeypatch.setattr(analysis, "download_youtube_audio", fake_download)
    monkeypatch.setattr(analysis, "run_full_separation", fake_sep)
    monkeypatch.setattr(analysis.lead_rhythm_sep, "run_lead_rhythm_split", fake_split)


def vocal_melody(path: Path, notes: list[tuple[int, float, float]], *, sr: int = SR,
                 seconds: float | None = None, amp: float = 0.3) -> Path:
    """Sine + 3 harmonics, 5.5 Hz vibrato at ±30 cents, 40 ms attack per note."""
    total = seconds if seconds is not None else max(e for _, _, e in notes) + 0.3
    out = np.zeros(int(sr * total))
    for pitch, start, end in notes:
        n = int(sr * (end - start))
        t = np.arange(n) / sr
        f0 = 440.0 * 2 ** ((pitch - 69) / 12)
        cents = 30.0 * np.sin(2 * np.pi * 5.5 * t)
        phase = 2 * np.pi * np.cumsum(f0 * 2 ** (cents / 1200)) / sr
        wave = sum((0.6 ** k) * np.sin((k + 1) * phase) for k in range(4))
        env = np.minimum(1.0, t / 0.04) * np.minimum(1.0, (n - np.arange(n)) / (0.03 * sr))
        i = int(sr * start)
        out[i : i + n] += amp * wave * env
    sf.write(path, out.astype(np.float32), sr)
    return path


def drum_pattern(path: Path, hits: list[tuple[str, float]], *, sr: int = SR,
                 seconds: float = 2.2, seed: int = 0) -> Path:
    from scipy.signal import butter, sosfilt

    rng = np.random.default_rng(seed)
    out = np.zeros(int(sr * seconds))
    hp = butter(6, 7000, "highpass", fs=sr, output="sos")
    bp = butter(4, [250, 2000], "bandpass", fs=sr, output="sos")
    for piece, start in hits:
        i = int(sr * start)
        if piece == "kick":
            n = int(0.18 * sr)
            t = np.arange(n) / sr
            freq = 50 + 60 * np.exp(-t * 30)
            wave = np.sin(2 * np.pi * np.cumsum(freq) / sr) * np.exp(-t * 18)
        elif piece == "snare":
            n = int(0.15 * sr)
            t = np.arange(n) / sr
            noise = sosfilt(bp, rng.standard_normal(n))
            wave = (0.8 * noise / (np.abs(noise).max() + 1e-9) + 0.5 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 25)
        else:
            n = int(0.06 * sr)
            t = np.arange(n) / sr
            noise = sosfilt(hp, rng.standard_normal(n))
            wave = 0.6 * noise / (np.abs(noise).max() + 1e-9) * np.exp(-t * 70)
        seg = out[i : i + n]
        seg += 0.6 * wave[: len(seg)]
    sf.write(path, out.astype(np.float32), sr)
    return path
