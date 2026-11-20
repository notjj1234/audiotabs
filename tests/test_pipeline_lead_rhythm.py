"""Pipeline integration for the lead/rhythm split mode."""

from __future__ import annotations

import json
import types
from pathlib import Path

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import audio_to_tab.lead_rhythm_sep as lead_rhythm_sep
import audio_to_tab.lead_rhythm_tab as lead_rhythm_tab
import audio_to_tab.pipeline as pipeline
from audio_to_tab.lead_rhythm_tab import StemNote, StemTranscription
from audio_to_tab.pipeline import EmptyTranscriptionError, PipelineConfig, run_pipeline
from audio_to_tab.separate import GUITAR_FT_CHECKPOINT_ID

SR = 44100


def _input_wav(tmp_path: Path) -> Path:
    src = tmp_path / "input.wav"
    t = np.arange(int(2.0 * SR)) / SR
    data = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(str(src), np.column_stack([data, data]), SR)
    return src


def _patch_common(monkeypatch, tmp_path):
    """Mock model-touching stages; keep file writers real."""
    calls: dict[str, object] = {}

    def fake_normalize(input_path, output_path=None, **kwargs):
        out = Path(output_path) if output_path is not None else tmp_path / "norm.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(input_path, out)
        return out

    def fake_separate(audio_path, output_path=None, **kwargs):
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), np.zeros((SR, 2), dtype=np.float32), SR)
        calls["separate_kwargs"] = kwargs
        return out

    def fake_resolve_tempo(**kwargs):
        calls["tempo_audio"] = kwargs.get("audio_path")
        return types.SimpleNamespace(
            bpm=120.0,
            confidence="high",
            beats=(),
            downbeats=(),
            beats_per_measure=4,
            anacrusis_sec=0.0,
        )

    def fake_split(guitar_path, output_dir, *, device="cpu", on_progress=None):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        lead = out / "lead_guitar.wav"
        rhythm = out / "rhythm_guitar.wav"
        n = SR
        t = np.arange(n) / SR
        sf.write(str(lead), (0.2 * np.sin(2 * np.pi * 330 * t)).astype(np.float32), SR)
        sf.write(str(rhythm), (0.2 * np.sin(2 * np.pi * 110 * t)).astype(np.float32), SR)
        calls["split_input"] = Path(guitar_path)
        diag = lead_rhythm_sep.analyze_lead_rhythm_stems(lead, rhythm, input_path=guitar_path)
        return {"lead_guitar": lead, "rhythm_guitar": rhythm}, diag

    monkeypatch.setattr(pipeline, "normalize_audio", fake_normalize)
    monkeypatch.setattr(pipeline, "separate_guitar_stem", fake_separate)
    monkeypatch.setattr(pipeline, "resolve_tempo", fake_resolve_tempo)
    monkeypatch.setattr(lead_rhythm_sep, "run_lead_rhythm_split", fake_split)
    return calls


def _tx(role: str, tmp_path: Path, pitches: list[int]) -> StemTranscription:
    notes = [
        StemNote(pitch=p, start=0.1 + i * 0.3, end=0.35 + i * 0.3, velocity=100, confidence=100 / 127)
        for i, p in enumerate(pitches)
    ]
    return StemTranscription(
        role=role,
        notes=notes,
        techniques=[],
        low_confidence_regions=[],
        source_midi=tmp_path / f"{role}_raw.mid",
    )


def _patch_transcriptions(monkeypatch, tmp_path, lead_pitches=(64, 67), rhythm_pitches=(40, 45, 50)):
    monkeypatch.setattr(
        lead_rhythm_tab,
        "transcribe_lead_stem",
        lambda *a, **k: _tx("lead", tmp_path, list(lead_pitches)),
    )
    monkeypatch.setattr(
        lead_rhythm_tab,
        "transcribe_rhythm_stem",
        lambda *a, **k: _tx("rhythm", tmp_path, list(rhythm_pitches)),
    )


def _run(tmp_path, **cfg_kwargs):
    out_dir = tmp_path / "run"
    artifacts = run_pipeline(
        audio_path=_input_wav(tmp_path),
        output_dir=out_dir,
        config=PipelineConfig(
            title="Song",
            separate_stems=True,
            lead_rhythm_split=True,
            export_gp5=False,
            **cfg_kwargs,
        ),
        on_progress=lambda *a: None,
    )
    return out_dir, artifacts


