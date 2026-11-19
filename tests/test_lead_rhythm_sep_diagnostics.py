"""Diagnostics math for the lead/rhythm split stage (Task 2)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.lead_rhythm_sep import (
    CORRELATION_WARN,
    MIN_INPUT_SEC,
    NEAR_SILENT_DBFS,
    LeadRhythmSplitDiagnostics,
    analyze_lead_rhythm_stems,
    integrated_loudness_lufs,
    pearson_rms_correlation,
)

SR = 44100


def _sine(path, freq=1000.0, amp=0.5, seconds=6.0, sr=SR, channels=2):
    t = np.arange(int(seconds * sr)) / sr
    data = amp * np.sin(2 * np.pi * freq * t)
    if channels == 2:
        data = np.column_stack([data, data])
    sf.write(str(path), data.astype(np.float32), sr)
    return path


def _noise(path, amp=0.5, seconds=6.0, sr=SR, seed=7):
    rng = np.random.default_rng(seed)
    data = amp * rng.uniform(-1.0, 1.0, int(seconds * sr))
    data = np.column_stack([data, data]).astype(np.float32)
    sf.write(str(path), data, sr)
    return path


class TestDiagnosticsMath:
    def test_rms_and_peak(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav", amp=0.1)
        rhythm = _noise(tmp_path / "rhythm.wav", amp=0.3)
        diag = analyze_lead_rhythm_stems(lead, rhythm)
        expected_rms = 20 * math.log10(0.1 / math.sqrt(2))
        assert abs(diag.lead.rms_dbfs - expected_rms) < 0.5
        assert abs(diag.lead.peak - 0.1) < 1e-3
        assert diag.rhythm.peak <= 0.31

    def test_spectral_centroid(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav", freq=1000.0)
        rhythm = _noise(tmp_path / "rhythm.wav")
        diag = analyze_lead_rhythm_stems(lead, rhythm)
        assert abs(diag.lead.spectral_centroid_hz - 1000.0) < 150.0

    def test_silence_ratio_bounds(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav")
        rhythm = _noise(tmp_path / "rhythm.wav")
        diag = analyze_lead_rhythm_stems(lead, rhythm)
        assert 0.0 <= diag.lead.silence_ratio <= 1.0
        assert diag.lead.silence_ratio < 0.1

    def test_silence_ratio_all_silent(self, tmp_path):
        zeros = np.zeros((SR * 6, 2), dtype=np.float32)
        lead = tmp_path / "lead.wav"
        rhythm = tmp_path / "rhythm.wav"
        sf.write(str(lead), zeros, SR)
        sf.write(str(rhythm), zeros, SR)
        diag = analyze_lead_rhythm_stems(lead, rhythm)
        assert diag.lead.silence_ratio == 1.0
        assert any("near-silent" in w for w in diag.warnings)
        assert diag.lead.rms_dbfs < NEAR_SILENT_DBFS

    def test_correlation_identical_warns(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav")
        rhythm = tmp_path / "rhythm.wav"
        import shutil

        shutil.copy2(lead, rhythm)
        diag = analyze_lead_rhythm_stems(lead, rhythm)
        assert diag.envelope_correlation > 0.99
        assert CORRELATION_WARN == 0.85
        assert any("correlation" in w for w in diag.warnings)

    def test_correlation_independent_no_warn(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav")
        rhythm = _noise(tmp_path / "rhythm.wav", seed=99)
        diag = analyze_lead_rhythm_stems(lead, rhythm)
        assert abs(diag.envelope_correlation) < 0.2
        assert not any("correlation" in w for w in diag.warnings)

    def test_clipped_input_warns(self, tmp_path):
        t = np.arange(SR * 6) / SR
        square = np.sign(np.sin(2 * np.pi * 220 * t)) * 1.0
        square = np.column_stack([square, square]).astype(np.float32)
        lead = tmp_path / "lead.wav"
        rhythm = tmp_path / "rhythm.wav"
        sf.write(str(lead), square, SR)
        sf.write(str(rhythm), np.column_stack([0.1 * square[:, 0], 0.1 * square[:, 0]]).astype(np.float32), SR)
        diag = analyze_lead_rhythm_stems(lead, rhythm, input_path=lead)
        assert any("clip" in w for w in diag.warnings)

    def test_clean_input_no_clip_warn(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav", amp=0.5)
        rhythm = _noise(tmp_path / "rhythm.wav", amp=0.3)
        diag = analyze_lead_rhythm_stems(lead, rhythm, input_path=lead)
        assert not any("clip" in w for w in diag.warnings)

    def test_short_input_warns(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav", seconds=1.0)
        rhythm = _noise(tmp_path / "rhythm.wav", seconds=1.0)
        diag = analyze_lead_rhythm_stems(lead, rhythm)
        assert diag.input_duration_sec < MIN_INPUT_SEC
        assert any("short" in w for w in diag.warnings)

    def test_mono_input_warns(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav", channels=1)
        rhythm = _sine(tmp_path / "rhythm.wav", freq=440.0, channels=1)
        diag = analyze_lead_rhythm_stems(lead, rhythm, input_path=lead)
        assert diag.input_channels == 1
        assert any("mono" in w for w in diag.warnings)

    def test_write_json_round_trip(self, tmp_path):
        lead = _sine(tmp_path / "lead.wav")
        rhythm = _noise(tmp_path / "rhythm.wav")
        diag = analyze_lead_rhythm_stems(lead, rhythm)
        out = diag.write_json(tmp_path / "diag.json")
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["model_sample_rate"] == diag.model_sample_rate
        assert payload["warnings"] == diag.warnings
        assert payload["lead"]["rms_dbfs"] == pytest.approx(diag.lead.rms_dbfs)
        assert isinstance(LeadRhythmSplitDiagnostics.from_dict(payload), LeadRhythmSplitDiagnostics)


class TestLoudness:
    def test_full_scale_sine_near_bs1770_reference(self, tmp_path):
        # 997 Hz full-scale sine: BS.1770 gated loudness ≈ -3.0 LUFS.
        sr = 48000
        t = np.arange(int(3.0 * sr)) / sr
        sine = (0.999 * np.sin(2 * np.pi * 997 * t)).astype(np.float32)
        value = integrated_loudness_lufs(sine, sr)
        assert -5.5 <= value <= -0.5

    def test_silence_is_gated_to_floor(self, tmp_path):
        value = integrated_loudness_lufs(np.zeros(SR * 2, dtype=np.float32), SR)
        assert value <= -69.0

    def test_quieter_signal_lower_loudness(self, tmp_path):
        sr = SR
        t = np.arange(int(2.0 * sr)) / sr
        loud = (0.9 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        quiet = (0.05 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        assert integrated_loudness_lufs(quiet, sr) < integrated_loudness_lufs(loud, sr) - 10.0


class TestEnvelopeCorrelation:
    def test_identical_arrays(self):
        rng = np.random.default_rng(3)
        x = rng.standard_normal(SR * 4).astype(np.float32)
        assert pearson_rms_correlation(x, x.copy(), SR) > 0.99

    def test_too_short_returns_none(self):
        x = np.zeros(100, dtype=np.float32)
        assert pearson_rms_correlation(x, x.copy(), SR) is None

    def test_mismatched_lengths_padded(self):
        rng = np.random.default_rng(5)
        x = rng.standard_normal(SR * 4).astype(np.float32)
        y = rng.standard_normal(SR * 3).astype(np.float32)
        r = pearson_rms_correlation(x, y, SR)
        assert r is not None and -1.0 <= r <= 1.0
