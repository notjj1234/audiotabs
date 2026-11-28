"""IsolateConfig lead_rhythm_split mode wiring."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import audio_to_tab.lead_rhythm_sep as lead_rhythm_sep
from audio_to_tab.isolate import SUPPORTED_MODELS, IsolateConfig, separate_stems
from audio_to_tab.separate import GUITAR_FT_CHECKPOINT_ID

SR = 44100


def _src(tmp_path: Path) -> Path:
    src = tmp_path / "song.wav"
    t = np.arange(int(2.0 * SR)) / SR
    data = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(str(src), np.column_stack([data, data]), SR)
    return src


def _patch_split(monkeypatch, captured: dict):
    def fake_split(guitar_path, output_dir, *, device="cpu", on_progress=None):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        lead = out / "lead_guitar.wav"
        rhythm = out / "rhythm_guitar.wav"
        n = SR
        t = np.arange(n) / SR
        sf.write(str(lead), (0.2 * np.sin(2 * np.pi * 330 * t)).astype(np.float32), SR)
        sf.write(str(rhythm), (0.2 * np.sin(2 * np.pi * 110 * t)).astype(np.float32), SR)
        captured["split_input"] = Path(guitar_path)
        diag = lead_rhythm_sep.analyze_lead_rhythm_stems(lead, rhythm, input_path=guitar_path)
        return {"lead_guitar": lead, "rhythm_guitar": rhythm}, diag

    monkeypatch.setattr(lead_rhythm_sep, "run_lead_rhythm_split", fake_split)
    return captured


def _patch_separate(monkeypatch, captured: dict):
    def fake_separate(audio_path, output_path=None, **kwargs):
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), np.zeros((SR, 2), dtype=np.float32), SR)
        captured["separate_kwargs"] = kwargs
        return out

    import audio_to_tab.separate as separate_mod

    monkeypatch.setattr(separate_mod, "separate_guitar_stem", fake_separate)
    return captured


def test_supported_models_contains_new_mode():
    assert "lead_rhythm_split" in SUPPORTED_MODELS
    cfg = IsolateConfig(model="lead_rhythm_split", emit_metronome=False)
    assert cfg.lead_rhythm_pre_pass is True


def test_prepass_default_uses_guitar_ft(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_split(monkeypatch, captured)
    _patch_separate(monkeypatch, captured)
    out = tmp_path / "out"

    artifacts = separate_stems(
        _src(tmp_path), out, IsolateConfig(model="lead_rhythm_split", emit_metronome=False)
    )

    assert captured["separate_kwargs"]["guitar_checkpoint"] == GUITAR_FT_CHECKPOINT_ID
    assert captured["separate_kwargs"]["model"] == "htdemucs_6s"
    assert captured["split_input"] == out / "guitar_stem.wav"
    for key in ("guitar", "lead_guitar", "rhythm_guitar", "lead_rhythm_split_diagnostics"):
        assert Path(artifacts[key]).is_file(), key
    presence = (out / "stem_presence.json").read_text(encoding="utf-8")
    assert "lead_guitar" in presence and "rhythm_guitar" in presence


def test_no_prepass_splits_input_directly(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_split(monkeypatch, captured)
    _patch_separate(monkeypatch, captured)
    src = _src(tmp_path)

    artifacts = separate_stems(
        src,
        tmp_path / "out",
        IsolateConfig(
            model="lead_rhythm_split",
            lead_rhythm_pre_pass=False,
            emit_metronome=False,
        ),
    )

    assert "separate_kwargs" not in captured
    assert captured["split_input"] == tmp_path / "out" / "guitar_stem.wav"
    assert Path(artifacts["lead_guitar"]).is_file()


def test_backend_missing_fails_loud(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Lead/rhythm split is not available.")

    monkeypatch.setattr(lead_rhythm_sep, "run_lead_rhythm_split", boom)
    _patch_separate(monkeypatch, {})
    with pytest.raises(RuntimeError, match="Lead/rhythm split is not available"):
        separate_stems(
            _src(tmp_path),
            tmp_path / "out",
            IsolateConfig(model="lead_rhythm_split", emit_metronome=False),
        )


def _roformer_host(monkeypatch, *, available: bool = True):
    import audio_to_tab.roformer as roformer

    monkeypatch.delenv("ATT_SPLIT_STAGE1", raising=False)
    monkeypatch.setattr(roformer, "is_roformer_available", lambda: available)


def test_prepass_uses_bs_roformer_on_gpu(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_split(monkeypatch, captured)
    _patch_separate(monkeypatch, captured)
    _roformer_host(monkeypatch)
    out = tmp_path / "out"

    separate_stems(
        _src(tmp_path),
        out,
        IsolateConfig(model="lead_rhythm_split", device="mps", emit_metronome=False),
    )

    assert captured["separate_kwargs"]["model"] == "bs_roformer_sw"
    assert captured["separate_kwargs"].get("guitar_checkpoint") is None
    assert captured["split_input"] == out / "guitar_stem.wav"


def test_prepass_roformer_failure_falls_back_to_guitar_ft(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_split(monkeypatch, captured)
    _roformer_host(monkeypatch)
    models: list[str] = []

    def fake_separate(audio_path, output_path=None, **kwargs):
        models.append(kwargs["model"])
        if kwargs["model"] == "bs_roformer_sw":
            raise RuntimeError("RoFormer refused this file")
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), np.zeros((SR, 2), dtype=np.float32), SR)
        captured["separate_kwargs"] = kwargs
        return out

    import audio_to_tab.separate as separate_mod

    monkeypatch.setattr(separate_mod, "separate_guitar_stem", fake_separate)

    artifacts = separate_stems(
        _src(tmp_path),
        tmp_path / "out",
        IsolateConfig(model="lead_rhythm_split", device="mps", emit_metronome=False),
    )

    assert models == ["bs_roformer_sw", "htdemucs_6s"]
    assert captured["separate_kwargs"]["guitar_checkpoint"] == GUITAR_FT_CHECKPOINT_ID
    assert Path(artifacts["lead_guitar"]).is_file()
