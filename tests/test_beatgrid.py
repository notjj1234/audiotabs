from __future__ import annotations

import json
from pathlib import Path

import pretty_midi
import pytest

from audio_to_tab.beatgrid import BeatGrid, beat_grid_from_events
from audio_to_tab.pipeline import PipelineConfig, run_pipeline
from audio_to_tab.tab_bundle import write_tab_exports
from audio_to_tab.tab_generate import TabDocument
from audio_to_tab.tempo import TempoEstimate, resolve_tempo


def _midi(path: Path) -> Path:
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    for start in (0.0, 0.5, 1.0, 1.5):
        guitar.notes.append(pretty_midi.Note(90, 64, start, start + 0.2))
    pm.instruments.append(guitar)
    pm.write(str(path))
    return path


def test_beat_grid_derives_three_four_tempo_and_anacrusis():
    grid = beat_grid_from_events(
        beats=[0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75, 4.25],
        downbeats=[0.75, 2.25, 3.75],
    )

    assert grid is not None
    assert grid.bpm == pytest.approx(120.0)
    assert grid.beats_per_measure == 3
    assert grid.anacrusis_sec == pytest.approx(0.75)


def test_beat_grid_derives_four_four_without_anacrusis():
    grid = beat_grid_from_events(
        beats=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        downbeats=[0.0, 2.0, 4.0],
    )

    assert grid is not None
    assert grid.beats_per_measure == 4
    assert grid.anacrusis_sec == 0.0


def test_beat_grid_preserves_tempo_above_legacy_180_bpm_cap():
    grid = beat_grid_from_events(
        beats=[0.0, 0.3, 0.6, 0.9, 1.2, 1.5, 1.8, 2.1, 2.4],
        downbeats=[0.0, 1.2, 2.4],
    )

    assert grid is not None
    assert grid.bpm == pytest.approx(200.0)


def test_delayed_first_downbeat_is_not_anacrusis_when_it_is_first_beat():
    grid = beat_grid_from_events(
        beats=[0.1, 0.4, 0.7, 1.0, 1.3, 1.6, 1.9, 2.2, 2.5],
        downbeats=[0.1, 1.3, 2.5],
    )

    assert grid is not None
    assert grid.anacrusis_sec == 0.0


def test_resolve_tempo_uses_beat_this_metadata(tmp_path: Path, monkeypatch):
    midi_path = _midi(tmp_path / "reference.mid")
    grid = BeatGrid(
        bpm=200.0,
        beats=(0.0, 0.3, 0.6, 0.9, 1.2),
        downbeats=(0.0, 1.2),
        beats_per_measure=4,
        anacrusis_sec=0.0,
    )
    monkeypatch.setattr("audio_to_tab.tempo.estimate_beat_grid", lambda *args, **kwargs: grid)
    monkeypatch.setattr(
        "audio_to_tab.tempo.estimate_tempo_from_audio",
        lambda *args, **kwargs: pytest.fail("librosa must not replace a Beat This result"),
    )

    est = resolve_tempo(audio_path="clip.wav", midi_path=midi_path)

    assert est.bpm == 200.0
    assert est.source == "beat_this"
    assert est.beats_per_measure == 4
    assert est.beats == (0.0, 0.3, 0.6, 0.9, 1.2)
    assert est.downbeats == (0.0, 1.2)


def test_resolve_tempo_falls_back_to_librosa(tmp_path: Path, monkeypatch):
    midi_path = _midi(tmp_path / "reference.mid")
    monkeypatch.setattr("audio_to_tab.tempo.estimate_beat_grid", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "audio_to_tab.tempo.estimate_tempo_from_audio",
        lambda *args, **kwargs: TempoEstimate(bpm=120.0, confidence="high", source="audio"),
    )

    est = resolve_tempo(audio_path="clip.wav", midi_path=midi_path)

    assert est.bpm == 120.0
    assert est.source == "audio"


def test_tempo_override_preserves_detected_meter_metadata(tmp_path: Path, monkeypatch):
    grid = BeatGrid(
        bpm=100.0,
        beats=(0.25, 0.75, 1.25, 1.75, 2.25),
        downbeats=(0.75, 2.25),
        beats_per_measure=3,
        anacrusis_sec=0.75,
    )
    monkeypatch.setattr("audio_to_tab.tempo.estimate_beat_grid", lambda *args, **kwargs: grid)

    est = resolve_tempo(
        audio_path="clip.wav",
        midi_path=_midi(tmp_path / "reference.mid"),
        override_bpm=140.0,
    )

    assert est.bpm == 140.0
    assert est.source == "override"
    assert est.beats_per_measure == 3
    assert est.downbeats == (0.75, 2.25)
    assert est.anacrusis_sec == 0.75


def test_pipeline_rejects_unknown_beat_model():
    with pytest.raises(ValueError, match="beat_model"):
        PipelineConfig(beat_model="unknown")


