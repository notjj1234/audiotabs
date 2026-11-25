from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.eval_lead_rhythm import (
    balanced_accuracy,
    changes_per_min,
    jams_notes,
    labelled_window_metrics,
    mix_pair,
    role_accuracy,
    sdr_db,
    section_labels,
    select_pairs,
    window_lead_share,
)


def _jams(path: Path, notes_per_string: list[list[tuple[float, float, float]]]) -> None:
    annotations = [{"namespace": "pitch_contour", "data": {"time": [], "value": []}}]
    for string_notes in notes_per_string:
        annotations.append(
            {
                "namespace": "note_midi",
                "data": [
                    {"time": t, "duration": d, "value": v, "confidence": None}
                    for t, d, v in string_notes
                ],
            }
        )
    path.write_text(json.dumps({"annotations": annotations}), encoding="utf-8")


def test_jams_notes_merges_strings_and_rounds_pitch(tmp_path: Path):
    path = tmp_path / "00_BN1-129-Eb_comp.jams"
    _jams(path, [[(1.0, 0.5, 44.4)], [(0.5, 0.25, 51.6)]])

    notes = jams_notes(path)

    assert [(n["pitch"], n["start"], n["end"]) for n in notes] == [(52, 0.5, 0.75), (44, 1.0, 1.5)]


def test_select_pairs_needs_both_takes_and_takes_one_per_player_genre(tmp_path: Path):
    for name in (
        "00_BN1-129-Eb_comp", "00_BN1-129-Eb_solo",
        "00_BN2-131-B_comp", "00_BN2-131-B_solo",
        "00_Rock1-90-C#_comp",  # no solo take
        "01_Jazz3-137-Eb_comp", "01_Jazz3-137-Eb_solo",
    ):
        (tmp_path / f"{name}.jams").write_text("{}", encoding="utf-8")

    assert select_pairs(tmp_path) == ["00_BN1-129-Eb", "01_Jazz3-137-Eb"]


def test_mix_pair_scales_mix_and_stems_together():
    comp = np.full(4, 0.8, dtype=np.float32)
    solo = np.full(6, 0.8, dtype=np.float32)

    mix, c, s = mix_pair(comp, solo)

    assert len(mix) == 4
    assert np.allclose(mix, c + s)
    assert np.isclose(np.max(np.abs(mix)), 0.95)


def test_role_accuracy_counts_right_stem_among_correct_notes():
    solo = [{"pitch": 72, "start": 0.0}, {"pitch": 74, "start": 0.5}]
    comp = [{"pitch": 48, "start": 0.0}, {"pitch": 52, "start": 0.0}]
    lead = [{"pitch": 72, "start": 0.01}, {"pitch": 48, "start": 0.0}]  # one rhythm note misfiled
    rhythm = [{"pitch": 52, "start": 0.02}, {"pitch": 74, "start": 0.51}]  # one lead note misfiled

    assert role_accuracy(lead, rhythm, solo, comp) == 0.5
    assert role_accuracy([], [], solo, comp) is None


def test_sdr_db_is_high_for_a_close_estimate_and_low_for_silence():
    ref = np.sin(np.linspace(0, 100, 4410))
    assert sdr_db(ref, ref * 0.99) > 30
    assert sdr_db(ref, np.zeros_like(ref)) == 0.0


def test_window_lead_share_and_audible_mask():
    sr = 100
    lead = np.concatenate([np.ones(sr), np.zeros(sr), np.zeros(sr)])
    rhythm = np.concatenate([np.zeros(sr), np.ones(sr), np.zeros(sr)])

    share, audible = window_lead_share(lead, rhythm, sr=sr)

    assert np.allclose(share[:2], [1.0, 0.0])
    assert audible.tolist() == [True, True, False]


def test_section_labels_use_song_time_and_mark_gaps_unlabelled():
    sections = [{"start": 10.0, "end": 12.0, "lead": False}, {"start": 12.0, "end": 13.0, "lead": True}]

    assert section_labels(sections, clip_start=10.0, n_windows=4).tolist() == [0, 0, 1, -1]


def test_balanced_accuracy_and_changes_per_min():
    truth = np.array([0, 0, 1, 1])
    assert balanced_accuracy(np.array([0, 1, 1, 1]), truth) == 0.75
    assert balanced_accuracy(np.array([1, 1]), np.array([1, 1])) is None
    assert changes_per_min(np.array([0, 1, 0, 0])) == 30.0


def test_labelled_window_metrics_scores_audio_and_tab_against_labels():
    share = np.array([0.1, 0.2, 0.9, 0.8])
    audible = np.ones(4, dtype=bool)
    labels = np.array([0, 0, 1, 1])
    lead_onsets = [102.2, 102.7, 103.1]  # song seconds; clip starts at 100 s

    m = labelled_window_metrics(share, audible, lead_onsets, labels, clip_start=100.0)

    assert m["audio_balanced_acc"] == 1.0
    assert m["tab_balanced_acc"] == 1.0
    assert m["audio_changes_per_min"] == 15.0
    assert m["tab_lead_notes_per_s_in_lead"] == 1.5
