"""Minimal dependency-free MusicXML 4.0 writer for tab documents."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from audio_to_tab.musicxml_export import write_musicxml
from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote


def _doc(events, tempo=120.0, beats_per_measure=4):
    return TabDocument(
        events=events,
        tempo_bpm=tempo,
        beats_per_measure=beats_per_measure,
    )


def _fixture_docs():
    lead = _doc(
        [
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=0.5, string=0, fret=3, pitch=43)],
            ),
            TabEvent(
                start=1.0,
                notes=[TabNote(start=1.0, end=2.0, string=2, fret=0, pitch=50)],
            ),
        ]
    )
    rhythm = _doc(
        [
            TabEvent(
                start=0.0,
                notes=[
                    TabNote(start=0.0, end=1.0, string=0, fret=0, pitch=40),
                    TabNote(start=0.0, end=1.0, string=1, fret=2, pitch=47),
                    TabNote(start=0.0, end=1.0, string=2, fret=2, pitch=52),
                ],
            )
        ]
    )
    return [("Lead", lead), ("Rhythm", rhythm)]


def test_writes_well_formed_musicxml_4(tmp_path):
    out = write_musicxml(_fixture_docs(), tmp_path / "score.musicxml", title="Song", tempo_bpm=96.0)
    tree = ET.parse(str(out))
    root = tree.getroot()
    assert root.tag == "score-partwise"
    assert root.get("version") == "4.0"


def test_two_parts_with_names(tmp_path):
    out = write_musicxml(_fixture_docs(), tmp_path / "s.xml", title="T", tempo_bpm=120.0)
    root = ET.parse(str(out)).getroot()
    names = [el.text for el in root.findall("./part-list/score-part/part-name")]
    assert names == ["Lead", "Rhythm"]
    parts = root.findall("part")
    assert len(parts) == 2


def test_fret_and_string_round_trip(tmp_path):
    out = write_musicxml(_fixture_docs(), tmp_path / "s.xml", title="T", tempo_bpm=120.0)
    root = ET.parse(str(out)).getroot()
    lead_part = root.findall("part")[0]
    strings = [int(el.text) for el in lead_part.findall(".//technical/string")]
    frets = [int(el.text) for el in lead_part.findall(".//technical/fret")]
    # MusicXML string 1 = high e; TabNote.string 0 = low E -> 6 - string.
    assert sorted(zip(strings, frets, strict=True)) == sorted([(6, 3), (4, 0)])
    rhythm_part = root.findall("part")[1]
    rhythm_strings = [int(el.text) for el in rhythm_part.findall(".//technical/string")]
    assert rhythm_strings == [6, 5, 4]


def test_tab_staff_details_with_six_line_tuning(tmp_path):
    out = write_musicxml(_fixture_docs(), tmp_path / "s.xml", title="T", tempo_bpm=120.0)
    root = ET.parse(str(out)).getroot()
    for part in root.findall("part"):
        details = part.find("./measure/attributes/staff-details")
        assert details is not None
        assert details.findtext("staff-lines") == "6"
        tuning = details.findall("staff-tuning")
        assert len(tuning) == 6
        assert tuning[0].get("line") == "1"
        assert tuning[0].findtext("tuning-step") is not None
        assert tuning[0].findtext("tuning-octave") is not None


def test_title_and_tempo_encoded(tmp_path):
    out = write_musicxml(
        _fixture_docs(), tmp_path / "s.xml", title="Rock & Roll <Live>", tempo_bpm=133.0
    )
    root = ET.parse(str(out)).getroot()
    assert root.findtext("./work/work-title") == "Rock & Roll <Live>"
    sounds = root.findall(".//sound")
    assert any(s.get("tempo") == "133" for s in sounds)


def test_divisions_positive_and_durations(tmp_path):
    out = write_musicxml(_fixture_docs(), tmp_path / "s.xml", title="T", tempo_bpm=120.0)
    root = ET.parse(str(out)).getroot()
    divisions = int(root.find(".//attributes/divisions").text)
    assert divisions > 0
    durations = [int(el.text) for el in root.findall(".//note/duration")]
    assert all(d > 0 for d in durations)


def test_note_pitch_elements(tmp_path):
    out = write_musicxml(_fixture_docs(), tmp_path / "s.xml", title="T", tempo_bpm=120.0)
    root = ET.parse(str(out)).getroot()
    pitches = root.findall(".//note/pitch")
    steps = {(p.findtext("step"), p.findtext("octave")) for p in pitches}
    # MIDI 43 = G2, MIDI 50 = D3, MIDI 40 = E2, 47 = B2, 52 = E3.
    assert ("G", "2") in steps
    assert ("E", "2") in steps


def test_empty_document_still_writes_score(tmp_path):
    out = write_musicxml([("Lead", _doc([]))], tmp_path / "s.xml", title="Empty", tempo_bpm=90.0)
    root = ET.parse(str(out)).getroot()
    assert root.tag == "score-partwise"
    assert len(root.findall("part")) == 1


class TestMeasureTiming:
    def test_chord_tones_use_chord_elements(self, tmp_path):
        out = write_musicxml(_fixture_docs(), tmp_path / "s.xml", title="T", tempo_bpm=120.0)
        root = ET.parse(str(out)).getroot()
        rhythm_part = root.findall("part")[1]
        chord_marks = rhythm_part.findall(".//note/chord")
        # Three simultaneous notes -> one primary + two chord tones.
        assert len(chord_marks) == 2
        for note in rhythm_part.findall(".//note"):
            if note.find("chord") is not None:
                assert note.find("duration") is None
            else:
                assert note.find("duration") is not None

    def test_forward_fills_gap_between_events(self, tmp_path):
        # Lead: 0.5 s note at 0.0, 1.0 s note at 1.0 (120 BPM, 4/4 -> 2 s measure).
        out = write_musicxml(_fixture_docs(), tmp_path / "s.xml", title="T", tempo_bpm=120.0)
        root = ET.parse(str(out)).getroot()
        lead_measure = root.findall("part")[0].find("measure")
        forward = lead_measure.find("forward")
        assert forward is not None
        assert int(forward.findtext("duration")) == 480  # 0.5 s gap = one quarter
        total = sum(
            int(el.findtext("duration"))
            for el in lead_measure
            if el.tag in ("note", "forward", "backup") and el.findtext("duration")
        )
        assert total == 4 * 480  # measure totals the time signature

    def test_measure_totals_time_signature_for_chords(self, tmp_path):
        out = write_musicxml(_fixture_docs(), tmp_path / "s.xml", title="T", tempo_bpm=120.0)
        root = ET.parse(str(out)).getroot()
        rhythm_measure = root.findall("part")[1].find("measure")
        total = sum(
            int(el.findtext("duration"))
            for el in rhythm_measure
            if el.tag in ("note", "forward", "backup") and el.findtext("duration")
        )
        assert total == 4 * 480
