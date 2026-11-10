"""On-screen staff, piano roll, and chord diagrams drawn by this app."""

from __future__ import annotations

import math
from html import escape

from audio_to_tab.staff_wrap import wrap_tab_staff
from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote, tab_to_ascii
from audio_to_tab.tuning import midi_note_name


def clamp_bars_per_line(value: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 4
    return min(8, max(1, number))


def measure_rows(count: int, bars_per_line: int) -> list[tuple[int, int]]:
    step = clamp_bars_per_line(bars_per_line)
    total = max(1, int(count))
    return [(start, min(total, start + step)) for start in range(0, total, step)]


def measure_count(doc: TabDocument) -> int:
    tempo = float(doc.tempo_bpm) if doc.tempo_bpm and doc.tempo_bpm > 0 else 120.0
    beats = max(1, int(doc.beats_per_measure))
    measure_sec = 60.0 / tempo * beats
    if not math.isfinite(measure_sec) or measure_sec <= 0:
        return 1
    end_time = max((note.end for event in doc.events for note in event.notes), default=measure_sec)
    return max(1, math.ceil(end_time / measure_sec))


def _measure_seconds(doc: TabDocument) -> float:
    tempo = float(doc.tempo_bpm) if doc.tempo_bpm and doc.tempo_bpm > 0 else 120.0
    beats = max(1, int(doc.beats_per_measure))
    return 60.0 / tempo * beats


def tab_staff_svg(doc: TabDocument, *, bars_per_line: int = 4) -> str:
    """Notation staff: six lines, fret numbers, and one row per bars-per-line group."""
    count = measure_count(doc)
    rows = measure_rows(count, bars_per_line)
    measure_sec = _measure_seconds(doc)
    row_height = 96
    measure_width = 180
    width = 48 + measure_width * max(1, max((end - start) for start, end in rows))
    height = 24 + row_height * len(rows)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" role="img" aria-label="Guitar tab">',
    ]
    labels = list(reversed(doc.tuning_names))
    for row_index, (row_start, row_end) in enumerate(rows):
        top = 28 + row_index * row_height
        parts.append(f'<g id="staff-row-{row_index}">')
        for column, measure_index in enumerate(range(row_start, row_end)):
            x = 40 + column * measure_width
            for string_index in range(6):
                y = top + string_index * 12
                parts.append(
                    f'<line x1="{x}" y1="{y}" x2="{x + measure_width - 16}" y2="{y}" '
                    'stroke="#222" stroke-width="1"/>'
                )
                if column == 0:
                    parts.append(
                        f'<text x="8" y="{y + 3}" font-size="11" fill="#111">'
                        f"{escape(labels[string_index])}</text>"
                    )
            m_start = measure_index * measure_sec
            m_end = m_start + measure_sec
            for event in doc.events:
                if event.start < m_start or event.start >= m_end:
                    continue
                rel = (event.start - m_start) / measure_sec
                x_note = x + 8 + rel * (measure_width - 28)
                for note in event.notes:
                    y_note = top + (5 - note.string) * 12
                    parts.append(
                        f'<text x="{x_note:.1f}" y="{y_note - 2}" font-size="12" '
                        f'font-weight="700" fill="#111">{int(note.fret)}</text>'
                    )
            parts.append(
                f'<text x="{x}" y="{top + 78}" font-size="11" fill="#111">{measure_index + 1}</text>'
            )
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


def _slice_document(doc: TabDocument, start: float, end: float) -> TabDocument:
    local_events: list[TabEvent] = []
    for event in doc.events:
        notes: list[TabNote] = []
        for note in event.notes:
            if note.end <= start or note.start >= end:
                continue
            notes.append(
                TabNote(
                    start=max(0.0, note.start - start),
                    end=min(end - start, note.end - start),
                    string=note.string,
                    fret=note.fret,
                    pitch=note.pitch,
                )
            )
        if notes:
            local_events.append(TabEvent(start=min(note.start for note in notes), notes=notes))
    return TabDocument(
        events=local_events,
        tuning_names=doc.tuning_names,
        tempo_bpm=doc.tempo_bpm,
        tempo_confidence=doc.tempo_confidence,
        beats_per_measure=doc.beats_per_measure,
    )


def screen_tab_text(doc: TabDocument, bars_per_line: int = 4) -> str:
    """Wrapped ASCII for the text view. One block per bars-per-line row."""
    measure_sec = _measure_seconds(doc)
    blocks: list[str] = []
    for index, (row_start, row_end) in enumerate(measure_rows(measure_count(doc), bars_per_line)):
        sliced = _slice_document(doc, row_start * measure_sec, row_end * measure_sec)
        raw = tab_to_ascii(sliced)
        if index:
            raw = raw.split("\n\n", 1)[-1]
        blocks.append(wrap_tab_staff(raw).strip("\n"))
    return "\n\n".join(blocks) + "\n"


