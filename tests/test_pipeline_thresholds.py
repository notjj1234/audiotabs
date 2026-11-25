"""Mix-aware transcription floor coupling (solo vs separated)."""

from __future__ import annotations

from audio_to_tab.pipeline import (
    LEAD_STEM_FLOORS,
    RHYTHM_STEM_FLOORS,
    PipelineConfig,
    _cleanup_config_for_pipeline,
    _part_transcription_settings,
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


def test_lead_rhythm_parts_on_separated_input_use_their_own_floors():
    cfg = PipelineConfig(separate_stems=True, mix_aware_filtering=True, lead_rhythm_split=True)

    lead = _part_transcription_settings(cfg, LEAD_STEM_FLOORS)
    rhythm = _part_transcription_settings(cfg, RHYTHM_STEM_FLOORS)

    # Both drop the general 0.40 frame floor; the lead keeps the strict cleanup, rhythm doesn't.
    assert lead[:3] == (0.58, 0.3, 90.0)
    assert (lead[3].min_velocity, lead[3].min_duration_sec) == (55, 0.08)
    assert rhythm[:3] == (0.58, 0.3, 90.0)
    assert (rhythm[3].min_velocity, rhythm[3].min_duration_sec) == (40, 0.05)


def test_lead_rhythm_part_floors_never_lower_user_thresholds():
    cfg = PipelineConfig(
        separate_stems=True,
        mix_aware_filtering=True,
        onset_threshold=0.7,
        frame_threshold=0.5,
        min_velocity=70,
    )

    onset, frame, _min_len, cleanup = _part_transcription_settings(cfg, RHYTHM_STEM_FLOORS)

    assert (onset, frame, cleanup.min_velocity) == (0.7, 0.5, 70)


def test_lead_rhythm_parts_on_isolated_input_use_the_user_settings():
    cfg = PipelineConfig(separate_stems=False, mix_aware_filtering=True)

    onset, frame, min_len, cleanup = _part_transcription_settings(cfg, LEAD_STEM_FLOORS)

    assert (onset, frame, min_len) == (0.5, 0.3, 58.0)
    assert cleanup.min_velocity == cfg.min_velocity
