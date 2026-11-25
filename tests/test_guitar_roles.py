"""Bar-level lead/rhythm role check on transcribed stems (texture cues only)."""

from dataclasses import dataclass

from audio_to_tab.guitar_roles import assign_roles, bar_features, bar_starts, texture_label

BAR = 2.0  # 120 BPM, 4/4


@dataclass
class N:
    pitch: int
    start: float
    end: float
    velocity: int = 90


def chords(bar: int, shape=(40, 47, 52), hits=4) -> list[N]:
    out = []
    for k in range(hits):
        t = bar * BAR + k * BAR / hits
        out.extend(N(p, t, t + 0.4) for p in shape)
    return out


def line(bar: int, pitches) -> list[N]:
    step = BAR / len(pitches)
    return [N(p, bar * BAR + i * step, bar * BAR + (i + 1) * step) for i, p in enumerate(pitches)]


SOLO_A = [64, 66, 67, 69, 71, 69, 67, 66]
SOLO_B = [72, 71, 69, 71, 72, 74, 76, 74]
RIFF = [52, 55, 57, 55, 52, 55, 57, 59]
ARPEGGIO = [45, 52, 57, 60, 64, 60, 57, 52]  # A minor spelled out


def _run(lead, rhythm, bars=4):
    return assign_roles(lead, rhythm, downbeats=[i * BAR for i in range(bars + 1)], tempo_bpm=120.0)


def test_bar_starts_fill_missing_downbeats_and_reach_the_end():
    starts = bar_starts(downbeats=[0.0, 2.0, 6.0], tempo_bpm=120.0, beats_per_measure=4, end_time=9.0)
    assert starts == [0.0, 2.0, 4.0, 6.0, 8.0]


def test_texture_labels_follow_polyphony_and_chord_outline():
    starts = [0.0, 2.0, 4.0]
    notes = [*chords(0), *line(1, SOLO_A), *line(2, ARPEGGIO)]
    labels = [texture_label(f) for f in bar_features(notes, starts, 6.0)]
    assert labels == ["chords", "line", "arpeggio"]


def test_lead_heard_again_in_the_rhythm_residual_is_removed_but_chord_tones_stay():
    lead = line(0, SOLO_A)
    bleed = [N(66, lead[1].start + 0.01, lead[1].end)]
    chord_copy = [N(64, 0.0, 0.4), N(59, 0.0, 0.4), N(55, 0.0, 0.4)]  # 64 also starts the lead
    new_lead, new_rhythm, report = _run(lead, [*bleed, *chord_copy])
    assert report.bleed_removed == 1
    assert sorted(n.pitch for n in new_rhythm) == [55, 59, 64]
    assert len(new_lead) == len(lead)


def test_solo_filed_as_rhythm_while_lead_is_silent_moves_to_lead():
    rhythm = [*chords(0), *chords(1), *line(2, SOLO_A), *line(3, SOLO_B)]
    lead = line(0, SOLO_B[:1])  # lead stem nearly silent
    new_lead, new_rhythm, report = _run(lead, rhythm)
    assert [m.bar for m in report.moves] == [3, 4]
    assert all(m.to_stem == "lead" for m in report.moves)
    assert {n.pitch for n in new_lead} >= set(SOLO_A) | set(SOLO_B)
    assert all(n.start < 2 * BAR for n in new_rhythm)


def test_repeating_single_note_riff_stays_rhythm():
    rhythm = [*line(0, RIFF), *line(1, RIFF), *line(2, RIFF), *line(3, RIFF)]
    _, new_rhythm, report = _run([], rhythm)
    assert report.moves == []
    assert len(new_rhythm) == len(rhythm)


def test_repeating_arpeggio_in_lead_with_no_rhythm_moves_to_rhythm():
    lead = [*line(0, ARPEGGIO), *line(1, ARPEGGIO)]
    new_lead, new_rhythm, report = _run(lead, [], bars=2)
    assert [m.to_stem for m in report.moves] == ["rhythm", "rhythm"]
    assert new_lead == []
    assert len(new_rhythm) == len(lead)


def test_a_lone_weak_bar_is_not_moved():
    # One short non-repeating line (5 onsets) with no agreeing neighbour: too little evidence.
    rhythm = [*chords(0), *line(1, [64, 66, 67, 69, 71]), *chords(2), *chords(3)]
    _, new_rhythm, report = _run([], rhythm)
    assert report.moves == []
    assert len(new_rhythm) == len(rhythm)


def test_chords_with_lead_playing_change_nothing():
    lead = [*line(0, SOLO_A), *line(1, SOLO_B)]
    rhythm = [*chords(0), *chords(1)]
    new_lead, new_rhythm, report = _run(lead, rhythm, bars=2)
    assert report.moves == [] and report.bleed_removed == 0
    assert new_lead == sorted(lead, key=lambda n: (n.start, n.pitch))
    assert len(new_rhythm) == len(rhythm)


def test_bars_follow_the_beat_grid_when_downbeats_are_noisy():
    beats = [0.5 * i for i in range(17)]
    noisy_downbeats = [0.0, 1.0, 2.0, 4.0, 5.0, 6.0]  # every other beat, sometimes
    starts = bar_starts(
        downbeats=noisy_downbeats, beats=beats, tempo_bpm=120.0, beats_per_measure=4, end_time=8.0
    )
    assert starts[:4] == [0.0, 2.0, 4.0, 6.0]


# --- chords found in the lead stem lean to rhythm ---------------------------------------------


def test_lead_stem_chord_goes_to_rhythm_when_rhythm_is_silent():
    chord = [N(52, 4.0, 4.5), N(55, 4.0, 4.5), N(59, 4.01, 4.5)]
    lead = [*line(0, SOLO_A), N(55, 4.0, 4.5)]  # the monophonic lead path kept one chord note
    rhythm = chords(0)  # rhythm only plays in bar 1
    new_lead, new_rhythm, report = assign_roles(
        lead, rhythm, downbeats=[0, 2, 4, 6], tempo_bpm=120.0, lead_chords=[chord]
    )
    assert report.chords_to_rhythm == 1 and report.chords_left == 0
    assert all(abs(n.start - 4.0) > 0.05 for n in new_lead)
    assert {52, 55, 59} <= {n.pitch for n in new_rhythm if abs(n.start - 4.0) < 0.05}
    assert report.to_dict()["chords_to_rhythm"] == 1


def test_lead_stem_chord_over_a_rhythm_strum_is_left_alone():
    chord = [N(52, 0.0, 0.4), N(55, 0.0, 0.4), N(59, 0.0, 0.4)]
    lead = [*line(0, SOLO_A)]
    rhythm = chords(0)  # a strum at 0.0 already
    new_lead, new_rhythm, report = assign_roles(
        lead, rhythm, downbeats=[0, 2], tempo_bpm=120.0, lead_chords=[chord]
    )
    assert report.chords_to_rhythm == 0 and report.chords_left == 1
    assert len(new_rhythm) == len(rhythm)
    assert len(new_lead) == len(lead)
