"""On-screen staff, piano roll, and chord diagrams drawn by this app."""

from __future__ import annotations

import json
import math
from html import escape
from typing import Any

from audio_to_tab.staff_wrap import wrap_tab_staff
from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote, tab_to_ascii
from audio_to_tab.tuning import midi_note_name

TAB_MEASURE_WIDTH = 180
TAB_ROW_HEIGHT = 96
TAB_ORIGIN_X = 40
TAB_ORIGIN_Y = 28
TAB_NOTE_INSET = 8
TAB_NOTE_PAD = 28
PIANO_ORIGIN_X = 48


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


def tab_playhead_layout(doc: TabDocument, *, bars_per_line: int = 4) -> dict[str, Any]:
    """Geometry shared by tab_staff_svg and the client playhead script."""
    bars = clamp_bars_per_line(bars_per_line)
    count = measure_count(doc)
    rows = measure_rows(count, bars)
    measure_width = TAB_MEASURE_WIDTH
    row_height = TAB_ROW_HEIGHT
    width = 48 + measure_width * max(1, max((end - start) for start, end in rows))
    height = 24 + row_height * len(rows)
    return {
        "mode": "tab",
        "measure_sec": float(_measure_seconds(doc)),
        "measure_width": measure_width,
        "row_height": row_height,
        "bars_per_line": bars,
        "measure_count": count,
        "row_count": len(rows),
        "origin_x": TAB_ORIGIN_X,
        "origin_y": TAB_ORIGIN_Y,
        "note_inset": TAB_NOTE_INSET,
        "note_span": measure_width - TAB_NOTE_PAD,
        "width": width,
        "height": height,
    }


def piano_roll_playhead_layout(
    notes: list[tuple[int, float, float]],
    *,
    tempo_bpm: float,
    beats_per_measure: int,
    semitones: int = 0,
) -> dict[str, Any]:
    """Geometry shared by piano_roll_svg and the client playhead script."""
    shifted = [(int(pitch) + int(semitones), float(start), float(end)) for pitch, start, end in notes]
    tempo = tempo_bpm if tempo_bpm > 0 else 120.0
    beats = max(1, int(beats_per_measure))
    measure_sec = 60.0 / tempo * beats
    if not shifted:
        return {
            "mode": "piano",
            "measure_sec": float(measure_sec),
            "end_time": float(measure_sec),
            "origin_x": PIANO_ORIGIN_X,
            "scale": 1.0,
            "width": 320,
            "height": 80,
        }
    end_time = max(note[2] for note in shifted)
    measures = max(1, math.ceil(end_time / measure_sec))
    low = min(pitch for pitch, _start, _end in shifted) - 1
    high = max(pitch for pitch, _start, _end in shifted) + 1
    if high <= low:
        high = low + 12
    width = max(320, int(measures * 160 + 56))
    height = 36 + (high - low + 1) * 10
    scale = (width - 64) / max(end_time, measure_sec)
    return {
        "mode": "piano",
        "measure_sec": float(measure_sec),
        "end_time": float(end_time),
        "origin_x": PIANO_ORIGIN_X,
        "scale": float(scale),
        "width": width,
        "height": height,
    }