def test_pipeline_config_preserves_positional_field_order():
    cfg = PipelineConfig(
        True,
        "balanced",
        "cpu",
        "htdemucs_6s",
        None,
        False,
        8,
        1,
        None,
        0.0,
        False,
        False,
        False,
        False,
        True,
        0.5,
        0.3,
        58.0,
        40,
        0.05,
        0.05,
        6,
        None,
        "Guitar Tab",
        None,
        4,
        "Standard (EADGBE)",
        2,
        1,
        3,
    )

    assert cfg.tuning_name == "Standard (EADGBE)"
    assert cfg.capo == 2
    assert cfg.transpose == 1
    assert cfg.bars_per_line == 3


@pytest.mark.parametrize(("auto_meter", "expected_meter"), [(True, 3), (False, 4)])
def test_pipeline_controls_detected_meter(
    tmp_path: Path,
    monkeypatch,
    auto_meter: bool,
    expected_meter: int,
):
    source = tmp_path / "input.wav"
    source.write_bytes(b"input")
    midi_path = _midi(tmp_path / "notes.mid")
    captured: dict[str, object] = {}

    def fake_normalize(_source, destination):
        Path(destination).write_bytes(b"RIFF")
        return Path(destination)

    def fake_transcribe(_audio, destination, **_kwargs):
        destination.write_bytes(midi_path.read_bytes())

    def fake_tab_document(_midi_path, **kwargs):
        captured["tab"] = kwargs["beats_per_measure"]
        captured["tab_beats"] = kwargs["beats"]
        captured["tab_fingering"] = kwargs["fingering_preference"]
        return TabDocument(events=[])

    def fake_exports(_doc, output_dir, **kwargs):
        captured["export"] = kwargs["beats_per_measure"]
        captured["beats"] = kwargs["beats"]
        captured["export_fingering"] = kwargs["fingering_preference"]
        captured["export_gp5"] = kwargs["export_gp5"]
        captured["downbeats"] = kwargs["downbeats"]
        captured["anacrusis_sec"] = kwargs["anacrusis_sec"]
        names = ("tab", "pdf", "result", "gp5") if kwargs["export_gp5"] else ("tab", "pdf", "result")
        paths = {name: output_dir / name for name in names}
        for path in paths.values():
            path.write_bytes(b"artifact")
        return paths

    monkeypatch.setattr("audio_to_tab.pipeline.normalize_audio", fake_normalize)
    monkeypatch.setattr("audio_to_tab.pipeline._trim_audio", lambda path, _limit: path)
    monkeypatch.setattr("audio_to_tab.pipeline.transcribe_audio", fake_transcribe)
    monkeypatch.setattr(
        "audio_to_tab.pipeline.resolve_tempo",
        lambda **_kwargs: TempoEstimate(
            bpm=120.0,
            confidence="high",
            source="beat_this",
            beats_per_measure=3,
            beats=(0.25, 0.75, 1.25, 1.75, 2.25),
            downbeats=(0.75, 2.25),
            anacrusis_sec=0.75,
        ),
    )
    monkeypatch.setattr("audio_to_tab.pipeline.tab_document_for", fake_tab_document)
    monkeypatch.setattr("audio_to_tab.pipeline.write_tab_exports", fake_exports)

    artifacts = run_pipeline(
        audio_path=source,
        output_dir=tmp_path / "output",
        config=PipelineConfig(
            separate_stems=False,
            max_duration_sec=None,
            auto_meter=auto_meter,
            fingering_preference="low_fret",
            export_gp5=True,
        ),
    )

    assert captured == {
        "tab": expected_meter,
        "tab_beats": (0.25, 0.75, 1.25, 1.75, 2.25),
        "tab_fingering": "low_fret",
        "export": expected_meter,
        "beats": (0.25, 0.75, 1.25, 1.75, 2.25),
        "export_fingering": "low_fret",
        "export_gp5": True,
        "downbeats": (0.75, 2.25),
        "anacrusis_sec": 0.75,
    }
    assert artifacts["gp5"].is_file()


