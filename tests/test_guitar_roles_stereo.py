"""Stereo pre-split: centre sine vs decorrelated side noise, mono pass-through."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.guitar_roles_stereo import (
    StereoSplitConfig,
    centre_weight,
    pan_index,
    stereo_presplit,
)

SR = 44100


def _energy(x: np.ndarray) -> float:
    return float(np.sum(x.astype(np.float64) ** 2))


def _centre_sine_side_noise(seconds: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    t = np.arange(int(SR * seconds)) / SR
    sine = 0.3 * np.sin(2 * np.pi * 440 * t)
    left_noise, right_noise = 0.1 * rng.standard_normal(len(t)), 0.1 * rng.standard_normal(len(t))
    centre = np.column_stack([sine, sine])
    side = np.column_stack([left_noise, np.zeros_like(t)]) + np.column_stack([np.zeros_like(t), right_noise])
    return (centre + side).astype(np.float32), centre, side


def test_centre_weight_shape():
    p = np.array([0.0, 0.2, 0.4, 0.6, 1.0, -0.4])
    assert np.allclose(centre_weight(p), [1.0, 1.0, 0.5, 0.0, 0.0, 0.5])


def test_pan_index_signs():
    assert pan_index(np.array([1.0]), np.array([0.0]))[0] == pytest.approx(-1.0)
    assert pan_index(np.array([0.0]), np.array([1.0]))[0] == pytest.approx(1.0)
    assert pan_index(np.array([1.0]), np.array([1.0]))[0] == pytest.approx(0.0)


def test_centre_sine_goes_to_lead_and_side_noise_to_rhythm(tmp_path):
    mix, centre_true, side_true = _centre_sine_side_noise()
    src = tmp_path / "guitar.wav"
    sf.write(src, mix, SR)

    res = stereo_presplit(src, tmp_path / "out")

    assert res.skipped is False
    lead, _ = sf.read(res.lead_candidate, always_2d=True)
    rhythm, _ = sf.read(res.rhythm_candidate, always_2d=True)
    assert lead.shape == rhythm.shape == mix.shape
    # The masks are complementary: the two candidates add back to the input.
    assert np.max(np.abs(lead + rhythm - mix)) < 1e-3
    # Most of the sine lands in the lead candidate, most of the noise in the rhythm candidate.
    lead_spec = np.abs(np.fft.rfft(lead[:, 0], n=4096 * 8))
    assert _energy(lead - centre_true) < 0.2 * _energy(side_true)
    assert _energy(rhythm - side_true) < 0.2 * _energy(side_true)
    assert lead_spec.argmax() * SR / (4096 * 8) == pytest.approx(440, abs=3)
    assert 0.0 < res.centre_energy_share < 1.0


def test_pan_only_mask_files_hard_panned_independent_noise_as_centre(tmp_path):
    """Why coherence is on: without it, half the side noise leaks into the lead candidate."""
    mix, centre_true, side_true = _centre_sine_side_noise()
    src = tmp_path / "guitar.wav"
    sf.write(src, mix, SR)

    pan_only = stereo_presplit(src, tmp_path / "pan", StereoSplitConfig(use_coherence=False))
    lead, _ = sf.read(pan_only.lead_candidate, always_2d=True)

    assert _energy(lead - centre_true) > 0.3 * _energy(side_true)


def test_near_mono_stem_passes_through(tmp_path):
    t = np.arange(SR) / SR
    sine = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    src = tmp_path / "mono_ish.wav"
    sf.write(src, np.column_stack([sine, sine * 0.98]), SR)

    res = stereo_presplit(src, tmp_path / "out")

    assert res.skipped is True
    assert "near-mono" in res.reason
    assert res.lr_correlation > StereoSplitConfig().mono_corr
    assert res.lead_candidate is None and not (tmp_path / "out").exists()


def test_single_channel_file_passes_through(tmp_path):
    src = tmp_path / "mono.wav"
    sf.write(src, np.zeros(SR, dtype=np.float32), SR)
    res = stereo_presplit(src, tmp_path / "out")
    assert res.skipped is True and res.reason == "mono file"
