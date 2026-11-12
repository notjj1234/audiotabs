"""Mix-aware transcription floor coupling (solo vs separated)."""

from __future__ import annotations

from audio_to_tab.pipeline import (
    PipelineConfig,
    _cleanup_config_for_pipeline,
    _transcription_thresholds,
)


def test_transcription_thresholds_solo_ignores_mix_aware_floors():
    cfg = PipelineConfig(
        mix_aware_filtering=True,
        separate_stems=False,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length_ms=58.0,
    )
    onset, frame, min_len = _transcription_thresholds(cfg)
    assert onset == 0.5
    assert frame == 0.3
    assert min_len == 58.0


def test_transcription_thresholds_separated_mix_aware_keeps_floors():
    cfg = PipelineConfig(
        mix_aware_filtering=True,
        separate_stems=True,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length_ms=58.0,
    )
    onset, frame, min_len = _transcription_thresholds(cfg)
    assert onset == 0.58
    assert frame == 0.40
    assert min_len == 90.0


def test_cleanup_config_solo_mix_aware_flag_does_not_raise_velocity():
    cfg = PipelineConfig(
        mix_aware_filtering=True,
        separate_stems=False,
        min_velocity=40,
        min_duration_sec=0.05,
    )
    cleanup = _cleanup_config_for_pipeline(cfg)
    assert cleanup.min_velocity == 40
    assert cleanup.min_duration_sec == 0.05


def test_cleanup_config_separated_mix_aware_raises_velocity():
    cfg = PipelineConfig(
        mix_aware_filtering=True,
        separate_stems=True,
        min_velocity=40,
        min_duration_sec=0.05,
    )
    cleanup = _cleanup_config_for_pipeline(cfg)
    assert cleanup.min_velocity >= 55
    assert cleanup.min_duration_sec >= 0.08