def score_playhead_html(svg: str, layout: dict[str, Any]) -> str:
    """Wrap score SVG with a playhead synced to #tab-audio when present."""
    payload = json.dumps(layout)
    mode = escape(str(layout.get("mode") or "tab"))
    return f"""
<div class="studio-score-sync" data-mode="{mode}">
  <div class="studio-score-svg" id="studio-score-svg">{svg}</div>
  <div class="score-playhead" id="score-playhead" hidden aria-hidden="true"></div>
</div>
<script>
(function () {{
  const layout = {payload};
  const host = (document.currentScript && document.currentScript.previousElementSibling)
    || document.querySelector(".studio-score-sync:last-of-type");
  if (!host || !host.classList || !host.classList.contains("studio-score-sync")) return;
  const svgHost = host.querySelector(".studio-score-svg");
  const needle = host.querySelector(".score-playhead");
  if (!svgHost || !needle) return;
  const svg = svgHost.querySelector("svg");
  if (!svg) return;

  function audioEl() {{
    return document.getElementById("tab-audio");
  }}

  function tabPoint(now) {{
    const measureSec = layout.measure_sec || 1;
    const bars = layout.bars_per_line || 4;
    const measureIndex = Math.max(0, Math.floor(now / measureSec));
    if (measureIndex >= (layout.measure_count || 0)) {{
      return null;
    }}
    const row = Math.floor(measureIndex / bars);
    const col = measureIndex % bars;
    const rel = (now - measureIndex * measureSec) / measureSec;
    const x = layout.origin_x + col * layout.measure_width + layout.note_inset + rel * layout.note_span;
    const y0 = layout.origin_y + row * layout.row_height;
    const y1 = y0 + 60;
    return {{ x, y0, y1, row }};
  }}

  function pianoPoint(now) {{
    const end = layout.end_time || 0;
    if (end <= 0) return null;
    const x = layout.origin_x + Math.max(0, Math.min(now, end)) * layout.scale;
    return {{ x, y0: 22, y1: (layout.height || 80) - 8, row: 0 }};
  }}

  function place(now) {{
    const point = layout.mode === "piano" ? pianoPoint(now) : tabPoint(now);
    if (!point) {{
      needle.hidden = true;
      return;
    }}
    const box = svg.getBoundingClientRect();
    const hostBox = host.getBoundingClientRect();
    if (box.width <= 0 || box.height <= 0) {{
      needle.hidden = true;
      return;
    }}
    const sx = box.width / (layout.width || box.width);
    const sy = box.height / (layout.height || box.height);
    const left = (box.left - hostBox.left) + point.x * sx;
    const top = (box.top - hostBox.top) + point.y0 * sy;
    const height = Math.max(8, (point.y1 - point.y0) * sy);
    needle.hidden = false;
    needle.style.left = left + "px";
    needle.style.top = top + "px";
    needle.style.height = height + "px";
    if (layout.mode === "tab") {{
      const row = svg.querySelector("#staff-row-" + point.row);
      if (row && typeof row.scrollIntoView === "function") {{
        const prev = host.dataset.playheadRow;
        if (prev !== String(point.row)) {{
          host.dataset.playheadRow = String(point.row);
          row.scrollIntoView({{ block: "nearest", inline: "nearest" }});
        }}
      }}
    }}
  }}

  function tick() {{
    const audio = audioEl();
    if (!audio) {{
      needle.hidden = true;
      return;
    }}
    place(audio.currentTime || 0);
    if (!audio.paused && !audio.ended) requestAnimationFrame(tick);
  }}

  function start() {{
    const audio = audioEl();
    if (!audio) {{
      needle.hidden = true;
      return;
    }}
    place(audio.currentTime || 0);
    requestAnimationFrame(tick);
  }}

  function bind() {{
    const audio = audioEl();
    if (!audio || audio.dataset.scorePlayheadBound === "1") {{
      start();
      return;
    }}
    audio.dataset.scorePlayheadBound = "1";
    audio.addEventListener("play", start);
    audio.addEventListener("timeupdate", () => place(audio.currentTime || 0));
    audio.addEventListener("seeked", () => place(audio.currentTime || 0));
    audio.addEventListener("pause", () => place(audio.currentTime || 0));
    start();
  }}

  function seekFromEvent(event) {{
    const audio = audioEl();
    if (!audio || !svg) return;
    const box = svg.getBoundingClientRect();
    if (box.width <= 0) return;
    const relX = (event.clientX - box.left) / box.width;
    const viewX = relX * (layout.width || box.width);
    let now = 0;
    if (layout.mode === "piano") {{
      now = Math.max(0, (viewX - layout.origin_x) / (layout.scale || 1));
    }} else {{
      const bars = layout.bars_per_line || 4;
      const localY = ((event.clientY - box.top) / box.height) * (layout.height || box.height);
      const row = Math.max(0, Math.min((layout.row_count || 1) - 1,
        Math.floor((localY - layout.origin_y) / (layout.row_height || 96))));
      const localX = viewX - layout.origin_x;
      const col = Math.max(0, Math.min(bars - 1, Math.floor(localX / (layout.measure_width || 180))));
      const within = localX - col * layout.measure_width - layout.note_inset;
      const rel = Math.max(0, Math.min(1, within / (layout.note_span || 1)));
      const measureIndex = row * bars + col;
      now = measureIndex * (layout.measure_sec || 1) + rel * (layout.measure_sec || 1);
    }}
    audio.currentTime = Math.max(0, now);
    place(audio.currentTime);
  }}

  svg.style.cursor = "pointer";
  svg.addEventListener("click", seekFromEvent);
  bind();
  setTimeout(bind, 50);
  setTimeout(bind, 250);
}})();
</script>
<style>
.studio-score-sync {{
  position: relative;
}}
.studio-score-sync .score-playhead {{
  position: absolute;
  width: 2px;
  background: #e8a317;
  pointer-events: none;
  z-index: 2;
  box-shadow: 0 0 0 1px rgba(15, 17, 21, 0.35);
}}
</style>
"""


