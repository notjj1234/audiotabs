"""Vocal de-bleed wiring: on for separated full mixes with vocals, never on solo input."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pretty_midi
import pytest

import audio_to_tab.pipeline as pipeline
import audio_to_tab.vocal_debleed as vocal_debleed
from audio_to_tab.pipeline import PipelineConfig, run_pipeline
from tests.test_pipeline_analysis import _bundle, _forbid_reingest
from tests.test_pipeline_lead_rhythm import (
    _input_wav,
    _patch_common,
    _patch_single_guitar_transcription,
    _patch_transcriptions,
)


def _features_marking(pitch: int) -> vocal_debleed.DebleedFeatures:
    """Evidence that every note at ``pitch`` is the singer bleeding in (ratio 0.3, no attack)."""
    n = 1000
    hop = 0.01
    vm = np.full(n, float(pitch))
    g = np.zeros((n, 128))
    v = np.zeros((n, 128))
    v[:, pitch] = 1.0
    g[:, pitch] = 0.3
    return vocal_debleed.DebleedFeatures(
        hop_sec=hop, vocal_midi=vm, guitar_mag=g, vocal_mag=v, onset=np.zeros(n), bleed_gain=0.3
    )


def test_solo_run_never_touches_debleed(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)
    _patch_single_guitar_transcription(monkeypatch, tmp_path)

    def boom(*a, **k):
        raise AssertionError("de-bleed must not run on solo input")

    monkeypatch.setattr(vocal_debleed.DebleedFeatures, "from_audio", classmethod(boom))
    arts = run_pipeline(
        audio_path=_input_wav(tmp_path),
        output_dir=tmp_path / "run",
        config=PipelineConfig(separate_stems=False, mix_aware_filtering=False, export_gp5=False),
    )
    assert "vocal_debleed_diagnostics" not in arts
    assert not (tmp_path / "run" / "vocal_debleed_diagnostics.json").exists()


def test_combined_path_drops_bleed_notes_and_writes_diagnostics(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch, split_ok=False)
    _forbid_reingest(monkeypatch)
    _patch_single_guitar_transcription(monkeypatch, tmp_path)  # notes 60, 64, 67, 72
    monkeypatch.setattr(
        vocal_debleed.DebleedFeatures, "from_audio", classmethod(lambda cls, g, v: _features_marking(64))
    )
    arts = run_pipeline(
        output_dir=tmp_path / "run",
        config=PipelineConfig(title="Song", separate_stems=True, export_gp5=False),
        analysis=bundle,
        parts=["combined"],
    )
    pitches = sorted(n.pitch for i in pretty_midi.PrettyMIDI(str(arts["midi"])).instruments for n in i.notes)
    assert 64 not in pitches and pitches == [60, 67, 72]
    diag = json.loads(Path(arts["vocal_debleed_diagnostics"]).read_text())
    assert diag["attempted"] is True
    assert diag["parts"]["combined"]["notes_in"] == 4
    assert diag["parts"]["combined"]["notes_removed"] == 1
    assert diag["thresholds"]["match_min"] == 0.6


def test_lead_rhythm_path_filters_each_stem_before_roles(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    _forbid_reingest(monkeypatch)
    _patch_transcriptions(monkeypatch, tmp_path, lead_pitches=(64, 67), rhythm_pitches=(40, 45, 50))
    monkeypatch.setattr(
        vocal_debleed.DebleedFeatures, "from_audio", classmethod(lambda cls, g, v: _features_marking(67))
    )
    arts = run_pipeline(
        output_dir=tmp_path / "run",
        config=PipelineConfig(title="Song", separate_stems=True, model="lead_rhythm_split", export_gp5=False),
        analysis=bundle,
        parts=["lead", "rhythm"],
    )
    lead = [n.pitch for i in pretty_midi.PrettyMIDI(str(arts["lead_midi"])).instruments for n in i.notes]
    assert 67 not in lead
    diag = json.loads(Path(arts["vocal_debleed_diagnostics"]).read_text())
    assert diag["parts"]["lead"]["notes_removed"] == 1
    assert diag["parts"]["rhythm"]["notes_removed"] == 0


def test_kill_switch_skips_and_records_why(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch, split_ok=False)
    _forbid_reingest(monkeypatch)
    _patch_single_guitar_transcription(monkeypatch, tmp_path)
    monkeypatch.setattr(
        vocal_debleed.DebleedFeatures, "from_audio",
        classmethod(lambda cls, g, v: pytest.fail("must not analyse when turned off")),
    )
    arts = run_pipeline(
        output_dir=tmp_path / "run",
        config=PipelineConfig(title="Song", separate_stems=True, export_gp5=False, vocal_debleed="off"),
        analysis=bundle,
        parts=["combined"],
    )
    diag = json.loads(Path(arts["vocal_debleed_diagnostics"]).read_text())
    assert diag["attempted"] is False and "off" in diag["reason"]
    pitches = sorted(n.pitch for i in pretty_midi.PrettyMIDI(str(arts["midi"])).instruments for n in i.notes)
    assert pitches == [60, 64, 67, 72]
