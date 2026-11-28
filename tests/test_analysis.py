"""Analysis phase: one ingest + one separation + split + presence, cached on disk."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import audio_to_tab.analysis as analysis
from audio_to_tab.analysis import analysis_fingerprint, load_analysis, run_analysis
from audio_to_tab.cancel import CancelToken
from audio_to_tab.lead_rhythm_sep import LeadRhythmSplitError
from audio_to_tab.pipeline import PipelineConfig
from audio_to_tab.subprocess_util import JobAborted

SR = 22050
LOUD = {"vocals", "drums", "bass", "guitar", "other"}


def _tone(path: Path, amp: float) -> Path:
    t = np.arange(int(SR * 1.0)) / SR
    sf.write(path, (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32), SR)
    return path


def _patch(monkeypatch, *, split_error: Exception | None = None, calls: list | None = None):
    def fake_normalize(src, dest):
        return _tone(Path(dest), 0.3)

    def fake_sep(src, out_dir, **kwargs):
        if calls is not None:
            calls.append(kwargs)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        return {
            n: _tone(out_dir / f"{n}.wav", 0.3 if n in LOUD else 0.0)
            for n in ("vocals", "drums", "bass", "guitar", "piano", "other")
        }

    def fake_split(guitar_path, out_dir, *, device="cpu", on_progress=None):
        if split_error is not None:
            raise split_error
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        from audio_to_tab.lead_rhythm_sep import LeadRhythmSplitDiagnostics

        return (
            {
                "lead_guitar": _tone(out_dir / "lead_guitar.wav", 0.3),
                "rhythm_guitar": _tone(out_dir / "rhythm_guitar.wav", 0.3),
            },
            LeadRhythmSplitDiagnostics(attempted=True, reason="ok"),
        )

    monkeypatch.setattr(analysis, "normalize_audio", fake_normalize)
    monkeypatch.setattr(analysis, "run_full_separation", fake_sep)
    monkeypatch.setattr(analysis.lead_rhythm_sep, "run_lead_rhythm_split", fake_split)


def _cfg(**kw) -> PipelineConfig:
    return PipelineConfig(separate_stems=True, model="lead_rhythm_split", **kw)


def test_run_analysis_round_trips_and_separates_once(tmp_path, monkeypatch):
    calls: list = []
    _patch(monkeypatch, calls=calls)
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")
    progress: list[tuple[str, str]] = []

    bundle = run_analysis(
        audio_path=src,
        youtube_url=None,
        analysis_dir=tmp_path / "a1",
        config=_cfg(),
        source={"kind": "upload", "upload_id": "u1"},
        on_progress=lambda s, m, f=None: progress.append((s, m)),
        cancel=CancelToken(),
    )

    assert len(calls) == 1
    assert set(bundle.stems) == {"vocals", "drums", "bass", "guitar", "piano", "other"}
    assert bundle.lead_rhythm.ok is True
    assert set(bundle.lead_rhythm_paths) == {"lead", "rhythm"}
    ids = [r.id for r in bundle.inventory]
    assert ids[:3] == ["lead", "rhythm", "combined"]
    assert {s for s, _ in progress} >= {"ingest", "separate", "split", "detect"}
    assert (tmp_path / "a1" / "inventory.json").is_file()
    assert (tmp_path / "a1" / "stem_presence.json").is_file()

    loaded = load_analysis(tmp_path / "a1")
    assert loaded.fingerprint == bundle.fingerprint
    assert loaded.inventory == bundle.inventory
    assert loaded.stems == bundle.stems
    assert loaded.work_audio.is_file()


def test_split_failure_yields_combined_only_inventory(tmp_path, monkeypatch):
    _patch(monkeypatch, split_error=LeadRhythmSplitError("Lead/rhythm split failed: boom"))
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")
    bundle = run_analysis(
        audio_path=src,
        youtube_url=None,
        analysis_dir=tmp_path / "a2",
        config=_cfg(),
        source={"kind": "upload", "upload_id": "u1"},
        on_progress=None,
        cancel=CancelToken(),
    )
    assert bundle.lead_rhythm.ok is False
    guitar = [r for r in bundle.inventory if r.family == "guitar"]
    assert [r.id for r in guitar] == ["lead", "rhythm", "combined"]
    assert [r.tabbable for r in guitar] == [False, False, True]
    assert guitar[2].default_selected is True
    assert (tmp_path / "a2" / "lead_rhythm_fallback.json").is_file()


def test_long_audio_refusal_falls_back_with_reason(tmp_path, monkeypatch):
    _patch(monkeypatch, split_error=RuntimeError("Audio is 400 s; RoFormer limit is 180 s"))
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")
    bundle = run_analysis(
        audio_path=src,
        youtube_url=None,
        analysis_dir=tmp_path / "a3",
        config=_cfg(),
        source={"kind": "upload", "upload_id": "u1"},
        on_progress=None,
        cancel=CancelToken(),
    )
    assert bundle.lead_rhythm.ok is False
    assert bundle.lead_rhythm.reason
    assert "Traceback" not in bundle.lead_rhythm.reason


def test_split_skipped_when_engine_is_not_lead_rhythm(tmp_path, monkeypatch):
    _patch(monkeypatch, split_error=AssertionError("split must not run"))
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")
    bundle = run_analysis(
        audio_path=src,
        youtube_url=None,
        analysis_dir=tmp_path / "a5",
        config=PipelineConfig(separate_stems=True, model="htdemucs_6s"),
        source={"kind": "upload", "upload_id": "u1"},
        on_progress=None,
        cancel=CancelToken(),
    )
    assert bundle.lead_rhythm.ok is False
    assert [(r.id, r.tabbable) for r in bundle.inventory if r.family == "guitar"] == [
        ("lead", False),
        ("rhythm", False),
        ("combined", True),
    ]


def test_cancel_after_separate_leaves_no_folder(tmp_path, monkeypatch):
    _patch(monkeypatch)
    token = CancelToken()
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")

    def progress(stage, message, fraction=None):
        if stage == "split":
            token.cancel()

    with pytest.raises(JobAborted):
        run_analysis(
            audio_path=src,
            youtube_url=None,
            analysis_dir=tmp_path / "a4",
            config=_cfg(),
            source={"kind": "upload", "upload_id": "u1"},
            on_progress=progress,
            cancel=token,
        )
    assert not (tmp_path / "a4").exists()


def test_fingerprint_ignores_tuning_capo_fingering_but_not_model_or_trim():
    src = {"kind": "upload", "upload_id": "u1"}
    base = analysis_fingerprint(src, _cfg(), 0.0)
    assert base == analysis_fingerprint(
        src, _cfg(tuning_name="Drop D", capo=3, fingering_preference="low_fret"), 0.0
    )
    assert base != analysis_fingerprint(src, PipelineConfig(separate_stems=True, model="htdemucs_6s"), 0.0)
    assert base != analysis_fingerprint(src, _cfg(max_duration_sec=60.0), 0.0)
    assert base != analysis_fingerprint(src, _cfg(), 5.0)
    assert base != analysis_fingerprint({"kind": "upload", "upload_id": "u2"}, _cfg(), 0.0)


@pytest.mark.parametrize(
    ("exc", "want"),
    [
        (LeadRhythmSplitError("Lead/rhythm split failed: [Errno 28] No space left on device"),
         "the split model couldn't process this recording."),
        (LeadRhythmSplitError('Lead/rhythm split is not available. Lead/Rhythm split requires the RoFormer runtime: pip install -e ".[roformer]"'),
         "the Lead/Rhythm split model isn't installed."),
        (RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB"),
         "the split model couldn't process this recording."),
    ],
)
def test_split_failure_reason_is_fixed_user_copy(tmp_path, monkeypatch, exc, want):
    _patch(monkeypatch, split_error=exc)
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")
    bundle = run_analysis(
        audio_path=src, youtube_url=None, analysis_dir=tmp_path / "a", config=_cfg(),
        source={"kind": "upload", "upload_id": "u1"}, on_progress=None, cancel=CancelToken(),
    )
    assert bundle.lead_rhythm.reason == want
    import json as _json

    payload = _json.loads((tmp_path / "a" / "lead_rhythm_fallback.json").read_text())
    assert payload["reason"] == want
    assert payload["detail"]  # raw text kept for diagnostics only


def test_split_too_long_reason(tmp_path, monkeypatch):
    from audio_to_tab.roformer import RoFormerTooLongError

    _patch(monkeypatch, split_error=RoFormerTooLongError(400.0, 180.0))
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")
    bundle = run_analysis(
        audio_path=src, youtube_url=None, analysis_dir=tmp_path / "a", config=_cfg(),
        source={"kind": "upload", "upload_id": "u1"}, on_progress=None, cancel=CancelToken(),
    )
    assert bundle.lead_rhythm.reason == "this recording is too long for the Lead/Rhythm split."


def test_split_gets_the_guitar_without_the_vocal_copy_and_records_it(tmp_path, monkeypatch):
    _patch(monkeypatch)  # fake guitar and vocals stems carry the same tone: full "bleed"
    seen: dict[str, Path] = {}
    fake_split = analysis.lead_rhythm_sep.run_lead_rhythm_split

    def spy(guitar_path, out_dir, **kwargs):
        seen["input"] = Path(guitar_path)
        return fake_split(guitar_path, out_dir, **kwargs)

    monkeypatch.setattr(analysis.lead_rhythm_sep, "run_lead_rhythm_split", spy)
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")

    run_analysis(
        audio_path=src, youtube_url=None, analysis_dir=tmp_path / "a1", config=_cfg(),
        source={"kind": "upload", "upload_id": "u1"}, on_progress=None, cancel=CancelToken(),
    )

    assert seen["input"] == tmp_path / "a1" / "_split" / "guitar_for_split.wav"
    import json

    diag = json.loads((tmp_path / "a1" / "lead_rhythm_split_diagnostics.json").read_text())
    assert diag["vocal_suppression"]["applied"] is True
    assert not (tmp_path / "a1" / "_split").exists()


# --- Stage 1 for the Lead/Rhythm split: BS-RoFormer SW guitar when it can run here ---


def _stage1_host(monkeypatch, *, roformer: bool = True, guitar_ft: bool = False):
    import audio_to_tab.roformer as roformer_mod

    monkeypatch.delenv("ATT_SPLIT_STAGE1", raising=False)
    monkeypatch.setattr(roformer_mod, "is_roformer_available", lambda: roformer)
    monkeypatch.setattr(analysis, "guitar_ft_weights_cached", lambda: guitar_ft)


@pytest.mark.parametrize(
    ("device", "roformer", "env", "checkpoint", "want"),
    [
        ("mps", True, None, None, ("bs_roformer_sw", None)),
        ("cuda", True, None, None, ("bs_roformer_sw", None)),
        ("cpu", True, None, None, ("htdemucs_6s", None)),
        ("mps", False, None, None, ("htdemucs_6s", None)),
        ("mps", True, "demucs", None, ("htdemucs_6s", None)),
        ("cpu", True, "bs_roformer_sw", None, ("bs_roformer_sw", None)),
        ("mps", True, None, "htdemucs_6s_guitar_ft", ("htdemucs_6s", "htdemucs_6s_guitar_ft")),
    ],
)
def test_split_stage1_model_choice(monkeypatch, device, roformer, env, checkpoint, want):
    _stage1_host(monkeypatch, roformer=roformer)
    if env:
        monkeypatch.setenv("ATT_SPLIT_STAGE1", env)
    cfg = _cfg(demucs_device=device, guitar_checkpoint=checkpoint)
    assert analysis.analysis_separation_model(cfg) == want


def test_split_stage1_falls_back_to_guitar_ft_demucs_when_roformer_cannot_run_here(monkeypatch):
    _stage1_host(monkeypatch, roformer=True, guitar_ft=True)
    cfg = _cfg(demucs_device="cpu")
    assert analysis.analysis_separation_model(cfg) == ("htdemucs_6s", "htdemucs_6s_guitar_ft")


def test_other_engines_keep_their_separator(monkeypatch):
    _stage1_host(monkeypatch)
    assert analysis.analysis_separation_model(
        PipelineConfig(model="htdemucs_6s", demucs_device="mps")
    ) == ("htdemucs_6s", None)


def test_split_analysis_separates_with_roformer_and_records_it(tmp_path, monkeypatch):
    import json

    calls: list = []
    _patch(monkeypatch, calls=calls)
    _stage1_host(monkeypatch)
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")

    bundle = run_analysis(
        audio_path=src, youtube_url=None, analysis_dir=tmp_path / "a", config=_cfg(demucs_device="mps"),
        source={"kind": "upload", "upload_id": "u1"}, on_progress=None, cancel=CancelToken(),
    )

    assert [c["model"] for c in calls] == ["bs_roformer_sw"]
    assert bundle.model == "bs_roformer_sw"
    meta = json.loads((tmp_path / "a" / "analysis.json").read_text())
    assert meta["model"] == "bs_roformer_sw"
    assert meta["separation"] == {"model": "bs_roformer_sw"}
    assert load_analysis(tmp_path / "a").model == "bs_roformer_sw"


def test_roformer_failure_retries_with_demucs_and_records_why(tmp_path, monkeypatch):
    import json

    calls: list = []
    _patch(monkeypatch, calls=calls)
    _stage1_host(monkeypatch)
    fake_sep = analysis.run_full_separation

    def flaky(src, out_dir, **kwargs):
        if kwargs["model"] == "bs_roformer_sw":
            calls.append(kwargs)
            raise RuntimeError("RoFormer refused this 400 s file (limit 180 s on this machine).")
        return fake_sep(src, out_dir, **kwargs)

    monkeypatch.setattr(analysis, "run_full_separation", flaky)
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")

    bundle = run_analysis(
        audio_path=src, youtube_url=None, analysis_dir=tmp_path / "a", config=_cfg(demucs_device="mps"),
        source={"kind": "upload", "upload_id": "u1"}, on_progress=None, cancel=CancelToken(),
    )

    assert [c["model"] for c in calls] == ["bs_roformer_sw", "htdemucs_6s"]
    assert bundle.model == "htdemucs_6s"
    assert bundle.lead_rhythm.ok is True
    sep = json.loads((tmp_path / "a" / "analysis.json").read_text())["separation"]
    assert sep["model"] == "htdemucs_6s"
    assert sep["fallback_from"] == "bs_roformer_sw"
    assert "limit 180 s" in sep["fallback_reason"]


def test_explicit_roformer_engine_failure_is_not_hidden(tmp_path, monkeypatch):
    _patch(monkeypatch)
    _stage1_host(monkeypatch)

    def boom(src, out_dir, **kwargs):
        raise RuntimeError("weights download failed")

    monkeypatch.setattr(analysis, "run_full_separation", boom)
    src = tmp_path / "in.wav"
    src.write_bytes(b"RIFF")
    with pytest.raises(RuntimeError, match="weights download failed"):
        run_analysis(
            audio_path=src, youtube_url=None, analysis_dir=tmp_path / "a",
            config=PipelineConfig(separate_stems=True, model="bs_roformer_sw", demucs_device="mps"),
            source={"kind": "upload", "upload_id": "u1"}, on_progress=None, cancel=CancelToken(),
        )
