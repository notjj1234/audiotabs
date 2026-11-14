from __future__ import annotations

import json
from pathlib import Path

import pretty_midi

from audio_to_tab.tab_generate import TabDocument
from scripts.eval_tabs import evaluate, note_match_f1, tempo_rel_error


def test_note_matching_is_optimal_for_unsorted_reference_notes():
    hyp = [
        {"pitch": 64, "start": 0.04, "end": 0.1},
        {"pitch": 64, "start": 0.09, "end": 0.2},
    ]
    ref = [
        {"pitch": 64, "start": 0.06, "end": 0.1},
        {"pitch": 64, "start": 0.0, "end": 0.1},
    ]

    result = note_match_f1(hyp, ref)

    assert result["matched"] == 2
    assert result["note_f1"] == 1.0


def test_evaluate_uses_pipeline_tempo_and_meter(tmp_path: Path, monkeypatch):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"audio")
    midi = tmp_path / "transcription.mid"
    pm = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=25)
    instrument.notes.append(pretty_midi.Note(90, 64, 0.0, 0.5))
    pm.instruments.append(instrument)
    pm.write(str(midi))
    playback = tmp_path / "playback.wav"
    playback.write_bytes(b"audio")
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "tempo_bpm": 200.0,
                "tempo_confidence": "low",
                "beats_per_measure": 3,
                "beats": [0.0, 0.3, 0.6, 0.9],
                "fingering_preference": "low_fret",
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_run_pipeline(**kwargs):
        captured["config"] = kwargs["config"]
        return {"midi": midi, "playback": playback, "result": result}

    monkeypatch.setattr("audio_to_tab.pipeline.run_pipeline", fake_run_pipeline)
    monkeypatch.setattr("audio_to_tab.tab_bundle.audio_duration_seconds", lambda _path: 1.0)

    def fake_tab_document(_midi_path, **kwargs):
        captured.update(kwargs)
        return TabDocument(events=[])

    monkeypatch.setattr("audio_to_tab.tab_bundle.tab_document_for", fake_tab_document)

    evaluate(
        audio,
        None,
        tmp_path / "output",
        separate=False,
        tag="test",
        fingering_preference="position",
        max_duration_sec=30.0,
        model="htdemucs_6s",
        export_gp5=True,
    )

    config = captured["config"]
    assert config.fingering_preference == "position"
    assert config.max_duration_sec == 30.0
    assert config.model == "htdemucs_6s"
    assert config.export_gp5 is True
    assert captured["tempo_bpm"] == 200.0
    assert captured["tempo_confidence"] == "low"
    assert captured["beats_per_measure"] == 3
    assert captured["beats"] == (0.0, 0.3, 0.6, 0.9)
    assert captured["fingering_preference"] == "low_fret"


def test_evaluate_measures_playability_from_exact_tab_source(tmp_path: Path, monkeypatch):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"audio")
    final_midi = tmp_path / "transcription.mid"
    tab_midi = tmp_path / "transcription_unquantized.mid"
    for path, start in ((final_midi, 0.05), (tab_midi, 0.03)):
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=25)
        instrument.notes.append(pretty_midi.Note(90, 64, start, start + 0.5))
        pm.instruments.append(instrument)
        pm.write(str(path))
    playback = tmp_path / "playback.wav"
    playback.write_bytes(b"audio")
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "tempo_bpm": 120.0,
                "tempo_confidence": "high",
                "beats_per_measure": 4,
                "beats": [0.0, 0.5, 1.0, 1.5],
                "fingering_preference": "playable",
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_run_pipeline(**kwargs):
        captured["include_tab_source"] = kwargs.get("include_tab_source")
        return {"midi": final_midi, "tab_midi": tab_midi, "playback": playback, "result": result}

    def fake_tab_document(midi_path, **kwargs):
        captured["tab_midi_path"] = midi_path
        return TabDocument(events=[])

    monkeypatch.setattr("audio_to_tab.pipeline.run_pipeline", fake_run_pipeline)
    monkeypatch.setattr("audio_to_tab.tab_bundle.audio_duration_seconds", lambda _path: 1.0)
    monkeypatch.setattr("audio_to_tab.tab_bundle.tab_document_for", fake_tab_document)

    evaluate(
        audio,
        None,
        tmp_path / "output",
        separate=False,
        tag="test",
    )

    assert captured["include_tab_source"] is True
    assert captured["tab_midi_path"] == tab_midi


def test_tempo_error_uses_reference_midi_tempo_map(tmp_path: Path):
    reference = tmp_path / "reference.mid"
    pm = pretty_midi.PrettyMIDI(initial_tempo=200.0)
    instrument = pretty_midi.Instrument(program=25)
    for start in (0.0, 1.2, 2.4, 3.6, 4.8):
        instrument.notes.append(pretty_midi.Note(90, 64, start, start + 0.2))
    pm.instruments.append(instrument)
    pm.write(str(reference))
    ref_notes = [
        {"pitch": 64, "start": start, "end": start + 0.2}
        for start in (0.0, 1.2, 2.4, 3.6, 4.8)
    ]

    assert tempo_rel_error(200.0, reference, ref_notes) == 0.0
    assert tempo_rel_error(100.0, reference, ref_notes) == 0.5
    assert tempo_rel_error(400.0, reference, ref_notes) == 1.0
