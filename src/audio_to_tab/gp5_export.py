"""Optional Guitar Pro 5 export through PyGuitarPro."""

from __future__ import annotations

import importlib.util
from collections import defaultdict
from pathlib import Path

from audio_to_tab.tab_generate import TabDocument, TabNote

GP5_INSTALL_HINT = 'GP5 export needs the optional extra: pip install -e ".[gp5]"'
SIXTEENTH_TICKS = 240
SUPPORTED_DURATIONS = (3840, 2880, 1920, 1440, 960, 720, 480, 360, 240)


def _duration_ticks(seconds: float, tempo_bpm: float) -> int:
    ticks = seconds * tempo_bpm * 960.0 / 60.0
    return max(0, round(ticks / SIXTEENTH_TICKS) * SIXTEENTH_TICKS)


def _note_segments(doc: TabDocument) -> dict[int, list[tuple[int, int, list[tuple[TabNote, bool]]]]]:
    measure_ticks = doc.beats_per_measure * 960
    grouped: dict[tuple[int, int], tuple[int, list[tuple[TabNote, bool]]]] = {}
    for event in doc.events:
        for note in event.notes:
            note_start = _duration_ticks(note.start, doc.tempo_bpm)
            note_end = max(note_start + SIXTEENTH_TICKS, _duration_ticks(note.end, doc.tempo_bpm))
            segment_start = note_start
            while segment_start < note_end:
                measure_index = segment_start // measure_ticks
                measure_end = (measure_index + 1) * measure_ticks
                segment_end = min(note_end, measure_end)
                relative_start = segment_start - measure_index * measure_ticks
                relative_end = segment_end - measure_index * measure_ticks
                key = (measure_index, relative_start)
                tied = segment_start > note_start
                if key in grouped:
                    prior_end, notes = grouped[key]
                    if any(existing.string == note.string for existing, _tied in notes):
                        segment_start = segment_end
                        continue
                    notes.append((note, tied))
                    grouped[key] = (max(prior_end, relative_end), notes)
                else:
                    grouped[key] = (relative_end, [(note, tied)])
                segment_start = segment_end

    measures: dict[int, list[tuple[int, int, list[tuple[TabNote, bool]]]]] = defaultdict(list)
    for (measure_index, start), (end, notes) in grouped.items():
        measures[measure_index].append((start, end, notes))
    for groups in measures.values():
        groups.sort(key=lambda group: group[0])
    return measures


def _append_beat(voice, start: int, duration: int, notes: list[tuple[TabNote, bool]], tied: bool) -> None:
    import guitarpro

    status = guitarpro.BeatStatus.rest if not notes else guitarpro.BeatStatus.normal
    remaining = duration
    beat_start = start
    first = True
    while remaining > 0:
        ticks = next(value for value in SUPPORTED_DURATIONS if value <= remaining)
        beat = guitarpro.Beat(
            voice,
            start=beat_start,
            duration=guitarpro.Duration.fromTime(ticks),
            status=status,
        )
        if notes:
            for note, cross_measure_tie in notes:
                note_type = (
                    guitarpro.NoteType.normal
                    if first and not tied and not cross_measure_tie
                    else guitarpro.NoteType.tie
                )
                beat.notes.append(
                    guitarpro.Note(
                        beat,
                        value=note.fret,
                        string=6 - note.string,
                        type=note_type,
                    )
                )
        voice.beats.append(beat)
        beat_start += ticks
        remaining -= ticks
        first = False


def _assign_tracks(
    groups: list[tuple[int, int, list[tuple[TabNote, bool]]]],
) -> list[list[list[tuple[int, int, list[tuple[TabNote, bool]]]]]]:
    """Assign rhythm groups to two-voice tracks without dropping overlaps."""
    tracks: list[list[list[tuple[int, int, list[tuple[TabNote, bool]]]]]] = []
    for group in groups:
        start, _end, _notes = group
        for voices in tracks:
            for index in range(2):
                if not voices[index] or voices[index][-1][1] <= start:
                    voices[index].append(group)
                    break
            else:
                continue
            break
        else:
            tracks.append([[group], []])
    return tracks


def _fill_measure(voice, groups: list[tuple[int, int, list[tuple[TabNote, bool]]]], measure_ticks: int) -> None:
    cursor = 0
    for start, end, notes in groups:
        if start < cursor:
            continue
        if start > cursor:
            _append_beat(voice, cursor, start - cursor, [], tied=False)
        _append_beat(voice, start, end - start, notes, tied=False)
        cursor = end
    if cursor < measure_ticks:
        _append_beat(voice, cursor, measure_ticks - cursor, [], tied=False)


def write_guitar_pro(doc: TabDocument, output_path: str | Path, *, title: str) -> Path:
    """Write a quantized tab document as GP5, preserving fret/string assignments."""
    if importlib.util.find_spec("guitarpro") is None:
        raise RuntimeError(GP5_INSTALL_HINT)
    import guitarpro

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    song = guitarpro.Song(title=title, tempo=max(1, round(doc.tempo_bpm)))
    measure_ticks = doc.beats_per_measure * 960
    measures = _note_segments(doc)
    assigned_measures = {
        index: _assign_tracks(groups) for index, groups in measures.items()
    }
    measure_count = max(1, max(measures, default=0) + 1)
    while len(song.measureHeaders) < measure_count:
        song.newMeasure()

    track_count = max(
        1,
        max((len(assigned) for assigned in assigned_measures.values()), default=1),
    )
    while len(song.tracks) < track_count:
        song.tracks.append(guitarpro.Track(song, number=len(song.tracks) + 1))

    for index, header in enumerate(song.measureHeaders):
        header.number = index + 1
        header.timeSignature.numerator = doc.beats_per_measure
        header.start = 960 + index * measure_ticks

    open_pitches = [64, 59, 55, 50, 45, 40]
    for event in doc.events:
        for note in event.notes:
            open_pitches[5 - note.string] = note.pitch - note.fret
    for index, track in enumerate(song.tracks):
        track.name = title if index == 0 else f"{title} (overflow {index})"
        track.strings = [
            guitarpro.GuitarString(number=string_index + 1, value=value)
            for string_index, value in enumerate(open_pitches)
        ]

    for track_index, track in enumerate(song.tracks):
        for measure_index, measure in enumerate(track.measures):
            track_groups = assigned_measures.get(measure_index, [])
            voice_groups = (
                track_groups[track_index] if track_index < len(track_groups) else [[], []]
            )
            for voice, groups in zip(measure.voices, voice_groups, strict=True):
                _fill_measure(voice, groups, measure_ticks)
    guitarpro.write(song, str(output))
    return output
