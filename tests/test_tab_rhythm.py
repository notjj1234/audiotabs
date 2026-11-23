"""Duration snap and beam grouping for Songsterr-style tab rhythm glyphs."""

from __future__ import annotations

from audio_to_tab.notation_view import chord_diagram_svg, piano_roll_svg, tab_staff_svg
from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote
from audio_to_tab.tab_rhythm import beam_groups, snap_duration


def test_snap_quarter_at_120_bpm():
    value = snap_duration(0.5, tempo_bpm=120.0)
    assert value.type_name == "quarter"
    assert value.flags == 0
    assert value.dotted is False


def test_snap_eighth_and_sixteenth():
    eighth = snap_duration(0.25, tempo_bpm=120.0)
    assert eighth.type_name == "eighth"
    assert eighth.flags == 1
    sixteenth = snap_duration(0.125, tempo_bpm=120.0)
    assert sixteenth.type_name == "16th"
    assert sixteenth.flags == 2


def test_snap_dotted_quarter():
    value = snap_duration(0.75, tempo_bpm=120.0)
    assert value.type_name == "quarter"
    assert value.dotted is True
    assert value.flags == 0


def test_beam_groups_pair_of_eighths_in_one_beat():
    # 120 BPM: beat = 0.5s; two eighths at 0.0 and 0.25
    events = [
        TabEvent(
            start=0.0,
            notes=[TabNote(start=0.0, end=0.25, string=0, fret=0, pitch=40)],
        ),
        TabEvent(
            start=0.25,
            notes=[TabNote(start=0.25, end=0.5, string=0, fret=3, pitch=43)],
        ),
    ]
    groups = beam_groups(events, tempo_bpm=120.0, beats_per_measure=4)
    assert groups == [[0, 1]]


def test_beam_groups_skips_quarters():
    events = [
        TabEvent(
            start=0.0,
            notes=[TabNote(start=0.0, end=0.5, string=0, fret=0, pitch=40)],
        ),
        TabEvent(
            start=0.5,
            notes=[TabNote(start=0.5, end=1.0, string=0, fret=3, pitch=43)],
        ),
    ]
    groups = beam_groups(events, tempo_bpm=120.0, beats_per_measure=4)
    assert groups == []


def test_beam_groups_preserves_member_indices_when_list_unsorted():
    # Insertion order is late then early; time order still beams both.
    events = [
        TabEvent(
            start=0.25,
            notes=[TabNote(start=0.25, end=0.5, string=0, fret=3, pitch=43)],
        ),
        TabEvent(
            start=0.0,
            notes=[TabNote(start=0.0, end=0.25, string=0, fret=0, pitch=40)],
        ),
    ]
    groups = beam_groups(events, tempo_bpm=120.0, beats_per_measure=4)
    assert groups == [[1, 0]]


def test_tab_staff_defaults_to_dark_theme_ink():
    doc = TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=0.5, string=0, fret=3, pitch=40)],
            )
        ],
        tempo_bpm=120.0,
    )
    svg = tab_staff_svg(doc, bars_per_line=4)
    assert 'fill="#f4f7fb"' in svg
    assert 'stroke="#8fa0b5"' in svg
    assert 'fill="#111"' not in svg


def test_piano_and_chord_defaults_match_dark_ink():
    piano = piano_roll_svg([(60, 0.0, 0.5)], tempo_bpm=120.0, beats_per_measure=4)
    assert 'fill="#f4f7fb"' in piano
    chord = chord_diagram_svg("E", [0, 2, 2, 1, 0, 0])
    assert 'fill="#f4f7fb"' in chord or 'stroke="#f4f7fb"' in chord


def test_tab_staff_draws_stem_for_quarter():
    doc = TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=0.5, string=0, fret=3, pitch=40)],
            )
        ],
        tempo_bpm=120.0,
    )
    svg = tab_staff_svg(doc, bars_per_line=4)
    assert 'class="tab-stem"' in svg or 'data-rhythm="stem"' in svg


def test_tab_staff_beams_pair_of_eighths():
    doc = TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=0.25, string=0, fret=0, pitch=40)],
            ),
            TabEvent(
                start=0.25,
                notes=[TabNote(start=0.25, end=0.5, string=0, fret=3, pitch=43)],
            ),
        ],
        tempo_bpm=120.0,
    )
    svg = tab_staff_svg(doc, bars_per_line=4)
    assert 'class="tab-beam"' in svg or 'data-rhythm="beam"' in svg


def test_tab_staff_flags_lone_sixteenth():
    doc = TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=0.125, string=0, fret=5, pitch=45)],
            )
        ],
        tempo_bpm=120.0,
    )
    svg = tab_staff_svg(doc, bars_per_line=4)
    assert 'class="tab-flag"' in svg or 'data-rhythm="flag"' in svg
