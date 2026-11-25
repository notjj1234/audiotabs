"""Deterministic synthetic audio for the vocal de-bleed evidence (no copyrighted audio)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf

SR = 22050
BLEED_GAIN = 0.3  # vocal copy left in the guitar stem (≈ −10 dB)

# 16 guitar notes (pitch, start, end). Note 9 (A4 = 69 at 4.5 s) is played in
# unison with the singer — the de-bleed must keep it.
GUITAR_NOTES: list[tuple[int, float, float]] = [
    (p, 0.5 + i * 0.5, 0.5 + i * 0.5 + 0.42)
    for i, p in enumerate([40, 47, 52, 55, 45, 52, 57, 60, 69, 43, 50, 55, 59, 48, 55, 52])
]
# 12 vocal notes, pitches disjoint from the guitar line except the unison A4.
VOCAL_NOTES: list[tuple[int, float, float]] = [
    (74, 0.6, 1.0), (76, 1.1, 1.5), (78, 1.6, 2.1), (79, 2.2, 2.7),
    (81, 2.8, 3.3), (77, 3.4, 3.9), (73, 4.0, 4.4), (69, 4.5, 4.95),
    (71, 5.1, 5.6), (75, 5.7, 6.2), (80, 6.3, 6.9), (76, 7.0, 7.6),
]
UNISON = (69, 4.5)
SECONDS = 9.0


def pluck(freq: float, dur: float, sr: int = SR, seed: int = 0) -> np.ndarray:
    """Karplus–Strong plucked string, seeded so every run is identical."""
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    period = max(2, int(round(sr / freq)))
    buf = rng.uniform(-1.0, 1.0, period)
    out = np.empty(n)
    for i in range(n):
        out[i] = buf[i % period]
        buf[i % period] = 0.996 * 0.5 * (buf[i % period] + buf[(i + 1) % period])
    return out / (np.max(np.abs(out)) + 1e-9)


def _guitar(sr: int = SR) -> np.ndarray:
    y = np.zeros(int(SECONDS * sr))
    for k, (pitch, start, end) in enumerate(GUITAR_NOTES):
        tone = 0.5 * pluck(440.0 * 2 ** ((pitch - 69) / 12), end - start, sr, seed=k)
        i = int(start * sr)
        y[i : i + len(tone)] += tone
    return y


def _vocal(sr: int = SR) -> np.ndarray:
    from tests.analysis_fakes import vocal_melody  # same vibrato voice as the notation tests

    tmp = Path(__import__("tempfile").mkdtemp()) / "v.wav"
    vocal_melody(tmp, VOCAL_NOTES, sr=sr, seconds=SECONDS, amp=0.35)
    y, _ = sf.read(tmp)
    return y


def _midi(path: Path, notes: list[tuple[int, float, float]]) -> Path:
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=25)
    inst.notes = [pretty_midi.Note(90, p, s, e) for p, s, e in notes]
    pm.instruments.append(inst)
    pm.write(str(path))
    return path


def make_bleed_fixture(out: Path) -> tuple[Path, Path, Path, Path]:
    """(guitar_stem_with_bleed, vocals_stem, guitar_ref.mid, vocal_ref.mid)."""
    out.mkdir(parents=True, exist_ok=True)
    guitar, vocal = _guitar(), _vocal()
    stem = guitar + BLEED_GAIN * vocal
    stem = stem / max(1.0, float(np.max(np.abs(stem))) / 0.95)
    g_path = out / "guitar_stem.wav"
    v_path = out / "vocals.wav"
    sf.write(g_path, stem.astype(np.float32), SR)
    sf.write(v_path, vocal.astype(np.float32), SR)
    return g_path, v_path, _midi(out / "guitar_ref.mid", GUITAR_NOTES), _midi(out / "vocal_ref.mid", VOCAL_NOTES)
