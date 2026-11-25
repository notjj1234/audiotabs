"""Vocal de-bleed: note-level rejection with a unison guard (no audio models needed)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import soundfile as sf

from audio_to_tab.pipeline import PipelineConfig
from audio_to_tab.vocal_debleed import (
    DEFAULT_THRESHOLDS,
    DebleedFeatures,
    guitar_for_split,
    reject_vocal_bleed,
    resolve_vocal_debleed,
    subtract_vocal_bleed,
)

HOP = 0.01
N = 400  # 4 s


@dataclass
class N_:
    pitch: int
    start: float
    end: float


def _features(*, vocal: list[tuple[int, float, float]], guitar_level: dict[int, float],
              vocal_level: float = 1.0, plucks: list[tuple[int, float]] = (),
              bleed_gain: float = 0.3) -> DebleedFeatures:
    """Synthetic evidence. ``plucks`` = (pitch, time): a guitar attack at that pitch."""
    vocal_midi = np.full(N, np.nan)
    g = np.zeros((N, 128))
    v = np.zeros((N, 128))
    for pitch, a, b in vocal:
        i, j = int(a / HOP), int(b / HOP)
        vocal_midi[i:j] = pitch
        v[i:j, pitch] = vocal_level
    for pitch, level in guitar_level.items():
        g[:, pitch] = level
    for pitch, t in plucks:
        i = int(t / HOP)
        g[i : i + 4, pitch] += 1.5  # 40 ms attack well above what bleed explains
    return DebleedFeatures(
        hop_sec=HOP, vocal_midi=vocal_midi, guitar_mag=g, vocal_mag=v,
        onset=np.zeros(N), bleed_gain=bleed_gain,
    )


def test_bleed_copy_of_the_singer_is_removed():
    feats = _features(vocal=[(69, 1.0, 1.6)], guitar_level={69: 0.3})
    kept, report = reject_vocal_bleed([N_(69, 1.0, 1.5), N_(40, 1.0, 1.5)], feats)
    assert [n.pitch for n in kept] == [40]
    assert report.notes_in == 2 and report.notes_removed == 1
    assert report.removed[0]["pitch"] == 69


def test_real_unison_guitar_with_its_own_pluck_is_kept():
    # Steady level equals the bleed (ratio 0.3), but the guitar attacks the note itself.
    feats = _features(vocal=[(69, 1.0, 1.6)], guitar_level={69: 0.3}, plucks=[(69, 1.0)])
    kept, _ = reject_vocal_bleed([N_(69, 1.0, 1.5)], feats)
    assert len(kept) == 1


def test_an_attack_at_another_pitch_does_not_save_a_bleed_note():
    # A different guitar note plucked at the same moment is not evidence for this one.
    feats = _features(vocal=[(69, 1.0, 1.6)], guitar_level={69: 0.3}, plucks=[(45, 1.0)])
    kept, _ = reject_vocal_bleed([N_(69, 1.0, 1.5)], feats)
    assert kept == []


def test_loud_unison_guitar_without_clear_pluck_is_kept():
    feats = _features(vocal=[(69, 1.0, 1.6)], guitar_level={69: 0.9})
    kept, _ = reject_vocal_bleed([N_(69, 1.0, 1.5)], feats)
    assert len(kept) == 1


def test_octave_error_of_the_vocal_is_removed():
    feats = _features(vocal=[(69, 1.0, 1.6)], guitar_level={57: 0.2})
    kept, _ = reject_vocal_bleed([N_(57, 1.0, 1.5)], feats)
    assert kept == []


def test_notes_off_the_vocal_pitch_are_never_touched():
    feats = _features(vocal=[(69, 1.0, 1.6)], guitar_level={64: 0.05})
    kept, _ = reject_vocal_bleed([N_(64, 1.0, 1.5)], feats)
    assert len(kept) == 1


def test_thresholds_are_reported():
    feats = _features(vocal=[], guitar_level={})
    _, report = reject_vocal_bleed([], feats)
    assert report.thresholds == DEFAULT_THRESHOLDS.to_dict()


def test_gate_auto_needs_a_separated_full_mix_with_vocals(tmp_path):
    vocals = tmp_path / "vocals.wav"
    vocals.write_bytes(b"x")
    full = PipelineConfig(separate_stems=True, mix_aware_filtering=True)
    assert resolve_vocal_debleed(full, vocals)[0] is True
    assert resolve_vocal_debleed(full, None)[0] is False
    assert resolve_vocal_debleed(full, tmp_path / "missing.wav")[0] is False
    solo = PipelineConfig(separate_stems=False, mix_aware_filtering=False)
    assert resolve_vocal_debleed(solo, vocals)[0] is False
    off = PipelineConfig(separate_stems=True, mix_aware_filtering=True, vocal_debleed="off")
    enabled, reason = resolve_vocal_debleed(off, vocals)
    assert enabled is False and "off" in reason
    on = PipelineConfig(separate_stems=True, mix_aware_filtering=False, vocal_debleed="on")
    assert resolve_vocal_debleed(on, vocals)[0] is True
    assert resolve_vocal_debleed(full, vocals, vocals_present=False)[0] is False


def test_unison_attack_counts_even_while_the_vocal_is_still_swelling():
    # Guitar attacks at the note start; the singer's level keeps rising after it
    # (the real fixture's shape). Comparing window maxima hid the attack.
    feats = _features(vocal=[(69, 1.0, 1.6)], guitar_level={})
    i = int(1.0 / HOP)
    ramp = np.linspace(0.1, 5.0, 8)
    feats.vocal_mag[i : i + 8, 69] = ramp
    feats.guitar_mag[i : i + 8, 69] = 0.3 * ramp
    feats.guitar_mag[i : i + 2, 69] += 0.8  # pluck peaks before the vocal does
    feats.guitar_mag[i + 8 : i + 60, 69] = 0.3 * 5.0
    feats.vocal_mag[i + 8 : i + 60, 69] = 5.0
    kept, _ = reject_vocal_bleed([N_(69, 1.0, 1.5)], feats)
    assert len(kept) == 1


# --- vocal suppression before the Lead/Rhythm split -----------------------------------------

SPLIT_SR = 44100


def _sine(hz: float, seconds: float = 2.0, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * SPLIT_SR)) / SPLIT_SR
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def _voice(seconds: float = 2.0) -> np.ndarray:
    return sum(_sine(440.0 * k, seconds, 0.3 / k) for k in (1, 2, 3)).astype(np.float32)


def _band_db(x: np.ndarray, hz: float) -> float:
    spec = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1 / SPLIT_SR)
    return float(10 * np.log10(np.sum(spec[np.abs(freqs - hz) < 5] ** 2) + 1e-12))


def test_vocal_copy_is_subtracted_and_the_guitar_note_stays():
    voice, note = _sine(440.0), _sine(196.0)
    guitar = np.column_stack([note + 0.3 * voice] * 2)

    cleaned, gain_db = subtract_vocal_bleed(guitar, voice, 0.3)

    assert _band_db(guitar[:, 0], 440) - _band_db(cleaned[:, 0], 440) > 12
    assert abs(_band_db(guitar[:, 0], 196) - _band_db(cleaned[:, 0], 196)) < 1
    assert gain_db < 0


def test_split_input_subtracts_the_measured_vocal_copy(tmp_path):
    voice, note = _voice(), _sine(196.0)
    guitar_path, vocals_path = tmp_path / "guitar.wav", tmp_path / "vocals.wav"
    sf.write(str(guitar_path), np.column_stack([note + 0.3 * voice] * 2), SPLIT_SR)
    sf.write(str(vocals_path), np.column_stack([voice] * 2), SPLIT_SR)
    cfg = PipelineConfig(separate_stems=True, mix_aware_filtering=True)

    path, report = guitar_for_split(cfg, guitar_path, vocals_path, tmp_path / "split_in.wav")

    assert report["applied"] is True and path == tmp_path / "split_in.wav"
    assert 0.15 < report["bleed_gain"] < 0.5
    cleaned, sr = sf.read(str(path), always_2d=True)
    assert sr == SPLIT_SR
    assert _band_db(note + 0.3 * voice, 440) - _band_db(cleaned[:, 0], 440) > 10
    assert abs(_band_db(note, 196) - _band_db(cleaned[:, 0], 196)) < 1


def test_split_input_is_the_guitar_stem_when_turned_off_or_without_vocals(tmp_path):
    guitar = tmp_path / "guitar.wav"
    sf.write(str(guitar), np.zeros((4410, 2), dtype=np.float32), SPLIT_SR)
    vocals = tmp_path / "vocals.wav"
    sf.write(str(vocals), np.zeros((4410, 2), dtype=np.float32), SPLIT_SR)

    off = PipelineConfig(separate_stems=True, vocal_debleed="off")
    path, report = guitar_for_split(off, guitar, vocals, tmp_path / "out.wav")
    assert path == guitar and report == {"applied": False, "reason": "turned off in settings"}

    auto = PipelineConfig(separate_stems=True, mix_aware_filtering=True)
    path, report = guitar_for_split(auto, guitar, tmp_path / "missing.wav", tmp_path / "out.wav")
    assert path == guitar and report["applied"] is False
    assert not (tmp_path / "out.wav").exists()
