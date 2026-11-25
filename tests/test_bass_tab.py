"""4-string bass tab through the shared tab engine and every tab writer."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pretty_midi
import pytest
from fastapi.testclient import TestClient

from app.server.main import create_app
from audio_to_tab.musicxml_export import write_musicxml
from audio_to_tab.tab_bundle import tab_document_for, write_tab_exports
from audio_to_tab.tab_generate import tab_document_from_dict, tab_document_to_dict, tab_to_ascii
from audio_to_tab.tuning import BASS_TUNING_NAME
from tests.test_api_run_parts import _save
from tests.test_score_parts_generic import _parts_record

H = {"X-Tab-Token": "t"}


def _bass_midi(path: Path) -> Path:
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    inst = pretty_midi.Instrument(program=33)
    for i, pitch in enumerate((28, 33, 40, 43)):
        inst.notes.append(pretty_midi.Note(90, pitch, i * 0.5, i * 0.5 + 0.4))
    pm.instruments.append(inst)
    pm.write(str(path))
    return path


def _doc(tmp_path):
    return tab_document_for(
        _bass_midi(tmp_path / "bass.mid"),
        tempo_bpm=120.0,
        tempo_confidence="high",
        beats_per_measure=4,
        tuning_name=BASS_TUNING_NAME,
        capo=0,
        transpose=0,
    )


def test_bass_document_uses_four_strings(tmp_path):
    doc = _doc(tmp_path)
    assert tuple(doc.tuning_names) == ("E", "A", "D", "G")
    notes = [n for e in doc.events for n in e.notes]
    assert len(notes) == 4
    assert all(0 <= n.string <= 3 for n in notes)
    assert (notes[0].string, notes[0].fret) == (0, 0)  # low E open


def test_bass_ascii_has_four_lines(tmp_path):
    lines = [ln for ln in tab_to_ascii(_doc(tmp_path)).splitlines() if "|" in ln and ln[1] == "|"]
    assert sorted(ln[0] for ln in lines) == ["A", "D", "E", "G"]


def test_bass_document_round_trips_through_dict(tmp_path):
    doc = _doc(tmp_path)
    again = tab_document_from_dict(tab_document_to_dict(doc))
    assert tuple(again.tuning_names) == ("E", "A", "D", "G")
    assert [(n.string, n.fret) for e in again.events for n in e.notes] == [
        (n.string, n.fret) for e in doc.events for n in e.notes
    ]


def test_bass_musicxml_staff_has_four_lines(tmp_path):
    out = write_musicxml([("Bass", _doc(tmp_path))], tmp_path / "b.musicxml", title="S", tempo_bpm=120)
    root = ET.parse(out).getroot()
    assert root.find(".//staff-lines").text == "4"
    assert len(root.findall(".//staff-tuning")) == 4
    strings = {int(s.text) for s in root.findall(".//technical/string")}
    assert strings <= {1, 2, 3, 4}


def test_bass_exports_write_pdf_tab_and_gp5(tmp_path):
    pytest.importorskip("guitarpro")
    import guitarpro

    written = write_tab_exports(
        _doc(tmp_path), tmp_path / "out", title="Bass", capo=0, transpose=0, bars_per_line=4,
        chords=[], key="E", duration_sec=2.0, tempo_bpm=120.0, tempo_confidence="high",
        tuning_name=BASS_TUNING_NAME, lyrics=[], lyrics_status="", beats_per_measure=4, export_gp5=True,
    )
    assert written["pdf"].stat().st_size > 0
    assert "G|" in written["tab"].read_text()
    song = guitarpro.parse(str(written["gp5"]))
    assert [s.value for s in song.tracks[0].strings] == [43, 38, 33, 28]


def test_api_exports_bass_formats(tmp_path):
    rec = _parts_record(tmp_path / "run1", ["bass"], guitar=False)
    rec.artifacts["bass_midi"] = _bass_midi(rec.dir / "bass.mid")
    run_id = _save(rec)
    client = TestClient(create_app(data_dir=tmp_path, token="t"))
    for fmt in ("pdf", "tab", "midi"):
        r = client.post(f"/api/runs/{run_id}/export", headers=H, json={"format": fmt, "part": "bass"})
        assert r.status_code == 200, (fmt, r.text)
    tab = client.post(f"/api/runs/{run_id}/export", headers=H, json={"format": "tab", "part": "bass"})
    assert "G|" in tab.text
