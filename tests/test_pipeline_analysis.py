"""Tab phase reuses a cached analysis: no download, no separation, selected parts only."""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

import audio_to_tab.lead_rhythm_sep as lead_rhythm_sep
import audio_to_tab.pipeline as pipeline
import audio_to_tab.separate as separate_mod
from audio_to_tab.analysis import run_analysis
from audio_to_tab.cancel import CancelToken
from audio_to_tab.pipeline import PipelineConfig, run_pipeline
from tests.analysis_fakes import patch_analysis_engine
from tests.test_pipeline_lead_rhythm import (
    _patch_single_guitar_transcription,
    _patch_transcriptions,
)


def _bundle(tmp_path, monkeypatch, *, split_ok=True, model="lead_rhythm_split"):
    patch_analysis_engine(monkeypatch, split_ok=split_ok)
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")
    return run_analysis(
        audio_path=src,
        youtube_url=None,
        analysis_dir=tmp_path / "analysis",
        config=PipelineConfig(separate_stems=True, model=model),
        source={"kind": "upload", "upload_id": "u"},
        on_progress=None,
        cancel=CancelToken(),
    )


def _forbid_reingest(monkeypatch):
    def nope(*a, **k):
        raise AssertionError("tab phase must not ingest, download, separate or split again")

    monkeypatch.setattr(pipeline, "normalize_audio", nope)
    monkeypatch.setattr(pipeline, "download_youtube_audio", nope)
    monkeypatch.setattr(pipeline, "separate_guitar_stem", nope)
    monkeypatch.setattr(lead_rhythm_sep, "run_lead_rhythm_split", nope)
    monkeypatch.setattr(
        pipeline,
        "resolve_tempo",
        lambda **k: types.SimpleNamespace(
            bpm=120.0, confidence="high", beats=(0.0, 0.5, 1.0, 1.5),
            downbeats=(0.0,), beats_per_measure=4, anacrusis_sec=0.0,
        ),
    )


def _run(tmp_path, bundle, parts, *, model="lead_rhythm_split"):
    return run_pipeline(
        output_dir=tmp_path / "run",
        config=PipelineConfig(title="Song", separate_stems=True, model=model, export_gp5=False),
        analysis=bundle,
        parts=parts,
    )


