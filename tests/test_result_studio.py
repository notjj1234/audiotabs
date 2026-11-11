"""Result-page behavior that sits beside the current PDF pipeline."""

from __future__ import annotations

from pathlib import Path

import pretty_midi
import pytest

from audio_to_tab.chords import chords_from_midi, detect_key, name_chord, placed_note
from audio_to_tab.lyrics import lyrics_skip_reason
from audio_to_tab.notation_view import (
    align_chords_to_lyrics,
    measure_rows,
    piano_roll_svg,
    tab_staff_svg,
)
from audio_to_tab.pdf_render import render_structured_tab_pdf
from audio_to_tab.player_bar import (
    PLAYER_SPEEDS,
    player_click_times,
    player_speed,
    synth_source_available,
)
from audio_to_tab.progress_checklist import apply_progress, new_checklist
from audio_to_tab.staff_wrap import wrap_tab_staff
from audio_to_tab.tab_bundle import (
    download_menu,
    downloads_after_run,
    format_size_kb,
    show_convert_action,
)
from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote, midi_to_tab, tab_to_ascii
from audio_to_tab.tuning import STANDARD_TUNING_MIDI, tuning_preset


def _write_midi(path: Path, groups: list[tuple[float, list[int]]]) -> Path:
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    for start, pitches in groups:
        for pitch in pitches:
            guitar.notes.append(pretty_midi.Note(100, pitch, start, start + 0.4))
    pm.instruments.append(guitar)
    pm.write(str(path))
    return path


def _long_doc() -> TabDocument:
    note = TabNote(start=0.0, end=20.0, string=5, fret=0, pitch=64)
    return TabDocument(events=[TabEvent(start=0.0, notes=[note])], tempo_bpm=120.0)


def test_wrap_splits_wide_staff_and_download_stays_raw():
    raw = tab_to_ascii(_long_doc())
    assert "--- Part" not in raw
    colored = []
    for line in raw.splitlines():
        if "|" in line and line[:1].isalpha():
            colored.append(f"\x1b[31m{line}\x1b[0m")
        else:
            colored.append(line)
    wrapped = wrap_tab_staff("\n".join(colored) + "\n")
    assert "\x1b" not in wrapped
    assert "--- Part 1/" in wrapped
    assert "--- Part 2/" in wrapped
    second = wrapped.split("--- Part 2/", 1)[1]
    assert "e|" in second
    assert "\n\n" in wrapped
    staff_lines = [line for line in wrapped.splitlines() if "|" in line and "Part" not in line]
    assert staff_lines
    assert max(len(line) for line in staff_lines) <= 100


def test_name_known_triads_from_pitch_classes():
    assert name_chord([60, 64, 67]) == "C"
    assert name_chord([67, 71, 74]) == "G"
    assert name_chord([57, 60, 64]) == "Am"
    assert name_chord([64]) is None


def test_chord_names_follow_grouped_midi(tmp_path: Path):
    path = _write_midi(
        tmp_path / "chords.mid",
        [(0.0, [60, 64, 67]), (1.0, [67, 71, 74])],
    )
    hits = chords_from_midi(path, transpose=0, capo=0, tuning_name="Standard (EADGBE)")
    assert [hit.name for hit in hits] == ["C", "G"]
    assert hits[0].start == pytest.approx(0.0)
    assert detect_key([60, 64, 67]) == "C major"


def test_capo_and_transpose_shift_pitch_and_chord_names(tmp_path: Path):
    path = _write_midi(tmp_path / "c.mid", [(0.0, [60, 64, 67]), (0.0, [64])])
    # The second group is the same onset, so the file is one C chord plus we
    # place the open E on its own file below.
    solo = _write_midi(tmp_path / "e.mid", [(0.0, [64])])
    base = placed_note(solo, transpose=0, capo=0, tuning_name="Standard (EADGBE)")
    assert base.pitch == 64
    assert base.pitch == STANDARD_TUNING_MIDI[base.string] + base.fret

    capo = placed_note(solo, transpose=0, capo=2, tuning_name="Standard (EADGBE)")
    tuning, _names = tuning_preset("Standard (EADGBE)")
    capo_tuning = tuple(note + 2 for note in tuning)
    assert capo.pitch == 66
    assert capo.pitch == capo_tuning[capo.string] + capo.fret

    shifted = placed_note(solo, transpose=2, capo=0, tuning_name="Standard (EADGBE)")
    assert shifted.pitch == 66
    assert shifted.pitch == STANDARD_TUNING_MIDI[shifted.string] + shifted.fret

    names = chords_from_midi(path, transpose=2, capo=0, tuning_name="Standard (EADGBE)")
    assert names[0].name == "D"
    capo_names = chords_from_midi(path, transpose=0, capo=2, tuning_name="Standard (EADGBE)")
    assert capo_names[0].name == "D"


