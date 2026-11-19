"""Minimal dependency-free MusicXML 4.0 writer for tab documents.

One ``<part>`` per TabDocument, each rendered as a 6-line TAB staff:
``<staff-details>`` with ``<staff-tuning>``, a TAB clef, and per-note
``<notations><technical><string>/<fret>`` so MuseScore / Dorico / Guitar Pro
can display the tablature directly. Standard-library ``xml.etree`` only —
no music21, no partitura.

Scope notes (deliberately minimal):
- Rhythmic values are approximated to the nearest note type; the tab staff
  is the authoritative representation, playback timing is not.
- ``<staff-tuning>`` is derived from ``TabDocument.tuning_names`` snapped to
  standard-guitar octaves (E2 A2 D3 G3 B3 E4); non-standard tunings render
  correctly when they stay within a few semitones of standard.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from audio_to_tab.tab_generate import TabDocument, TabNote

DIVISIONS = 480  # ticks per quarter note

# Standard tuning, low E string first (matches tuning.STANDARD_TUNING_NAMES).
_STANDARD_LINE_MIDI_LOW_FIRST = (40, 45, 50, 55, 59, 64)
_STEP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _pitch_elements(parent: ET.Element, pitch: int) -> None:
    name = _STEP_NAMES[pitch % 12]
    step, _, _sharp = name.partition("#")
    pitch_el = ET.SubElement(parent, "pitch")
    ET.SubElement(pitch_el, "step").text = step
    if _sharp:
        ET.SubElement(pitch_el, "alter").text = "1"
    ET.SubElement(pitch_el, "octave").text = str(pitch // 12 - 1)


def _duration_ticks(note: TabNote, sec_per_quarter: float) -> int:
    seconds = max(0.01, float(note.end) - float(note.start))
    return max(1, int(round(seconds / sec_per_quarter * DIVISIONS)))


def _type_name(ticks: int) -> str:
    table = (
        (DIVISIONS * 4, "whole"),
        (DIVISIONS * 2, "half"),
        (DIVISIONS, "quarter"),
        (DIVISIONS // 2, "eighth"),
        (DIVISIONS // 4, "16th"),
        (DIVISIONS // 8, "32nd"),
    )
    for threshold, name in table:
        if ticks >= threshold:
            return name
    return "32nd"


def _line_midi(tuning_names: tuple[str, ...]) -> list[int]:
    """MIDI per TAB line (line 1 = high e … line 6 = low E)."""
    lines: list[int] = []
    for i, std_midi in enumerate(reversed(_STANDARD_LINE_MIDI_LOW_FIRST)):
        name = tuning_names[5 - i] if len(tuning_names) == 6 else _STEP_NAMES[std_midi % 12]
        candidates = [
            midi
            for midi in range(std_midi - 3, std_midi + 4)
            if _STEP_NAMES[midi % 12] == name
        ]
        lines.append(min(candidates, key=lambda m: abs(m - std_midi)) if candidates else std_midi)
    return lines


def _write_part(part_el: ET.Element, doc: TabDocument) -> None:
    sec_per_quarter = 60.0 / max(1.0, float(doc.tempo_bpm))
    measure_sec = sec_per_quarter * max(1, int(doc.beats_per_measure))

    events = sorted(doc.events, key=lambda ev: ev.start)
    measure_count = max(1, int(max((ev.start for ev in events), default=0.0) / measure_sec) + 1)
    lines = _line_midi(tuple(doc.tuning_names))

    for measure_index in range(measure_count):
        measure = ET.SubElement(part_el, "measure", number=str(measure_index + 1))
        attributes = ET.SubElement(measure, "attributes")
        ET.SubElement(attributes, "divisions").text = str(DIVISIONS)
        if measure_index == 0:
            ET.SubElement(attributes, "time")
            time_el = attributes.find("time")
            ET.SubElement(time_el, "beats").text = str(int(doc.beats_per_measure))
            ET.SubElement(time_el, "beat-type").text = "4"
            clef = ET.SubElement(attributes, "clef")
            ET.SubElement(clef, "sign").text = "TAB"
            ET.SubElement(clef, "line").text = "5"
            details = ET.SubElement(attributes, "staff-details")
            ET.SubElement(details, "staff-lines").text = "6"
            for line_no, midi in enumerate(lines, start=1):
                tuning = ET.SubElement(details, "staff-tuning", line=str(line_no))
                name = _STEP_NAMES[midi % 12]
                step, _, _sharp = name.partition("#")
                ET.SubElement(tuning, "tuning-step").text = step
                if _sharp:
                    ET.SubElement(tuning, "tuning-alter").text = "1"
                ET.SubElement(tuning, "tuning-octave").text = str(midi // 12 - 1)

        for event in events:
            if int(event.start / measure_sec) != measure_index:
                continue
            for note in sorted(event.notes, key=lambda n: (n.string, n.fret)):
                note_el = ET.SubElement(measure, "note")
                _pitch_elements(note_el, int(note.pitch))
                ticks = _duration_ticks(note, sec_per_quarter)
                ET.SubElement(note_el, "duration").text = str(ticks)
                ET.SubElement(note_el, "type").text = _type_name(ticks)
                notations = ET.SubElement(note_el, "notations")
                technical = ET.SubElement(notations, "technical")
                ET.SubElement(technical, "string").text = str(6 - int(note.string))
                ET.SubElement(technical, "fret").text = str(int(note.fret))


def write_musicxml(
    parts: list[tuple[str, TabDocument]],
    output_path: str | Path,
    *,
    title: str,
    tempo_bpm: float,
) -> Path:
    """Write ``parts`` (display name, tab document) to a MusicXML 4.0 file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("score-partwise", version="4.0")
    work = ET.SubElement(root, "work")
    ET.SubElement(work, "work-title").text = title or "Untitled"
    ET.SubElement(root, "identification")

    part_list = ET.SubElement(root, "part-list")
    for index, (name, _doc) in enumerate(parts):
        score_part = ET.SubElement(part_list, "score-part", id=f"P{index + 1}")
        ET.SubElement(score_part, "part-name").text = str(name) or f"Part {index + 1}"

    for index, (_name, doc) in enumerate(parts):
        part_el = ET.SubElement(root, "part", id=f"P{index + 1}")
        _write_part(part_el, doc)
        first_measure = part_el.find("measure")
        if first_measure is not None:
            direction = ET.Element("direction", placement="above")
            direction_type = ET.SubElement(direction, "direction-type")
            metronome = ET.SubElement(direction_type, "metronome")
            ET.SubElement(metronome, "beat-unit").text = "quarter"
            ET.SubElement(metronome, "per-minute").text = str(int(round(tempo_bpm)))
            ET.SubElement(direction, "sound", tempo=str(int(round(tempo_bpm))))
            first_measure.insert(0, direction)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
    return output_path