def tab_staff_svg(
    doc: TabDocument,
    *,
    bars_per_line: int = 4,
    ink: str = "#111",
    line: str = "#222",
) -> str:
    """Notation staff: six lines, fret numbers, and one row per bars-per-line group."""
    layout = tab_playhead_layout(doc, bars_per_line=bars_per_line)
    count = layout["measure_count"]
    rows = measure_rows(count, layout["bars_per_line"])
    measure_sec = layout["measure_sec"]
    row_height = layout["row_height"]
    measure_width = layout["measure_width"]
    width = layout["width"]
    height = layout["height"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" role="img" aria-label="Guitar tab">',
    ]
    labels = list(reversed(doc.tuning_names))
    for row_index, (row_start, row_end) in enumerate(rows):
        top = TAB_ORIGIN_Y + row_index * row_height
        parts.append(f'<g id="staff-row-{row_index}">')
        for column, measure_index in enumerate(range(row_start, row_end)):
            x = TAB_ORIGIN_X + column * measure_width
            for string_index in range(6):
                y = top + string_index * 12
                parts.append(
                    f'<line x1="{x}" y1="{y}" x2="{x + measure_width - 16}" y2="{y}" '
                    f'stroke="{line}" stroke-width="1"/>'
                )
                if column == 0:
                    parts.append(
                        f'<text x="8" y="{y + 3}" font-size="11" fill="{ink}">'
                        f"{escape(labels[string_index])}</text>"
                    )
            m_start = measure_index * measure_sec
            m_end = m_start + measure_sec
            for event in doc.events:
                if event.start < m_start or event.start >= m_end:
                    continue
                rel = (event.start - m_start) / measure_sec
                x_note = x + TAB_NOTE_INSET + rel * (measure_width - TAB_NOTE_PAD)
                for note in event.notes:
                    y_note = top + (5 - note.string) * 12
                    parts.append(
                        f'<text x="{x_note:.1f}" y="{y_note - 2}" font-size="12" '
                        f'font-weight="700" fill="{ink}">{int(note.fret)}</text>'
                    )
            parts.append(
                f'<text x="{x}" y="{top + 78}" font-size="11" fill="{ink}">{measure_index + 1}</text>'
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
    ink: str = "#111",
    line: str = "#bbb",
) -> str:
    """Time against sounding pitch, with measure numbers."""
    shifted = [(int(pitch) + int(semitones), float(start), float(end)) for pitch, start, end in notes]
    if not shifted:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="80"></svg>'
    layout = piano_roll_playhead_layout(
        notes,
        tempo_bpm=tempo_bpm,
        beats_per_measure=beats_per_measure,
        semitones=semitones,
    )
    measure_sec = layout["measure_sec"]
    end_time = layout["end_time"]
    measures = max(1, math.ceil(end_time / measure_sec))
    low = min(pitch for pitch, _start, _end in shifted) - 1
    high = max(pitch for pitch, _start, _end in shifted) + 1
    if high <= low:
        high = low + 12
    width = layout["width"]
    height = layout["height"]
    scale = layout["scale"]

    def y_for(pitch: int) -> float:
        return 24 + (high - pitch) * 10

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'width="100%" role="img" aria-label="Piano roll">',
    ]
    for index in range(measures):
        x = PIANO_ORIGIN_X + index * measure_sec * scale
        parts.append(f'<text x="{x:.1f}" y="16" font-size="12" fill="{ink}">{index + 1}</text>')
        parts.append(
            f'<line x1="{x:.1f}" y1="22" x2="{x:.1f}" y2="{height - 8}" stroke="{line}" stroke-width="1"/>'
        )
    for pitch, start, end in shifted:
        name = midi_note_name(min(127, max(0, pitch)))
        x = PIANO_ORIGIN_X + start * scale
        w = max(4.0, (end - start) * scale)
        y = y_for(pitch)
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="8" fill="{ink}" rx="1">'
            f"<title>{escape(name)}</title></rect>"
        )
        parts.append(
            f'<text x="{x + w + 4:.1f}" y="{y + 8:.1f}" font-size="11" fill="{ink}">{escape(name)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def chord_diagram_svg(
    name: str,
    frets: list[int | None] | tuple[int | None, ...],
    *,
    ink: str = "#111",
) -> str:
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
        f'font-weight="700" fill="{ink}">{escape(name)}</text>',
    ]
    if start > 1:
        parts.append(f'<text x="4" y="{top + 14}" font-size="11" fill="{ink}">{start}</text>')
    for string_index in range(6):
        x = left + string_index * string_gap
        parts.append(
            f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + 4 * fret_gap}" stroke="{ink}" stroke-width="1"/>'
        )
    for fret_index in range(5):
        y = top + fret_index * fret_gap
        weight = 3 if fret_index == 0 and start == 1 else 1
        parts.append(
            f'<line x1="{left}" y1="{y}" x2="{left + 5 * string_gap}" y2="{y}" '
            f'stroke="{ink}" stroke-width="{weight}"/>'
        )
    for string_index, fret in enumerate(values):
        x = left + string_index * string_gap
        if fret is None:
            parts.append(f'<text x="{x}" y="{top - 6}" text-anchor="middle" font-size="11" fill="{ink}">x</text>')
            continue
        if fret == 0:
            parts.append(
                f'<circle cx="{x}" cy="{top - 8}" r="4" fill="none" stroke="{ink}" stroke-width="1"/>'
            )
            continue
        row = fret - start + 1
        if row < 1 or row > 4:
            row = min(4, max(1, row))
        y = top + (row - 0.5) * fret_gap
        parts.append(f'<circle cx="{x}" cy="{y:.1f}" r="5" fill="{ink}"/>')
    parts.append("</svg>")
    return "".join(parts)