def test_drop_d_changes_the_low_string(tmp_path: Path):
    path = _write_midi(tmp_path / "low.mid", [(0.0, [40])])
    standard = placed_note(path, transpose=0, capo=0, tuning_name="Standard (EADGBE)")
    dropped = placed_note(path, transpose=0, capo=0, tuning_name="Drop D")
    assert standard.fret == 0
    assert standard.string == 0
    assert dropped.fret == 2
    assert dropped.string == 0
    _midi, names = tuning_preset("Half-step down")
    assert _midi == tuple(note - 1 for note in STANDARD_TUNING_MIDI)
    assert names[0] == "Eb"


def test_consecutive_identical_chords_collapse(tmp_path: Path):
    path = _write_midi(
        tmp_path / "repeat.mid",
        [(0.0, [60, 64, 67]), (1.0, [60, 64, 67]), (2.0, [67, 71, 74])],
    )
    hits = chords_from_midi(path, transpose=0, capo=0, tuning_name="Standard (EADGBE)")
    assert [hit.name for hit in hits] == ["C", "G"]


def test_bars_per_line_changes_pdf_and_staff_rows(tmp_path: Path):
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    for index in range(8):
        guitar.notes.append(pretty_midi.Note(100, 64, index * 2.0, index * 2.0 + 0.4))
    pm.instruments.append(guitar)
    midi_path = tmp_path / "bars.mid"
    pm.write(str(midi_path))
    doc = midi_to_tab(str(midi_path), tempo_bpm=120.0, beats_per_measure=4)
    one = tmp_path / "one.pdf"
    eight = tmp_path / "eight.pdf"
    render_structured_tab_pdf(doc, str(one), measures_per_row=1)
    render_structured_tab_pdf(doc, str(eight), measures_per_row=8)
    assert one.read_bytes() != eight.read_bytes()
    assert len(measure_rows(8, 4)) == 2
    assert len(measure_rows(8, 1)) == 8
    assert tab_staff_svg(doc, bars_per_line=4).count('id="staff-row-') == 2
    assert tab_staff_svg(doc, bars_per_line=1).count('id="staff-row-') == 8


def test_piano_roll_transpose_moves_pitch_and_shows_measures():
    low = piano_roll_svg([(60, 0.0, 1.0)], tempo_bpm=120.0, beats_per_measure=4, semitones=0)
    high = piano_roll_svg([(60, 0.0, 1.0)], tempo_bpm=120.0, beats_per_measure=4, semitones=2)
    assert "C4" in low
    assert ">1<" in low or ">1</text>" in low
    assert "D4" in high
    assert "C4" not in high


def test_lyric_line_carries_the_chord_above_it():
    chords = [type("Hit", (), {"start": 1.0, "end": 1.4, "name": "C"})()]
    lines = [type("Line", (), {"start": 0.5, "end": 2.0, "text": "hello"})()]
    rows = align_chords_to_lyrics(chords, lines)
    assert rows[0]["chords"] == ["C"]
    assert rows[0]["text"] == "hello"
    bare = align_chords_to_lyrics(chords, [])
    assert bare[0]["text"] == ""
    assert bare[0]["chords"] == ["C"]


def test_checklist_marks_a_skip_and_ignores_unknown_stages():
    rows = new_checklist()
    rows = apply_progress(rows, "ingest", "Loading audio")
    rows = apply_progress(rows, "separate", "skipped: Separation is off")
    rows = apply_progress(rows, "tempo", "Estimating tempo")
    rows = apply_progress(rows, "transcribe", "Detecting notes")
    by_id = {row["id"]: row for row in rows}
    assert by_id["separate"]["state"] == "skipped"
    assert by_id["separate"]["detail"] == "Separation is off"
    assert by_id["ingest"]["state"] == "done"
    assert by_id["transcribe"]["state"] == "active"
    assert "tempo" not in by_id


def test_downloads_hide_missing_stem_and_unwritten_formats(tmp_path: Path):
    pdf = tmp_path / "transcription.pdf"
    midi = tmp_path / "transcription.mid"
    tab = tmp_path / "transcription.tab"
    pdf.write_bytes(b"%PDF")
    midi.write_bytes(b"MThd")
    tab.write_text("e|\n", encoding="utf-8")
    items = download_menu({"pdf": pdf, "midi": midi, "tab": tab, "playback": tmp_path / "playback.wav"})
    assert [item["key"] for item in items] == ["pdf", "midi", "tab"]
    assert downloads_after_run({"pdf": pdf}, failed=True) == []
    assert "musicxml" not in {item["key"] for item in items}


def test_player_speed_keeps_quarter_speed():
    from audio_to_tab.mixer import clamp_playback_rate

    assert PLAYER_SPEEDS == (0.25, 0.5, 0.75, 1.0)
    assert clamp_playback_rate(0.25) == 0.5
    assert player_speed(0.25) == 0.25
    assert player_speed(0.3) == 1.0
    clicks = player_click_times(duration_sec=2.0, bpm=120.0)
    assert clicks == pytest.approx([0.0, 0.5, 1.0, 1.5])
    assert synth_source_available() is False


def test_file_chip_and_convert_visibility():
    assert format_size_kb(1536) == "1.5 KB"
    assert show_convert_action(has_file=True, youtube_url="") is True
    assert show_convert_action(has_file=False, youtube_url="https://youtu.be/abcdefghijk") is True
    assert show_convert_action(has_file=False, youtube_url="https://example.com/song") is False