def test_tab_phase_never_separates(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    before = separate_mod.SEPARATION_CALLS
    _forbid_reingest(monkeypatch)
    _patch_transcriptions(monkeypatch, tmp_path)

    artifacts = _run(tmp_path, bundle, ["lead", "rhythm"])

    assert before == separate_mod.SEPARATION_CALLS
    assert Path(artifacts["lead_result"]).is_file()
    assert Path(artifacts["rhythm_result"]).is_file()
    parts = json.loads(Path(artifacts["parts"]).read_text())
    assert parts["parts"] == ["lead", "rhythm"]
    grid = json.loads(Path(artifacts["grid"]).read_text())
    assert grid["bpm"] == 120.0 and grid["beats_per_measure"] == 4
    assert Path(artifacts["playback"]).is_file()
    assert Path(artifacts["vocals_stem"]).is_file()


def test_run_split_diagnostics_keep_the_analysis_vocal_suppression_report(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)  # fake stems: the guitar carries the vocal's tone
    _forbid_reingest(monkeypatch)
    _patch_transcriptions(monkeypatch, tmp_path)

    artifacts = _run(tmp_path, bundle, ["lead", "rhythm"])

    run_diag = json.loads(Path(artifacts["lead_rhythm_split_diagnostics"]).read_text())
    saved = json.loads((tmp_path / "analysis" / "lead_rhythm_split_diagnostics.json").read_text())
    assert saved["vocal_suppression"]["applied"] is True
    assert run_diag["vocal_suppression"] == saved["vocal_suppression"]


def test_lead_only_selection_hides_rhythm(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    _forbid_reingest(monkeypatch)
    _patch_transcriptions(monkeypatch, tmp_path)
    artifacts = _run(tmp_path, bundle, ["lead"])
    assert json.loads(Path(artifacts["parts"]).read_text())["parts"] == ["lead"]


def test_split_failed_analysis_runs_combined_with_fallback_notice(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch, split_ok=False)
    _forbid_reingest(monkeypatch)
    _patch_single_guitar_transcription(monkeypatch, tmp_path)
    artifacts = _run(tmp_path, bundle, ["combined"])
    assert "lead_midi" not in artifacts
    assert Path(artifacts["result"]).is_file()
    assert json.loads(Path(artifacts["parts"]).read_text())["parts"] == ["combined"]
    fb = json.loads(Path(artifacts["lead_rhythm_fallback"]).read_text())
    assert fb["fallback"] is True and fb["reason"]


def test_combined_only_with_successful_split_skips_lead_rhythm(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    _forbid_reingest(monkeypatch)
    _patch_single_guitar_transcription(monkeypatch, tmp_path)
    artifacts = _run(tmp_path, bundle, ["combined"])
    assert "lead_midi" not in artifacts
    assert "lead_rhythm_fallback" not in artifacts


def test_unknown_part_rejected(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        _run(tmp_path, bundle, ["kazoo"])


def test_keys_only_run_has_no_guitar_tab(tmp_path, monkeypatch):
    import audio_to_tab.part_transcribe as part_transcribe
    from tests.test_part_transcribe import _fake_basic_pitch

    bundle = _bundle(tmp_path, monkeypatch)
    _forbid_reingest(monkeypatch)
    monkeypatch.setattr(part_transcribe, "transcribe_audio", _fake_basic_pitch([60, 64, 67]))
    artifacts = _run(tmp_path, bundle, ["keys"])
    assert json.loads(Path(artifacts["parts"]).read_text())["parts"] == ["keys"]
    assert Path(artifacts["keys_result"]).is_file()
    assert Path(artifacts["keys_midi"]).is_file()
    assert "lead_result" not in artifacts and "tab" not in artifacts
    assert Path(artifacts["playback"]).is_file()
    assert Path(artifacts["grid"]).is_file()
    assert Path(artifacts["result"]).is_file()


def test_empty_part_recorded_and_job_continues(tmp_path, monkeypatch):
    bundle = _bundle(tmp_path, monkeypatch)
    _forbid_reingest(monkeypatch)
    _patch_transcriptions(monkeypatch, tmp_path)
    artifacts = _run(tmp_path, bundle, ["lead", "rhythm", "keys"])  # piano stem is silent
    parts = json.loads(Path(artifacts["parts"]).read_text())
    assert parts["parts"] == ["lead", "rhythm", "keys"]
    assert parts["empty"]["keys"] == "No notes found in this part."


def test_empty_guitar_part_does_not_sink_the_other_parts(tmp_path, monkeypatch):
    import audio_to_tab.part_transcribe as part_transcribe
    from audio_to_tab.pipeline import EmptyTranscriptionError
    from tests.test_part_transcribe import _fake_basic_pitch

    bundle = _bundle(tmp_path, monkeypatch, split_ok=False)
    _forbid_reingest(monkeypatch)
    monkeypatch.setattr(part_transcribe, "transcribe_audio", _fake_basic_pitch([60, 64, 67]))

    def empty_guitar(*a, **k):
        raise EmptyTranscriptionError("No usable notes were found.")

    monkeypatch.setattr(pipeline, "_run_guitar_pipeline", empty_guitar)
    artifacts = _run(tmp_path, bundle, ["combined", "keys"])
    parts = json.loads(Path(artifacts["parts"]).read_text())
    assert parts["parts"] == ["combined", "keys"]
    assert parts["empty"]["combined"] == "No notes found in this part."
    assert Path(artifacts["keys_result"]).is_file()
    assert Path(artifacts["playback"]).is_file() and Path(artifacts["grid"]).is_file()


def test_empty_guitar_alone_still_fails_with_the_usual_message(tmp_path, monkeypatch):
    from audio_to_tab.pipeline import EmptyTranscriptionError

    bundle = _bundle(tmp_path, monkeypatch, split_ok=False)
    _forbid_reingest(monkeypatch)
    monkeypatch.setattr(pipeline, "_run_guitar_pipeline", lambda **k: (_ for _ in ()).throw(EmptyTranscriptionError("x")))
    with pytest.raises(EmptyTranscriptionError):
        _run(tmp_path, bundle, ["combined"])
