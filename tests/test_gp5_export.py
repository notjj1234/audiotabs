from __future__ import annotations

from pathlib import Path

import guitarpro
import pytest

from audio_to_tab.gp5_export import write_guitar_pro
from audio_to_tab.tab_bundle import write_tab_exports
from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote


def _document() -> TabDocument:
    return TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[
                    TabNote(start=0.0, end=0.5, string=0, fret=0, pitch=40),
                    TabNote(start=0.0, end=0.5, string=5, fret=0, pitch=64),
                ],
            ),
            TabEvent(
                start=1.75,
                notes=[TabNote(start=1.75, end=2.5, string=0, fret=3, pitch=43)],
            ),
        ],
        tempo_bpm=120.0,
        beats_per_measure=4,
    )


def test_gp5_round_trip_preserves_notes_tempo_and_cross_measure_tie(tmp_path: Path):
    path = tmp_path / "transcription.gp5"

    write_guitar_pro(_document(), path, title="Test riff")

    song = guitarpro.parse(str(path))
    assert song.tempo == 120
    assert song.measureHeaders[0].timeSignature.numerator == 4
    assert len(song.tracks[0].measures) == 2
    first_beat = song.tracks[0].measures[0].voices[0].beats[0]
    assert sorted((note.value, note.string) for note in first_beat.notes) == [(0, 1), (0, 6)]
    second_measure_notes = [
        note
        for voice in song.tracks[0].measures[1].voices
        for beat in voice.beats
        for note in beat.notes
    ]
    assert len(second_measure_notes) == 1
    assert second_measure_notes[0].type == guitarpro.NoteType.tie
    assert second_measure_notes[0].value == 3
    assert second_measure_notes[0].string == 6


def test_gp5_export_keeps_overlapping_notes_in_second_voice(tmp_path: Path):
    doc = TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=1.0, string=0, fret=0, pitch=40)],
            ),
            TabEvent(
                start=0.5,
                notes=[TabNote(start=0.5, end=1.0, string=5, fret=0, pitch=64)],
            ),
        ],
        tempo_bpm=120.0,
    )
    path = tmp_path / "overlap.gp5"

    write_guitar_pro(doc, path, title="Overlap")

    song = guitarpro.parse(str(path))
    notes = [
        (note.value, note.string)
        for voice in song.tracks[0].measures[0].voices
        for beat in voice.beats
        for note in beat.notes
        if note.type == guitarpro.NoteType.normal
    ]
    assert sorted(notes) == [(0, 1), (0, 6)]


def test_gp5_export_preserves_three_overlapping_rhythms(tmp_path: Path):
    doc = TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=2.0, string=0, fret=0, pitch=40)],
            ),
            TabEvent(
                start=0.5,
                notes=[TabNote(start=0.5, end=1.0, string=5, fret=0, pitch=64)],
            ),
            TabEvent(
                start=0.75,
                notes=[TabNote(start=0.75, end=1.25, string=4, fret=3, pitch=48)],
            ),
        ],
        tempo_bpm=120.0,
    )
    path = tmp_path / "three-overlap.gp5"

    write_guitar_pro(doc, path, title="Three overlap")

    song = guitarpro.parse(str(path))
    notes = [
        (note.value, note.string)
        for track in song.tracks
        for measure in track.measures
        for voice in measure.voices
        for beat in voice.beats
        for note in beat.notes
        if note.type == guitarpro.NoteType.normal
    ]
    assert sorted(notes) == [(0, 1), (0, 6), (3, 2)]


def test_gp5_export_preserves_three_four_meter(tmp_path: Path):
    doc = TabDocument(events=_document().events, tempo_bpm=120.0, beats_per_measure=3)
    path = tmp_path / "three-four.gp5"

    write_guitar_pro(doc, path, title="Three four")

    song = guitarpro.parse(str(path))
    assert song.measureHeaders[0].timeSignature.numerator == 3


def test_gp5_missing_dependency_has_install_hint(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("audio_to_tab.gp5_export.importlib.util.find_spec", lambda _name: None)

    with pytest.raises(RuntimeError, match=r"\[gp5\]"):
        write_guitar_pro(_document(), tmp_path / "missing.gp5", title="Missing")


def test_gp5_export_deduplicates_same_string_onsets(tmp_path: Path):
    doc = TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=0.5, string=0, fret=0, pitch=40)],
            ),
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=0.5, string=0, fret=3, pitch=43)],
            ),
        ],
        tempo_bpm=120.0,
    )
    path = tmp_path / "duplicate-string.gp5"

    write_guitar_pro(doc, path, title="Duplicate string")

    song = guitarpro.parse(str(path))
    notes = [
        note
        for voice in song.tracks[0].measures[0].voices
        for beat in voice.beats
        for note in beat.notes
        if note.type == guitarpro.NoteType.normal
    ]
    assert len(notes) == 1
    assert notes[0].string == 6


def test_gp5_round_trip_supports_more_than_32_measures(tmp_path: Path):
    events = [
        TabEvent(
            start=index * 2.0,
            notes=[TabNote(start=index * 2.0, end=index * 2.0 + 0.5, string=0, fret=3, pitch=43)],
        )
        for index in range(40)
    ]
    path = tmp_path / "long.gp5"

    write_guitar_pro(TabDocument(events=events, tempo_bpm=120.0), path, title="Long")

    song = guitarpro.parse(str(path))
    assert len(song.tracks[0].measures) == 40
    notes = [
        note
        for measure in song.tracks[0].measures
        for voice in measure.voices
        for beat in voice.beats
        for note in beat.notes
        if note.type == guitarpro.NoteType.normal
    ]
    assert len(notes) == 40


def test_write_tab_exports_includes_gp5_when_requested(tmp_path: Path):
    artifacts = write_tab_exports(
        _document(),
        tmp_path,
        title="Test riff",
        capo=0,
        transpose=0,
        bars_per_line=4,
        chords=[],
        key="C",
        duration_sec=2.5,
        tempo_bpm=120.0,
        tempo_confidence="high",
        tuning_name="Standard (EADGBE)",
        lyrics=[],
        lyrics_status="",
        beats_per_measure=4,
        export_gp5=True,
    )

    assert artifacts["gp5"].is_file()
    assert guitarpro.parse(str(artifacts["gp5"])).tracks[0].name == "Test riff"
