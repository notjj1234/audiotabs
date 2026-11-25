"""Lead/rhythm role evidence in lead_rhythm.py: texture first, ambiguous over wrong.

Covers the role spec's acceptance tests: F2/F5 features, tier-capped scoring,
tie -> ambiguous, register-only difference refused, mono / duplicated material
refused, empty or short stems skipped.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab import lead_rhythm as lr
from audio_to_tab.lead_rhythm import (
    LOW_TIER_FEATURES,
    ROLE_MARGIN_MIN,
    ROLE_WEIGHTS,
    RoleFeatures,
    classify_lead_rhythm_roles,
    extract_role_features_from_notes,
    pitch_class_change_rate,
    salience_stats,
    split_lead_rhythm_guitar,
)

SR = 22050


@dataclass
class N:
    pitch: int
    start: float
    end: float
    velocity: int = 80


def triad_stream(bars: int = 4) -> list[N]:
    """Strummed E minor, eight strums per bar: same pitch classes every attack."""
    notes = []
    for k in range(bars * 8):
        t = k * 0.25
        notes.extend(N(p, t, t + 0.24) for p in (52, 55, 59, 64))
    return notes


def moving_line(bars: int = 4) -> list[N]:
    # No two neighbours share a pitch class, including the wrap from the top back down.
    scale = [64, 66, 67, 69, 71, 72, 74, 75]
    return [N(scale[k % 8], k * 0.25, k * 0.25 + 0.24) for k in range(bars * 8)]


def tone(midis: list[int], sec: float = 3.0) -> np.ndarray:
    t = np.arange(int(SR * sec)) / SR
    y = np.zeros_like(t)
    for m in midis:
        f = 440 * 2 ** ((m - 69) / 12)
        for h in range(1, 9):
            y += (0.7 ** (h - 1)) * np.sin(2 * np.pi * f * h * t)
    env = np.minimum(1.0, np.minimum(t / 0.005, (sec - t) / 0.02))
    return (y * env / np.max(np.abs(y)) * 0.5).astype(np.float32)


def line_audio(midis: list[int], each: float = 0.25, reps: int = 3) -> np.ndarray:
    return np.concatenate([tone([m], each) for _ in range(reps) for m in midis])


# --- F2 pitch_class_change_rate -------------------------------------------------------------


def test_f2_strumming_repeats_pitch_classes_and_a_line_changes_them():
    assert pitch_class_change_rate(triad_stream()) == 0.0
    assert pitch_class_change_rate(moving_line()) == 1.0
    assert pitch_class_change_rate([N(60, 0, 1)]) is None


def test_f2_is_part_of_note_features():
    feats = extract_role_features_from_notes(triad_stream(), duration_sec=8.0)
    assert feats.pitch_class_change_rate == 0.0
    assert feats.to_dict()["pitch_class_change_rate"] == 0.0


# --- F5 salience_concentration ----------------------------------------------------------------


@pytest.mark.parametrize("midis", [[57], [40], [64]])
def test_f5_single_notes_have_one_dominant_peak_at_any_register(midis):
    stats = salience_stats(tone(midis), SR)
    assert stats.peak_count == 1
    assert stats.single_peak_share > 0.9


@pytest.mark.parametrize("midis", [[40, 47], [52, 55, 59], [40, 47, 52, 56, 59, 64]])
def test_f5_chords_have_competing_peaks(midis):
    stats = salience_stats(tone(midis), SR)
    assert stats.peak_count >= 2
    assert stats.single_peak_share < 0.1


def test_f5_moving_line_reads_as_one_voice_and_beats_a_chord_on_concentration():
    line = salience_stats(line_audio([64, 66, 67, 69, 71, 69, 67, 66]), SR)
    chord = salience_stats(tone([52, 55, 59]), SR)
    assert line.peak_count == 1
    assert line.concentration > chord.concentration


def test_power_chord_is_not_confident_monophonic():
    # The old single-FFT-peak proxy called this "confident"; F5 does not.
    _, confidence = lr._dominant_pitch_estimate(tone([40, 47]), SR)
    assert confidence < lr.PITCH_CONFIDENCE_MIN
    freq, confidence = lr._dominant_pitch_estimate(tone([57]), SR)
    assert confidence >= lr.PITCH_CONFIDENCE_MIN
    assert freq == pytest.approx(220, rel=0.03)


# --- scoring ----------------------------------------------------------------------------------


def test_low_evidence_tiers_are_capped_at_ten_percent():
    total = sum(w for w, _ in ROLE_WEIGHTS.values())
    low = sum(ROLE_WEIGHTS[name][0] for name in LOW_TIER_FEATURES)
    assert low / total <= 0.10 + 1e-9
    assert ROLE_WEIGHTS["pitch_median"][0] <= 0.10
    assert all(tier for _, tier in ROLE_WEIGHTS.values())


def test_repeated_triads_vs_moving_line_assigns_roles_above_the_floor():
    rhythm = extract_role_features_from_notes(triad_stream(), duration_sec=8.0)
    lead = extract_role_features_from_notes(moving_line(), duration_sec=8.0)
    assignment, margin, detail = classify_lead_rhythm_roles(rhythm, lead)
    assert assignment == "b_lead"
    assert margin >= ROLE_MARGIN_MIN
    assert detail["texture_margin"] >= ROLE_MARGIN_MIN
    assert "pitch_class_change_rate" in detail["features_used"]


def test_tied_evidence_is_ambiguous_not_lead():
    feats = extract_role_features_from_notes(moving_line(), duration_sec=8.0)
    assignment, margin, _ = classify_lead_rhythm_roles(feats, feats, margin_min=0.0)
    assert assignment == "ambiguous"
    assert margin == 0.0


def test_register_alone_cannot_carry_a_role_decision():
    low = RoleFeatures(45.0, 6.0, 4.0, 1.2, 80.0, 0.3, pitch_class_change_rate=0.8)
    high = RoleFeatures(78.0, 6.0, 4.0, 1.2, 80.0, 0.3, pitch_class_change_rate=0.8)
    assignment, margin, detail = classify_lead_rhythm_roles(low, high)
    assert detail["texture_margin"] == 0.0
    assert assignment == "ambiguous"
    assert margin < ROLE_MARGIN_MIN


# --- split decisions on audio -----------------------------------------------------------------


def _write(path: Path, left: np.ndarray, right: np.ndarray) -> Path:
    n = min(len(left), len(right))
    sf.write(str(path), np.column_stack([left[:n], right[:n]]), SR, subtype="PCM_16")
    return path


def _assert_no_role_wavs(out: dict, out_dir: Path):
    assert "lead_guitar" not in out and "rhythm_guitar" not in out
    assert not (out_dir / "lead_guitar.wav").exists()
    assert not (out_dir / "rhythm_guitar.wav").exists()


def test_mono_identical_channels_are_ambiguous_and_write_no_wavs(tmp_path):
    sig = np.concatenate([tone([52, 55, 59], 2.0), line_audio([64, 66, 67, 69], 0.25, 2)])
    path = _write(tmp_path / "guitar.wav", sig, sig)
    for mode in ("confident", "best_effort"):
        out_dir = tmp_path / mode
        out, diag = split_lead_rhythm_guitar(path, out_dir, use_basic_pitch=False, emit_mode=mode)
        assert diag.outcome == "ambiguous", (mode, diag.reason)
        _assert_no_role_wavs(out, out_dir)


def test_hard_panned_duplicate_of_the_same_part_is_refused(tmp_path):
    sig = line_audio([64, 66, 67, 69, 71, 69, 67, 66], 0.25, 2)
    delayed = np.r_[np.zeros(int(0.015 * SR), dtype=np.float32), sig][: len(sig)]
    path = _write(tmp_path / "guitar.wav", sig, delayed)
    out, diag = split_lead_rhythm_guitar(path, tmp_path / "out", use_basic_pitch=False)
    assert diag.outcome == "ambiguous", diag.reason
    _assert_no_role_wavs(out, tmp_path / "out")


def test_tie_is_refused_even_in_best_effort_mode(tmp_path, monkeypatch):
    left = tone([52, 55, 59], 4.0)
    right = line_audio([64, 66, 67, 69, 71, 69, 67, 66], 0.25, 2)
    path = _write(tmp_path / "guitar.wav", left, right)
    same = RoleFeatures(60.0, 6.0, 4.0, 2.0, 80.0, 0.3, pitch_class_change_rate=0.5)
    monkeypatch.setattr(lr, "_features_from_audio_stats", lambda *a, **k: same)
    out, diag = split_lead_rhythm_guitar(
        path, tmp_path / "out", use_basic_pitch=False, emit_mode="best_effort"
    )
    assert diag.outcome == "ambiguous"
    assert "tied" in diag.reason
    _assert_no_role_wavs(out, tmp_path / "out")


@pytest.mark.parametrize("seconds", [0.0, 0.2])
def test_empty_or_very_short_stem_is_skipped(tmp_path, seconds):
    sig = tone([57], seconds) if seconds else np.zeros(SR * 2, dtype=np.float32)
    path = _write(tmp_path / "guitar.wav", sig, sig)
    out, diag = split_lead_rhythm_guitar(path, tmp_path / "out", use_basic_pitch=False)
    assert diag.outcome == "skipped"
    _assert_no_role_wavs(out, tmp_path / "out")
    assert "constants" in diag.features


def test_diagnostics_list_uncalibrated_constants_and_feature_trace(tmp_path):
    left = tone([52, 55, 59], 4.0)
    right = line_audio([64, 66, 67, 69, 71, 69, 67, 66], 0.25, 2)
    path = _write(tmp_path / "guitar.wav", left, right)
    _, diag = split_lead_rhythm_guitar(path, tmp_path / "out", use_basic_pitch=False)
    if diag.method == "none":
        pytest.skip("no candidate pair built for this synthetic input")
    constants = diag.features["constants"]
    assert all(v.startswith(("CALIBRATED", "UNCALIBRATED")) for v in constants.values())
    assert constants["ROLE_WEIGHTS"].startswith("UNCALIBRATED")
    for side in ("stream_a", "stream_b"):
        assert "salience_peaks" in diag.features[side]
        assert "pitch_class_change_rate" in diag.features[side]


def test_hard_panned_strum_and_moving_line_are_split_with_the_line_as_lead(tmp_path):
    strum = np.concatenate([tone([52, 55, 59, 64], 0.25) for _ in range(24)])
    line = line_audio([64, 66, 67, 69, 71, 72, 74, 75], 0.25, 3)
    path = _write(tmp_path / "guitar.wav", strum, line)
    out, diag = split_lead_rhythm_guitar(path, tmp_path / "out", use_basic_pitch=False)
    assert diag.outcome == "lead_rhythm", diag.reason
    assert diag.role_confidence >= ROLE_MARGIN_MIN
    assert diag.features["score_b_lead"] > diag.features["score_a_lead"]  # right = the line
    assert out["lead_guitar"].exists() and out["rhythm_guitar"].exists()