def test_pipeline_quantizes_midi_artifact_but_not_tab_source(tmp_path: Path, monkeypatch):
    source = tmp_path / "input.wav"
    source.write_bytes(b"input")
    captured: dict[str, object] = {}

    def fake_normalize(_source, destination):
        Path(destination).write_bytes(b"RIFF")
        return Path(destination)

    def fake_transcribe(_audio, destination, **kwargs):
        captured["cleanup_quantize"] = kwargs["cleanup"].quantize_sec
        pm = pretty_midi.PrettyMIDI()
        guitar = pretty_midi.Instrument(program=25)
        for start in (0.03, 0.53, 1.03):
            guitar.notes.append(pretty_midi.Note(90, 64, start, start + 0.10))
        pm.instruments.append(guitar)
        pm.write(str(destination))

    def fake_tab_document(midi_path, **kwargs):
        pm = pretty_midi.PrettyMIDI(str(midi_path))
        captured["tab_start"] = pm.instruments[0].notes[0].start
        captured["beats"] = kwargs["beats"]
        return TabDocument(events=[])

    def fake_exports(_doc, output_dir, **_kwargs):
        paths = {name: output_dir / name for name in ("tab", "pdf", "result")}
        for path in paths.values():
            path.write_bytes(b"artifact")
        return paths

    monkeypatch.setattr("audio_to_tab.pipeline.normalize_audio", fake_normalize)
    monkeypatch.setattr("audio_to_tab.pipeline._trim_audio", lambda path, _limit: path)
    monkeypatch.setattr("audio_to_tab.pipeline.transcribe_audio", fake_transcribe)
    monkeypatch.setattr(
        "audio_to_tab.pipeline.resolve_tempo",
        lambda **_kwargs: TempoEstimate(
            bpm=120.0,
            confidence="high",
            source="beat_this",
            beats=(0.0, 0.5, 1.0, 1.5),
        ),
    )
    monkeypatch.setattr("audio_to_tab.pipeline.tab_document_for", fake_tab_document)
    monkeypatch.setattr("audio_to_tab.pipeline.write_tab_exports", fake_exports)

    artifacts = run_pipeline(
        audio_path=source,
        output_dir=tmp_path / "output",
        config=PipelineConfig(separate_stems=False, quantize_sec=0.05),
    )

    final_pm = pretty_midi.PrettyMIDI(str(artifacts["midi"]))
    assert captured["cleanup_quantize"] is None
    assert captured["tab_start"] == pytest.approx(0.03, abs=0.001)
    assert captured["beats"] == (0.0, 0.5, 1.0, 1.5)
    assert final_pm.instruments[0].notes[0].start == pytest.approx(0.05)


def test_pipeline_can_return_unquantized_tab_source(tmp_path: Path, monkeypatch):
    source = tmp_path / "input.wav"
    source.write_bytes(b"input")

    def fake_normalize(_source, destination):
        Path(destination).write_bytes(b"RIFF")
        return Path(destination)

    def fake_transcribe(_audio, destination, **_kwargs):
        pm = pretty_midi.PrettyMIDI()
        guitar = pretty_midi.Instrument(program=25)
        for start in (0.03, 0.53, 1.03):
            guitar.notes.append(pretty_midi.Note(90, 64, start, start + 0.10))
        pm.instruments.append(guitar)
        pm.write(str(destination))

    monkeypatch.setattr("audio_to_tab.pipeline.normalize_audio", fake_normalize)
    monkeypatch.setattr("audio_to_tab.pipeline._trim_audio", lambda path, _limit: path)
    monkeypatch.setattr("audio_to_tab.pipeline.transcribe_audio", fake_transcribe)
    monkeypatch.setattr(
        "audio_to_tab.pipeline.cleanup_midi",
        lambda source, destination, **_kwargs: Path(destination).write_bytes(
            Path(source).read_bytes()
        ),
    )
    monkeypatch.setattr(
        "audio_to_tab.pipeline.resolve_tempo",
        lambda **_kwargs: TempoEstimate(bpm=120.0, confidence="high", source="beat_this"),
    )
    monkeypatch.setattr(
        "audio_to_tab.pipeline.tab_document_for",
        lambda *_args, **_kwargs: TabDocument(events=[]),
    )
    monkeypatch.setattr(
        "audio_to_tab.pipeline.write_tab_exports",
        lambda _doc, output_dir, **_kwargs: {
            name: output_dir / name for name in ("tab", "pdf", "result")
        },
    )

    artifacts = run_pipeline(
        audio_path=source,
        output_dir=tmp_path / "output",
        config=PipelineConfig(separate_stems=False, quantize_sec=0.05),
        include_tab_source=True,
    )

    tab_source_pm = pretty_midi.PrettyMIDI(str(artifacts["tab_midi"]))
    assert tab_source_pm.instruments[0].notes[0].start == pytest.approx(0.03, abs=0.001)


def test_exports_include_beat_metadata(tmp_path: Path):
    artifacts = write_tab_exports(
        TabDocument(events=[]),
        tmp_path,
        title="Clip",
        capo=0,
        transpose=0,
        bars_per_line=4,
        chords=[],
        key="C",
        duration_sec=2.0,
        tempo_bpm=120.0,
        tempo_confidence="high",
        tuning_name="Standard (EADGBE)",
        lyrics=[],
        lyrics_status="",
        beats_per_measure=3,
        beats=(0.25, 0.75, 1.25, 1.75, 2.25),
        downbeats=(0.75, 2.25),
        anacrusis_sec=0.75,
        fingering_preference="low_fret",
    )

    result = json.loads(artifacts["result"].read_text(encoding="utf-8"))
    assert result["fingering_preference"] == "low_fret"
    assert result["beats"] == [0.25, 0.75, 1.25, 1.75, 2.25]
    assert result["downbeats"] == [0.75, 2.25]
    assert result["anacrusis_sec"] == 0.75