def piano_roll_svg(
    notes: list[tuple[int, float, float]],
    *,
    tempo_bpm: float,
    beats_per_measure: int,
    semitones: int = 0,
) -> str:
    """Time against sounding pitch, with measure numbers."""
    shifted = [(int(pitch) + int(semitones), float(start), float(end)) for pitch, start, end in notes]
    if not shifted:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="80"></svg>'
    tempo = tempo_bpm if tempo_bpm > 0 else 120.0
    beats = max(1, int(beats_per_measure))
    measure_sec = 60.0 / tempo * beats
    end_time = max(note[2] for note in shifted)
    measures = max(1, math.ceil(end_time / measure_sec))
    low = min(pitch for pitch, _start, _end in shifted) - 1
    high = max(pitch for pitch, _start, _end in shifted) + 1
    if high <= low:
        high = low + 12
    width = max(320, int(measures * 160 + 56))
    height = 36 + (high - low + 1) * 10
    scale = (width - 64) / max(end_time, measure_sec)

    def y_for(pitch: int) -> float:
        return 24 + (high - pitch) * 10

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'width="100%" role="img" aria-label="Piano roll">',
    ]
    for index in range(measures):
        x = 48 + index * measure_sec * scale
        parts.append(f'<text x="{x:.1f}" y="16" font-size="12" fill="#111">{index + 1}</text>')
        parts.append(
            f'<line x1="{x:.1f}" y1="22" x2="{x:.1f}" y2="{height - 8}" stroke="#bbb" stroke-width="1"/>'
        )
    for pitch, start, end in shifted:
        name = midi_note_name(min(127, max(0, pitch)))
        x = 48 + start * scale
        w = max(4.0, (end - start) * scale)
        y = y_for(pitch)
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="8" fill="#222" rx="1">'
            f"<title>{escape(name)}</title></rect>"
        )
        parts.append(
            f'<text x="{x + w + 4:.1f}" y="{y + 8:.1f}" font-size="11" fill="#111">{escape(name)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def chord_diagram_svg(name: str, frets: list[int | None] | tuple[int | None, ...]) -> str:
    """Six-string diagram. Fret 0 is open. None is a muted string."""
    values = list(frets[:6]) + [None] * (6 - len(list(frets[:6])))
    played = [fret for fret in values if isinstance(fret, int) and fret > 0]
    start = 1 if not played or min(played) <= 1 else min(played)
    if any(fret == 0 for fret in values if isinstance(fret, int)):
        start = 1
    width = 120
    height = 150
    left = 28
    top = 36
    string_gap = 14
    fret_gap = 18
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'role="img" aria-label="Chord {escape(name)}">',
        f'<text x="{width / 2}" y="18" text-anchor="middle" font-size="14" '
        f'font-weight="700" fill="#111">{escape(name)}</text>',
    ]
    if start > 1:
        parts.append(f'<text x="4" y="{top + 14}" font-size="11" fill="#111">{start}</text>')
    for string_index in range(6):
        x = left + string_index * string_gap
        parts.append(
            f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + 4 * fret_gap}" stroke="#222" stroke-width="1"/>'
        )
    for fret_index in range(5):
        y = top + fret_index * fret_gap
        weight = 3 if fret_index == 0 and start == 1 else 1
        parts.append(
            f'<line x1="{left}" y1="{y}" x2="{left + 5 * string_gap}" y2="{y}" '
            f'stroke="#222" stroke-width="{weight}"/>'
        )
    for string_index, fret in enumerate(values):
        x = left + string_index * string_gap
        if fret is None:
            parts.append(f'<text x="{x}" y="{top - 6}" text-anchor="middle" font-size="11" fill="#111">x</text>')
            continue
        if fret == 0:
            parts.append(
                f'<circle cx="{x}" cy="{top - 8}" r="4" fill="none" stroke="#222" stroke-width="1"/>'
            )
            continue
        row = fret - start + 1
        if row < 1 or row > 4:
            row = min(4, max(1, row))
        y = top + (row - 0.5) * fret_gap
        parts.append(f'<circle cx="{x}" cy="{y:.1f}" r="5" fill="#222"/>')
    parts.append("</svg>")
    return "".join(parts)


def align_chords_to_lyrics(chords, lines) -> list[dict]:
    """Put each chord on the lyric line it overlaps. No lyrics leaves a timeline."""
    if not lines:
        return [
            {"chords": [chord.name], "text": "", "start": float(chord.start)}
            for chord in chords
        ]
    buckets: list[list[str]] = [[] for _line in lines]
    for chord in chords:
        best_index = 0
        best_overlap = -1.0
        for index, line in enumerate(lines):
            overlap = min(float(chord.end), float(line.end)) - max(float(chord.start), float(line.start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_index = index
        if best_overlap <= 0:
            best_index = min(
                range(len(lines)),
                key=lambda index: abs(float(lines[index].start) - float(chord.start)),
            )
        buckets[best_index].append(chord.name)
    return [
        {
            "chords": buckets[index],
            "text": lines[index].text,
            "start": float(lines[index].start),
        }
        for index in range(len(lines))
    ]
