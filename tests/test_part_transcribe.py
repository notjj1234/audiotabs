"""Per-part transcription for non-guitar instruments."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf

import audio_to_tab.part_transcribe as part_transcribe
from audio_to_tab.part_transcribe import transcribe_part
from audio_to_tab.pipeline import PipelineConfig
from tests.analysis_fakes import SR, drum_pattern, vocal_melody


def _fake_basic_pitch(pitches):
    def fake(_audio, destination, **kwargs):
        pm = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        for i, p in enumerate(pitches):
            inst.notes.append(pretty_midi.Note(90, p, 0.1 + i * 0.4, 0.4 + i * 0.4))
        pm.instruments.append(inst)
        pm.write(str(destination))
        fake.kwargs = kwargs
        return Path(destination)

    return fake


def test_vocals_part_writes_staff_result(tmp_path):
    stem = vocal_melody(tmp_path / "vocals.wav", [(62, 0.1, 0.6), (65, 0.8, 1.3)])
    res = transcribe_part("vocals", stem, tmp_path / "out", cfg=PipelineConfig())
    assert res.kind == "staff" and res.note_count == 2 and res.empty_reason is None
    payload = json.loads(res.result.read_text())
    assert payload["kind"] == "staff" and payload["clef"] == "treble"
    assert [n["pitch"] for n in payload["notes"]] == [62, 65]
    assert len(pretty_midi.PrettyMIDI(str(res.midi)).instruments[0].notes) == 2


def test_bass_part_uses_bass_range_and_tuning(tmp_path, monkeypatch):
    fake = _fake_basic_pitch([28, 40])
    monkeypatch.setattr(part_transcribe, "transcribe_audio", fake)
    stem = tmp_path / "bass.wav"
    sf.write(stem, np.zeros(SR), SR)
    res = transcribe_part("bass", stem, tmp_path / "out", cfg=PipelineConfig())
    payload = json.loads(res.result.read_text())
    assert payload["kind"] == "tab" and payload["tuning_midi"] == [28, 33, 38, 43]
    assert fake.kwargs["cleanup"].pitch_min == 28 and fake.kwargs["cleanup"].pitch_max == 67
    assert fake.kwargs["cleanup"].max_notes_per_onset == 2


def test_keys_part_is_grand_staff(tmp_path, monkeypatch):
    monkeypatch.setattr(part_transcribe, "transcribe_audio", _fake_basic_pitch([48, 72, 76]))
    stem = tmp_path / "piano.wav"
    sf.write(stem, np.zeros(SR), SR)
    res = transcribe_part("keys", stem, tmp_path / "out", cfg=PipelineConfig())
    payload = json.loads(res.result.read_text())
    assert payload["clef"] == "grand" and res.note_count == 3


def test_drums_part_writes_gm_midi(tmp_path):
    stem = drum_pattern(tmp_path / "drums.wav", [("kick", 0.1), ("snare", 0.6), ("hihat", 0.35)])
    res = transcribe_part("drums", stem, tmp_path / "out", cfg=PipelineConfig())
    payload = json.loads(res.result.read_text())
    assert payload["kind"] == "drums" and res.note_count >= 3
    inst = pretty_midi.PrettyMIDI(str(res.midi)).instruments[0]
    assert inst.is_drum
    assert {n.pitch for n in inst.notes} <= {36, 38, 42}


def test_silent_part_reports_empty_without_raising(tmp_path):
    stem = tmp_path / "drums.wav"
    sf.write(stem, np.zeros(SR), SR)
    res = transcribe_part("drums", stem, tmp_path / "out", cfg=PipelineConfig())
    assert res.note_count == 0
    assert res.empty_reason == "No notes found in this part."
    assert res.result.is_file()