def chord_lyric_blocks(chords, lines) -> list[dict]:
    """Chords per lyric line, each with a character offset inside the line text.

    Every chord is kept exactly once, assigned with the same overlap / nearest
    fallback as align_chords_to_lyrics. Chords are in ascending start order;
    ties share an offset and stay in start order.

    With no lyric lines the fallback is one block per chord: the chord name at
    offset 0 and the chord start time in "start", so the caller can render a
    chord + clock timeline.
    """
    if not lines:
        return [
            {
                "text": "",
                "chords": [{"offset": 0, "name": str(chord.name)}],
                "start": float(chord.start),
            }
            for chord in chords
        ]
    line_chords: list[list[dict]] = [[] for _line in lines]
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
        line = lines[best_index]
        text = str(line.text)
        span = max(float(line.end) - float(line.start), 0.05)
        offset = round((float(chord.start) - float(line.start)) / span * len(text))
        offset = max(0, min(len(text) - 1, offset)) if text else 0
        line_chords[best_index].append({"offset": offset, "name": str(chord.name)})
    return [
        {
            "text": str(lines[index].text),
            "chords": sorted(line_chords[index], key=lambda item: item["offset"]),
            "start": float(lines[index].start),
        }
        for index in range(len(lines))
    ]


def chord_row_string(chords: list[dict]) -> str:
    """Chord-row text with names padded to their character offsets.

    Chords whose offset would collide with the previous name are separated by
    one space instead. Chord names are HTML-escaped.
    """
    parts: list[str] = []
    cursor = 0
    for item in chords:
        raw = str(item["name"])
        name = escape(raw)
        offset = int(item["offset"])
        if offset < cursor:
            parts.append(" " + name)
        else:
            parts.append(" " * (offset - cursor) + name)
        cursor = max(cursor, offset) + len(raw)
    return "".join(parts)


def chord_lyric_block_html(block: dict) -> str:
    """One aligned chord row above its lyric row, everything HTML-escaped."""
    chord_row = chord_row_string(block["chords"])
    lyric_row = escape(str(block["text"]))
    start = float(block.get("start") or 0.0)
    return (
        f'<div class="chord-lyric" data-start="{start}">'
        f'<div class="chord-row">{chord_row or "&nbsp;"}</div>'
        f'<div class="lyric-row">{lyric_row or "&nbsp;"}</div>'
        "</div>"
    )


def chords_playhead_html(body: str) -> str:
    """Wrap chord blocks so the active chord highlights from #tab-audio time."""
    return f"""
<div class="studio-chords-sync" id="studio-chords-sync">
{body}
</div>
<script>
(function () {{
  const host = document.querySelector(".studio-chords-sync:last-of-type");
  if (!host) return;
  const blocks = Array.from(host.querySelectorAll(".chord-lyric[data-start]"));
  if (!blocks.length) return;
  const starts = blocks.map((el) => Number(el.getAttribute("data-start") || 0));

  function audioEl() {{
    return document.getElementById("tab-audio");
  }}

  function paint(now) {{
    let active = -1;
    for (let i = 0; i < starts.length; i += 1) {{
      const next = i + 1 < starts.length ? starts[i + 1] : Infinity;
      if (now >= starts[i] && now < next) {{
        active = i;
        break;
      }}
    }}
    blocks.forEach((el, index) => {{
      el.classList.toggle("is-active", index === active);
    }});
  }}

  function tick() {{
    const audio = audioEl();
    if (!audio) return;
    paint(audio.currentTime || 0);
    if (!audio.paused && !audio.ended) requestAnimationFrame(tick);
  }}

  function bind() {{
    const audio = audioEl();
    if (!audio) return;
    if (audio.dataset.chordsPlayheadBound !== "1") {{
      audio.dataset.chordsPlayheadBound = "1";
      audio.addEventListener("play", () => requestAnimationFrame(tick));
      audio.addEventListener("timeupdate", () => paint(audio.currentTime || 0));
      audio.addEventListener("seeked", () => paint(audio.currentTime || 0));
    }}
    paint(audio.currentTime || 0);
    if (!audio.paused) requestAnimationFrame(tick);
  }}
  bind();
  setTimeout(bind, 50);
  setTimeout(bind, 250);
}})();
</script>
"""


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