def test_lyrics_skip_reason_without_a_vocal_stem():
    reason = lyrics_skip_reason(None)
    assert reason is not None
    assert "vocal" in reason.lower()
    assert "not produced" in reason.lower() or "lyrics" in reason.lower()


def test_pipeline_skips_lyrics_without_vocal_and_still_writes_tab(tmp_path: Path, monkeypatch):
    from audio_to_tab.pipeline import PipelineConfig, run_pipeline
    from audio_to_tab.tempo import TempoEstimate

    source = tmp_path / "in.wav"
    source.write_bytes(b"not-a-real-wav")
    out = tmp_path / "out"

    def fake_normalize(src, dest):
        dest = Path(dest)
        dest.write_bytes(b"RIFF")
        return dest

    def fake_transcribe(audio, midi_path, **kwargs):
        _write_midi(Path(midi_path), [(0.0, [60, 64, 67])])

    monkeypatch.setattr("audio_to_tab.pipeline.normalize_audio", fake_normalize)
    monkeypatch.setattr("audio_to_tab.pipeline.transcribe_audio", fake_transcribe)
    monkeypatch.setattr(
        "audio_to_tab.pipeline.resolve_tempo",
        lambda **kwargs: TempoEstimate(bpm=120.0, confidence="high", source="override"),
    )
    monkeypatch.setattr(
        "audio_to_tab.pipeline._trim_audio",
        lambda path, max_duration_sec: path,
    )
    events: list[tuple[str, str]] = []
    artifacts = run_pipeline(
        audio_path=source,
        output_dir=out,
        config=PipelineConfig(
            separate_stems=False,
            max_duration_sec=None,
            mix_aware_filtering=False,
            title="Clip",
        ),
        on_progress=lambda stage, message: events.append((stage, message)),
    )
    stages = [stage for stage, _message in events]
    assert stages[:7] == ["ingest", "separate", "transcribe", "tab", "chords", "lyrics", "pdf"]
    lyric_messages = [message for stage, message in events if stage == "lyrics"]
    assert lyric_messages
    assert lyric_messages[0].startswith("skipped:")
    assert "vocal" in lyric_messages[0].lower()
    assert Path(artifacts["pdf"]).is_file()
    assert Path(artifacts["tab"]).is_file()
    assert "--- Part" not in Path(artifacts["tab"]).read_text(encoding="utf-8")
    assert Path(artifacts["playback"]).is_file()
    assert "guitar_stem" not in artifacts


def test_empty_transcription_writes_no_downloads(tmp_path: Path, monkeypatch):
    from audio_to_tab.pipeline import (
        EMPTY_TRANSCRIPTION_MESSAGE,
        EmptyTranscriptionError,
        PipelineConfig,
        run_pipeline,
    )

    source = tmp_path / "in.wav"
    source.write_bytes(b"x")
    out = tmp_path / "out"

    def fake_normalize(src, dest):
        Path(dest).write_bytes(b"RIFF")
        return Path(dest)

    def fake_transcribe(audio, midi_path, **kwargs):
        _write_midi(Path(midi_path), [(0.0, [64])])

    monkeypatch.setattr("audio_to_tab.pipeline.normalize_audio", fake_normalize)
    monkeypatch.setattr("audio_to_tab.pipeline.transcribe_audio", fake_transcribe)
    monkeypatch.setattr("audio_to_tab.pipeline._trim_audio", lambda path, max_duration_sec: path)

    with pytest.raises(EmptyTranscriptionError, match="cleaner solo-guitar clip"):
        run_pipeline(
            audio_path=source,
            output_dir=out,
            config=PipelineConfig(separate_stems=False, max_duration_sec=None),
        )
    assert "cleaner solo-guitar clip" in EMPTY_TRANSCRIPTION_MESSAGE
    assert not (out / "transcription.pdf").exists()
    assert not (out / "transcription.tab").exists()
    assert downloads_after_run({"pdf": out / "transcription.pdf"}, failed=True) == []


def test_page_keeps_current_guards_and_clears_failed_downloads():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    app = (page.parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'layout="wide"' in app
    assert "public YouTube links only" in source
    assert 'key="tab_separate_stems"' in source
    assert "Safer length (recommended)" in source
    assert "EmptyTranscriptionError" in source
    assert "carry_over_is_guitar_stem" not in source
    assert "MusicXML" not in source
    assert "LilyPond" not in source
    assert "Chords" in source and "Piano roll" in source
    assert "record_failure" in source
    from audio_to_tab.pipeline import EmptyTranscriptionError
    from ui.pages.tab_pdf import record_failure

    state = {"tab_pdf_artifacts": {"pdf": "old.pdf"}, "tab_pdf_flash": "done"}
    record_failure(state, EmptyTranscriptionError("A cleaner solo-guitar clip is needed."))
    assert "tab_pdf_artifacts" not in state
    assert "cleaner solo-guitar clip" in state["tab_pdf_error"]