def test_full_mode_produces_all_artifacts(tmp_path, monkeypatch):
    calls = _patch_common(monkeypatch, tmp_path)
    _patch_transcriptions(monkeypatch, tmp_path)
    out_dir, artifacts = _run(tmp_path)

    expected = {
        "midi", "tab", "pdf", "result", "playback", "guitar_stem",
        "lead_guitar", "rhythm_guitar",
        "lead_rhythm_split_diagnostics", "lead_rhythm_notes",
        "lead_midi", "rhythm_midi", "stems_midi", "musicxml",
        "lead_tab", "lead_pdf", "lead_result",
        "rhythm_tab", "rhythm_pdf", "rhythm_result",
    }
    assert expected <= set(artifacts)
    for key in expected:
        assert Path(artifacts[key]).is_file(), key
    sep_kwargs = calls["separate_kwargs"]
    assert sep_kwargs["guitar_checkpoint"] == GUITAR_FT_CHECKPOINT_ID
    assert sep_kwargs["model"] == "htdemucs_6s"
    # Split ran on the pre-passed guitar stem.
    assert calls["split_input"] == out_dir / "guitar_stem.wav"
    # Tempo resolved on the guitar stem, not the original mix.
    assert calls["tempo_audio"] == out_dir / "guitar_stem.wav"

    import xml.etree.ElementTree as ET

    root = ET.parse(str(artifacts["musicxml"])).getroot()
    assert root.tag == "score-partwise"

    pm = pretty_midi.PrettyMIDI(str(artifacts["stems_midi"]))
    assert len(pm.instruments) == 2
    assert {i.name for i in pm.instruments} == {"Lead", "Rhythm"}

    payload = json.loads(Path(artifacts["lead_rhythm_notes"]).read_text(encoding="utf-8"))
    assert payload["warnings"] == []
    assert len(payload["lead"]["notes"]) == 2
    assert len(payload["rhythm"]["notes"]) == 3


def test_user_guitar_checkpoint_respected(tmp_path, monkeypatch):
    calls = _patch_common(monkeypatch, tmp_path)
    _patch_transcriptions(monkeypatch, tmp_path)
    _run(tmp_path, guitar_checkpoint=GUITAR_FT_CHECKPOINT_ID)
    assert calls["separate_kwargs"]["guitar_checkpoint"] == GUITAR_FT_CHECKPOINT_ID


def test_already_isolated_input_skips_prepass(tmp_path, monkeypatch):
    calls = _patch_common(monkeypatch, tmp_path)
    _patch_transcriptions(monkeypatch, tmp_path)
    out_dir = tmp_path / "run"
    artifacts = run_pipeline(
        audio_path=_input_wav(tmp_path),
        output_dir=out_dir,
        config=PipelineConfig(
            title="Song",
            separate_stems=False,
            lead_rhythm_split=True,
            export_gp5=False,
        ),
        on_progress=lambda *a: None,
    )
    assert "separate_kwargs" not in calls
    assert calls["split_input"] == out_dir / "guitar_stem.wav"
    assert Path(artifacts["lead_guitar"]).is_file()


def test_split_failure_propagates_without_fallback(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)

    def boom(*a, **k):
        raise RuntimeError("backend exploded")

    monkeypatch.setattr(lead_rhythm_sep, "run_lead_rhythm_split", boom)
    with pytest.raises(RuntimeError, match="Lead/rhythm split failed"):
        _run(tmp_path)
    out_dir = tmp_path / "run"
    assert not (out_dir / "transcription.tab").exists()


def test_both_stems_empty_raises(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)
    _patch_transcriptions(monkeypatch, tmp_path, lead_pitches=(), rhythm_pitches=())
    with pytest.raises(EmptyTranscriptionError):
        _run(tmp_path)


def test_one_empty_stem_warns_and_continues(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)
    _patch_transcriptions(monkeypatch, tmp_path, lead_pitches=(), rhythm_pitches=(40, 45))
    _, artifacts = _run(tmp_path)
    payload = json.loads(Path(artifacts["lead_rhythm_notes"]).read_text(encoding="utf-8"))
    assert any("lead" in w.lower() for w in payload["warnings"])
    assert Path(artifacts["lead_midi"]).is_file()
    assert Path(artifacts["rhythm_midi"]).is_file()


def test_defaults_unchanged_and_model_alias():
    cfg = PipelineConfig()
    assert cfg.lead_rhythm_split is False
    assert cfg.model == "auto"
    aliased = PipelineConfig(model="lead_rhythm_split")
    assert aliased.lead_rhythm_split is True


def test_split_error_not_double_prefixed(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)
    _patch_transcriptions(monkeypatch, tmp_path)

    def already_wrapped(*a, **k):
        raise lead_rhythm_sep.LeadRhythmSplitError(
            "Lead/rhythm split is not available. install hint"
        )

    monkeypatch.setattr(lead_rhythm_sep, "run_lead_rhythm_split", already_wrapped)
    with pytest.raises(RuntimeError) as excinfo:
        _run(tmp_path)
    assert str(excinfo.value).startswith("Lead/rhythm split is not available.")

    def raw_error(*a, **k):
        raise ValueError("backend exploded")

    monkeypatch.setattr(lead_rhythm_sep, "run_lead_rhythm_split", raw_error)
    with pytest.raises(RuntimeError, match="Lead/rhythm split failed: backend exploded"):
        _run(tmp_path)
