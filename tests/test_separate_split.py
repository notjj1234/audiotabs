"""Separation split: run the model once (all stems), post-process guitar separately."""

from __future__ import annotations

from pathlib import Path

import audio_to_tab.separate as separate_mod
from audio_to_tab.separate import (
    postprocess_guitar_stem,
    run_full_separation,
    separate_guitar_stem,
)

SIX = ("vocals", "drums", "bass", "guitar", "piano", "other")


def _six_stem_demucs(args: list[str], **_kwargs) -> None:
    root = Path(args[args.index("-o") + 1])
    dest = root / "htdemucs_6s" / "track"
    dest.mkdir(parents=True)
    for name in SIX:
        (dest / f"{name}.wav").write_bytes(f"{name}-bytes".encode())


def _patch_demucs(monkeypatch, runner=_six_stem_demucs) -> None:
    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs", runner)


def test_run_full_separation_keeps_six_stems(tmp_path: Path, monkeypatch):
    _patch_demucs(monkeypatch)
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    before = separate_mod.SEPARATION_CALLS

    stems = run_full_separation(audio, tmp_path / "stems", model="htdemucs_6s")

    assert set(stems) == set(SIX)
    for name, path in stems.items():
        assert path.parent == tmp_path / "stems"
        assert path.read_bytes() == f"{name}-bytes".encode()
    assert separate_mod.SEPARATION_CALLS == before + 1


def test_run_full_separation_forwards_should_abort(tmp_path: Path, monkeypatch):
    seen: dict[str, object] = {}

    def runner(args, **kwargs):
        seen.update(kwargs)
        _six_stem_demucs(args)

    _patch_demucs(monkeypatch, runner)
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    abort = lambda: False  # noqa: E731

    run_full_separation(audio, tmp_path / "stems", should_abort=abort)

    assert seen.get("should_abort") is abort


def test_postprocess_guitar_stem_uses_cached_stems_without_separating(tmp_path: Path):
    stems = {}
    for name in SIX:
        p = tmp_path / f"{name}.wav"
        p.write_bytes(f"{name}-bytes".encode())
        stems[name] = p
    before = separate_mod.SEPARATION_CALLS

    out = postprocess_guitar_stem(stems, tmp_path / "guitar_stem.wav", model="htdemucs_6s")

    assert out.read_bytes() == b"guitar-bytes"
    assert separate_mod.SEPARATION_CALLS == before


def test_bleed_gate_excludes_guitar_self(tmp_path: Path, monkeypatch):
    _patch_demucs(monkeypatch)
    captured: dict[str, object] = {}

    def fake_gate(guitar_path, output_path=None, *, competitor_paths=None, **_kw):
        captured["competitors"] = dict(competitor_paths or {})
        from audio_to_tab.isolate import BleedGateDiagnostics

        return BleedGateDiagnostics(attempted=False, reason="test")

    monkeypatch.setattr("audio_to_tab.isolate.apply_bleed_gate", fake_gate)
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")

    separate_guitar_stem(audio, tmp_path / "g.wav", bleed_gate=True)

    assert "guitar" not in captured["competitors"]
    assert set(captured["competitors"]) == {"other", "bass", "drums"}


def test_bleed_gate_can_include_vocals_competitor(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_gate(guitar_path, output_path=None, *, competitor_paths=None, **_kw):
        captured["competitors"] = dict(competitor_paths or {})
        from audio_to_tab.isolate import BleedGateDiagnostics

        return BleedGateDiagnostics(attempted=False, reason="test")

    monkeypatch.setattr("audio_to_tab.isolate.apply_bleed_gate", fake_gate)
    stems = {}
    for name in SIX:
        p = tmp_path / f"{name}.wav"
        p.write_bytes(b"x")
        stems[name] = p

    postprocess_guitar_stem(
        stems,
        tmp_path / "out.wav",
        model="htdemucs_6s",
        bleed_gate=True,
        bleed_gate_competitors=("other", "bass", "drums", "vocals"),
    )

    assert set(captured["competitors"]) == {"other", "bass", "drums", "vocals"}
