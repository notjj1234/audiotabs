"""Progress hooks for guitar stem separation (no model quality changes)."""

from __future__ import annotations

import time
from pathlib import Path

from audio_to_tab.separate import _run_blocking_with_creep


def test_blocking_creep_advances_then_reaches_end():
    fractions: list[float] = []

    def on_progress(_message: str, fraction: float) -> None:
        fractions.append(fraction)

    def blocking() -> None:
        time.sleep(0.9)

    _run_blocking_with_creep(
        blocking,
        on_progress=on_progress,
        message="Isolating",
        start=0.15,
        end=0.75,
        tau_sec=1.0,
    )
    assert fractions
    assert fractions[0] >= 0.15
    assert fractions[-1] == 0.75
    assert max(fractions) <= 0.75
    assert any(a < b for a, b in zip(fractions, fractions[1:]))


def test_pipeline_separate_emits_multiple_fraction_updates(monkeypatch, tmp_path: Path):
    from audio_to_tab import pipeline as pipeline_mod
    from audio_to_tab.pipeline import PipelineConfig, run_pipeline

    events: list[tuple[str, str, float | None]] = []

    def on_progress(stage: str, message: str, fraction: float | None = None) -> None:
        events.append((stage, message, fraction))

    def fake_normalize(audio_path, output_path):  # noqa: ANN001
        Path(output_path).write_bytes(b"RIFF")
        return Path(output_path)

    def fake_duration(_path):  # noqa: ANN001
        return 12.0

    def fake_separate(audio_path, output_path, **kwargs):  # noqa: ANN001
        cb = kwargs.get("on_progress")
        if cb:
            cb("Isolating guitar stem", 0.2)
            cb("Isolating guitar stem", 0.6)
            cb("Isolating guitar stem", 0.9)
        Path(output_path).write_bytes(b"stem")
        return Path(output_path)

    class _Diag:
        def write_json(self, _path):  # noqa: ANN001
            return None

    monkeypatch.setattr(pipeline_mod, "normalize_audio", fake_normalize)
    monkeypatch.setattr(pipeline_mod, "audio_duration_seconds", fake_duration)
    monkeypatch.setattr(pipeline_mod, "separate_guitar_stem", fake_separate)
    monkeypatch.setattr(pipeline_mod, "resolve_guitar_model", lambda model, _d: "htdemucs_6s")
    monkeypatch.setattr(pipeline_mod, "analyze_guitar_stem_quality", lambda _p: _Diag())

    # Stop after separate by raising on transcribe.
    def boom(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("stop-after-separate")

    monkeypatch.setattr(pipeline_mod, "transcribe_audio", boom)

    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFF")
    out = tmp_path / "out"
    out.mkdir()
    try:
        run_pipeline(
            audio_path=audio,
            output_dir=out,
            config=PipelineConfig(separate_stems=True, max_duration_sec=None),
            on_progress=on_progress,
        )
    except RuntimeError as exc:
        assert "stop-after-separate" in str(exc)

    separate_events = [e for e in events if e[0] == "separate"]
    assert len(separate_events) >= 2
    fractions = [f for _, _, f in separate_events if f is not None]
    assert fractions == sorted(fractions)
    assert fractions[-1] >= fractions[0]
