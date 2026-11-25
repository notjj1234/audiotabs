"""Build on-screen score payloads from a completed run."""

from __future__ import annotations

import json
import math
from itertools import pairwise
from pathlib import Path

from audio_to_tab.lyrics import LyricLine
from audio_to_tab.notation_view import (
    chord_diagram_svg,
    chord_lyric_blocks,
    piano_roll_svg,
    screen_tab_text,
    tab_playhead_layout,
    tab_staff_svg,
)
from audio_to_tab.tab_bundle import bundle_chords, key_for_midi, tab_document_for, write_tab_exports
from audio_to_tab.tuning import TUNING_PRESETS

from .parts import GUITAR_PARTS, REGISTRY, part_label, run_parts
from .parts import available_parts as _available_parts
from .store import RunRecord


def _load_result_at(path: Path | None) -> dict:
    if path is None or not Path(path).is_file():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_result(record: RunRecord) -> dict:
    return _load_result_at(record.artifacts.get("result"))


def available_parts(record: RunRecord) -> list[str]:
    """Ordered part ids for this run (picker runs: details.parts; legacy: lead/rhythm/combined)."""
    return _available_parts(record)


def resolve_part_paths(record: RunRecord, part: str | None) -> tuple[Path | None, Path | None]:
    """Return (midi_path, result_path) for the requested part.

    Unknown or missing parts fall back to combined.
    """
    requested = (part or "combined").strip().lower()
    if requested == "lead":
        midi = record.artifacts.get("lead_midi")
        result = record.artifacts.get("lead_result")
        if midi is not None and Path(midi).is_file() and result is not None and Path(result).is_file():
            return Path(midi), Path(result)
    elif requested == "rhythm":
        midi = record.artifacts.get("rhythm_midi")
        result = record.artifacts.get("rhythm_result")
        if midi is not None and Path(midi).is_file() and result is not None and Path(result).is_file():
            return Path(midi), Path(result)
    midi = record.artifacts.get("midi")
    result = record.artifacts.get("result")
    return (
        Path(midi) if midi is not None else None,
        Path(result) if result is not None else None,
    )


def _lyric_lines(stored: dict) -> list[LyricLine]:
    lines: list[LyricLine] = []
    for item in stored.get("lyrics") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        try:
            lines.append(LyricLine(start=float(item["start"]), end=float(item["end"]), text=text))
        except (KeyError, TypeError, ValueError):
            continue
    return lines


def _roll_notes(midi_path: Path) -> list[tuple[int, float, float]]:
    import pretty_midi

    music = pretty_midi.PrettyMIDI(str(midi_path))
    notes: list[tuple[int, float, float]] = []
    for instrument in music.instruments:
        if instrument.is_drum:
            continue
        notes.extend(
            (int(note.pitch), float(note.start), float(note.end)) for note in instrument.notes
        )
    return notes


_TRACK_LABELS = {"lead": "Lead", "rhythm": "Rhythm", "combined": "Guitar"}
_EVENT_TECHNIQUES = ("palm_mute", "harmonic")
_LEGATO_TECHNIQUES = ("hammer_on", "pull_off", "slide")


def _float_list(raw: object) -> list[float]:
    if not isinstance(raw, list):
        return []
    out: list[float] = []
    for value in raw:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number >= 0:
            out.append(number)
    return sorted(set(out))


def regular_grid(times: list[float], end_time: float) -> tuple[list[float], float]:
    """Drop detections that sit too close, fill gaps at the typical spacing, run to the end.

    Beat trackers sometimes double, skip or stop early; the viewer needs one grid
    for the whole song, so the detected times are kept and only the holes are filled.
    """
    gaps = sorted(b - a for a, b in pairwise(times) if b > a)
    if not gaps:
        return list(times), 0.0
    length = gaps[len(gaps) // 2]
    clean = [times[0]]
    for value in times[1:]:
        if value - clean[-1] < 0.6 * length:
            continue
        while value - clean[-1] > 1.6 * length:
            clean.append(clean[-1] + length)
        clean.append(value)
    while clean[-1] + length < end_time:
        clean.append(clean[-1] + length)
    while clean[0] - length > 0.25 * length:
        clean.insert(0, clean[0] - length)
    return [round(v, 4) for v in clean], length


def _bar_starts(
    beats: list[float], downbeats: list[float], beats_per_measure: int, end_time: float
) -> tuple[list[float], float]:
    """Bar starts every ``beats_per_measure`` detected beats, phased to agree with the downbeats."""
    grid, beat_len = regular_grid(beats, end_time)
    per = max(1, beats_per_measure)
    if len(grid) < per + 1 or beat_len <= 0:
        return [], 0.0
    tolerance = 0.25 * beat_len

    def hits(phase: int) -> int:
        return sum(
            1 for t in grid[phase::per] if any(abs(t - db) <= tolerance for db in downbeats)
        )

    phase = max(range(per), key=hits) if downbeats else 0
    starts = grid[phase::per]
    return starts, beat_len * per


def tab_measures(
    *,
    beats: list[float],
    downbeats: list[float],
    tempo_bpm: float,
    beats_per_measure: int,
    end_time: float,
) -> list[dict]:
    """Measure spans in seconds from the detected beat grid, else downbeats, else a fixed tempo."""
    tempo = tempo_bpm if tempo_bpm and tempo_bpm > 0 else 120.0
    fixed = 60.0 / tempo * max(1, beats_per_measure)
    end_time = max(end_time, fixed)
    starts: list[float] = []
    grid, length = _bar_starts(beats, downbeats, beats_per_measure, end_time)
    if not grid and len(downbeats) >= 2:
        grid, length = regular_grid(downbeats, end_time)
    if grid and length > 0:
        starts = [db for db in grid if db < end_time] or [grid[0]]
        # A short lead-in folds into the first bar; a longer one becomes a pickup bar.
        if starts[0] > 0.25 * length:
            starts.insert(0, 0.0)
        else:
            starts[0] = 0.0
        ends = [*starts[1:], starts[-1] + length]
    else:
        count = max(1, math.ceil(end_time / fixed - 1e-9))
        starts = [i * fixed for i in range(count)]
        ends = [s + fixed for s in starts]
    return [
        {"index": i, "start": round(s, 4), "end": round(e, 4)}
        for i, (s, e) in enumerate(zip(starts, ends, strict=True))
        if e > s
    ]


def _beat_times(beats: list[float], measures: list[dict], beats_per_measure: int) -> list[float]:
    """Detected beat times (holes filled), or an even split of each measure when none were saved."""
    if len(beats) >= 2 and measures:
        return regular_grid(beats, measures[-1]["end"])[0]
    per = max(1, beats_per_measure)
    out: list[float] = []
    for measure in measures:
        step = (measure["end"] - measure["start"]) / per
        out.extend(round(measure["start"] + k * step, 4) for k in range(per))
    return out


def _load_techniques(record: RunRecord) -> dict[str, list[dict]]:
    path = record.artifacts.get("lead_rhythm_notes")
    payload = _load_result_at(path)
    out: dict[str, list[dict]] = {}
    for role in ("lead", "rhythm"):
        section = payload.get(role)
        marks = section.get("techniques") if isinstance(section, dict) else None
        rows: list[dict] = []
        for mark in marks or []:
            if not isinstance(mark, dict):
                continue
            kind = str(mark.get("kind") or "")
            try:
                start = float(mark["start"])
                end = float(mark["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if kind in _LEGATO_TECHNIQUES or kind in _EVENT_TECHNIQUES:
                rows.append({"kind": kind, "start": start, "end": end})
        out[role] = rows
    return out


def _attach_techniques(events: list[dict], marks: list[dict]) -> None:
    """Hang saved technique marks on tab events by time (marks only; nothing is guessed)."""
    if not events:
        return
    starts = [event["start"] for event in events]
    for mark in marks:
        nearest = min(range(len(starts)), key=lambda i: abs(starts[i] - mark["start"]))
        if abs(starts[nearest] - mark["start"]) > 0.12:
            continue
        target = nearest
        if mark["kind"] in _LEGATO_TECHNIQUES:
            # The mark joins note A to note B; Songsterr-style, the label sits on B.
            target = nearest + 1
            if target >= len(events) or starts[target] > mark["end"] + 0.12:
                continue
        kinds = events[target].setdefault("techniques", [])
        if mark["kind"] not in kinds:
            kinds.append(mark["kind"])


def _track_events(document, measures: list[dict], beats_per_measure: int) -> list[dict]:
    """Tab events with rhythm values and beam groups, measured against each bar's own length."""
    events = sorted(document.events, key=lambda event: event.start)
    out: list[dict] = []
    m_index = 0
    by_measure: dict[int, list[int]] = {}
    for event in events:
        if not event.notes:
            continue
        while m_index + 1 < len(measures) and event.start >= measures[m_index]["end"]:
            m_index += 1
        out.append(
            {
                "start": round(float(event.start), 4),
                "end": round(max(note.end for note in event.notes), 4),
                "measure": m_index,
                "notes": [
                    {
                        "string": int(note.string),
                        "fret": int(note.fret),
                        "pitch": int(note.pitch),
                        "end": round(float(note.end), 4),
                    }
                    for note in sorted(event.notes, key=lambda n: n.string)
                ],
            }
        )
        by_measure.setdefault(m_index, []).append(len(out) - 1)
    _apply_rhythm(out, by_measure, measures, beats_per_measure)
    return out


def _apply_rhythm(
    out: list[dict],
    by_measure: dict[int, list[int]],
    measures: list[dict],
    beats_per_measure: int,
) -> None:
    """Rhythm values and beam groups for events, measured against each bar's own length."""
    from audio_to_tab.tab_generate import TabEvent, TabNote
    from audio_to_tab.tab_rhythm import beam_groups, snap_duration

    beam_id = 0
    for m_index, members in by_measure.items():
        measure = measures[m_index]
        m_len = measure["end"] - measure["start"]
        beat_sec = m_len / max(1, beats_per_measure)
        local_bpm = 60.0 / beat_sec if beat_sec > 0 else 120.0
        local: list[TabEvent] = []
        for i in members:
            row = out[i]
            span = max(0.01, min(row["end"], measure["end"]) - row["start"])
            value = snap_duration(span, tempo_bpm=local_bpm)
            row["rhythm"] = {"type": value.type_name, "flags": value.flags, "dotted": value.dotted}
            rel = row["start"] - measure["start"]
            local.append(
                TabEvent(
                    start=rel,
                    notes=[TabNote(start=rel, end=rel + span, string=0, fret=0, pitch=40)],
                )
            )
        for group in beam_groups(local, tempo_bpm=local_bpm, beats_per_measure=beats_per_measure):
            beam_id += 1
            for local_index in group:
                out[members[local_index]]["beam"] = beam_id


_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_ONSET_WINDOW = 0.03
_BASS_MAX_FRET = 24


def spell_pitch(pitch: int) -> str:
    """Sharps-only spelling, e.g. 66 → F#4."""
    return f"{_NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


def _onset_groups(items: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for item in sorted(items, key=lambda it: (it["start"], it.get("pitch", 0))):
        if groups and item["start"] - groups[-1][0]["start"] <= _ONSET_WINDOW:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def _bass_positions(pitches: list[int], tuning: list[int]) -> list[tuple[int, int, int]]:
    """(string, fret, pitch) per note, lowest fret first, one note per string."""
    used: set[int] = set()
    out: list[tuple[int, int, int]] = []
    for pitch in sorted(pitches):
        options = [
            (pitch - open_pitch, string)
            for string, open_pitch in enumerate(tuning)
            if string not in used and 0 <= pitch - open_pitch <= _BASS_MAX_FRET
        ]
        if not options:
            continue
        fret, string = min(options)
        used.add(string)
        out.append((string, fret, pitch))
    return out


def _part_events(
    payload: dict, kind: str, measures: list[dict], beats_per_measure: int, transpose: int
) -> list[dict]:
    """Events for a non-guitar part (bass tab, staff notation, drum hits) on the shared bars."""
    if kind == "drums":
        items = [
            {"start": float(h["start"]), "end": float(h["start"]) + 0.1, "piece": str(h["piece"])}
            for h in payload.get("hits") or []
            if isinstance(h, dict) and "start" in h and "piece" in h
        ]
    else:
        items = [
            {
                "start": float(n["start"]),
                "end": float(n["end"]),
                "pitch": int(n["pitch"]) + int(transpose),
            }
            for n in payload.get("notes") or []
            if isinstance(n, dict) and {"start", "end", "pitch"} <= set(n)
        ]
    tuning = [int(p) for p in payload.get("tuning_midi") or []]
    out: list[dict] = []
    by_measure: dict[int, list[int]] = {}
    m_index = 0
    for group in _onset_groups(items):
        start = group[0]["start"]
        while m_index + 1 < len(measures) and start >= measures[m_index]["end"]:
            m_index += 1
        if kind == "drums":
            notes = [{"piece": it["piece"], "end": round(it["end"], 4)} for it in group]
        elif kind == "tab":
            ends = {it["pitch"]: it["end"] for it in group}
            notes = [
                {"string": s, "fret": f, "pitch": p, "end": round(ends[p], 4)}
                for s, f, p in _bass_positions([it["pitch"] for it in group], tuning)
            ]
        else:
            notes = [
                {"pitch": it["pitch"], "spelling": spell_pitch(it["pitch"]), "end": round(it["end"], 4)}
                for it in sorted(group, key=lambda it: it["pitch"])
            ]
        if not notes:
            continue
        out.append(
            {
                "start": round(start, 4),
                "end": round(max(it["end"] for it in group), 4),
                "measure": m_index,
                "notes": notes,
            }
        )
        by_measure.setdefault(m_index, []).append(len(out) - 1)
    _apply_rhythm(out, by_measure, measures, beats_per_measure)
    return out


def build_tab_payload(
    record: RunRecord,
    *,
    parts: list[str],
    stored: dict,
    tuning_name: str,
    capo: int,
    transpose: int,
) -> dict | None:
    """Structured tab for the interactive viewer: tracks, bars, beats, rhythm and techniques."""
    generic = run_parts(record)
    if generic is not None:
        track_ids = list(generic)
    elif "lead" in parts and "rhythm" in parts:
        track_ids = ["lead", "rhythm"]
    elif "lead" in parts:
        track_ids = ["lead"]
    else:
        track_ids = ["combined"]

    tempo = float(stored.get("tempo_bpm") or 120.0)
    confidence = str(stored.get("tempo_confidence") or "high")
    beats_per_measure = int(stored.get("beats_per_measure") or 4)
    beats = _float_list(stored.get("beats"))
    downbeats = _float_list(stored.get("downbeats"))
    techniques = _load_techniques(record)

    documents = []
    part_payloads: dict[str, dict] = {}
    for track_id in track_ids:
        if track_id not in GUITAR_PARTS:
            part_payloads[track_id] = _load_result_at(
                record.artifacts.get(REGISTRY[track_id].result_key)
            )
            continue
        midi_path, _ = resolve_part_paths(record, track_id)
        if midi_path is None or not Path(midi_path).is_file():
            continue
        document = tab_document_for(
            Path(midi_path),
            tempo_bpm=tempo,
            tempo_confidence=confidence,
            beats_per_measure=beats_per_measure,
            tuning_name=tuning_name,
            capo=capo,
            transpose=transpose,
            beats=tuple(beats),
        )
        documents.append((track_id, document))
    if not documents and not part_payloads:
        return None

    last_note = max(
        (note.end for _, doc in documents for event in doc.events for note in event.notes),
        default=0.0,
    )
    for payload in part_payloads.values():
        for item in [*(payload.get("notes") or []), *(payload.get("hits") or [])]:
            try:
                last_note = max(last_note, float(item.get("end", item.get("start", 0.0))))
            except (AttributeError, TypeError, ValueError):
                continue
    duration = max(float(stored.get("duration_sec") or 0.0), last_note)
    measures = tab_measures(
        beats=beats,
        downbeats=downbeats,
        tempo_bpm=tempo,
        beats_per_measure=beats_per_measure,
        end_time=duration,
    )
    tracks = []
    by_id = dict(documents)
    empty_parts = (record.details or {}).get("empty_parts") or {}
    default_strings = list(
        TUNING_PRESETS.get(tuning_name, TUNING_PRESETS["Standard (EADGBE)"])[1]
    )
    for track_id in track_ids:
        if generic is not None and track_id in GUITAR_PARTS and track_id not in by_id:
            # Guitar part with nothing to show: say so instead of drawing a blank tab.
            tracks.append(
                {
                    "id": track_id,
                    "label": part_label(track_id),
                    "kind": "tab",
                    "strings": default_strings,
                    "events": [],
                    "empty_reason": str(empty_parts.get(track_id) or "No notes found in this part."),
                }
            )
            continue
        if track_id in by_id:
            document = by_id[track_id]
            events = _track_events(document, measures, beats_per_measure)
            _attach_techniques(events, techniques.get(track_id, []))
            if generic is None:
                tracks.append(
                    {
                        "id": track_id,
                        "label": _TRACK_LABELS.get(track_id, track_id.title()),
                        "events": events,
                    }
                )
            else:
                track = {
                    "id": track_id,
                    "label": part_label(track_id),
                    "kind": "tab",
                    "strings": list(document.tuning_names),
                    "events": events,
                }
                if not events:
                    track["empty_reason"] = str(
                        empty_parts.get(track_id) or "No notes found in this part."
                    )
                tracks.append(track)
        elif track_id in part_payloads:
            payload = part_payloads[track_id]
            kind = REGISTRY[track_id].kind
            track: dict = {
                "id": track_id,
                "label": part_label(track_id),
                "kind": kind,
                "events": _part_events(payload, kind, measures, beats_per_measure, transpose),
            }
            if kind == "tab":
                track["strings"] = [str(n) for n in payload.get("tuning_names") or []]
            if kind == "staff":
                track["clef"] = str(payload.get("clef") or "treble")
            empty = payload.get("empty_reason") or (record.details or {}).get(
                "empty_parts", {}
            ).get(track_id)
            if empty or not track["events"]:
                track["empty_reason"] = str(empty or "No notes found in this part.")
            tracks.append(track)
    if documents:
        tuning_names = list(documents[0][1].tuning_names)
    else:
        tuning_names = list(TUNING_PRESETS.get(tuning_name, TUNING_PRESETS["Standard (EADGBE)"])[1])
    return {
        "ai_generated": True,
        "tempo_bpm": tempo,
        "beats_per_measure": beats_per_measure,
        "duration_sec": duration,
        "tuning": tuning_names,
        "capo": capo,
        "beats": _beat_times(beats, measures, beats_per_measure),
        "measures": measures,
        "tracks": tracks,
        "techniques_available": bool(techniques.get("lead") or techniques.get("rhythm")),
    }


def build_score(
    record: RunRecord,
    *,
    view: str = "staff",
    tuning: str | None = None,
    capo: int | None = None,
    transpose: int | None = None,
    bars: int | None = None,
    part: str | None = None,
) -> dict:
    parts = available_parts(record)
    generic = run_parts(record) is not None
    requested = (part or "").strip().lower()
    if generic:
        resolved_part = requested if requested in parts else parts[0]
    elif not requested:
        # Default open part: lead when present, else combined.
        resolved_part = "lead" if "lead" in parts else "combined"
    elif requested in parts:
        resolved_part = requested
    else:
        resolved_part = "combined"

    midi_path, result_path = resolve_part_paths(record, resolved_part)
    # If resolve fell back, reflect that in the response part id.
    if not generic and resolved_part in ("lead", "rhythm"):
        expected_midi = record.artifacts.get(f"{resolved_part}_midi")
        if midi_path is None or expected_midi is None or Path(midi_path) != Path(expected_midi):
            resolved_part = "combined"

    stored = _load_result_at(result_path)
    if not stored:
        stored = _load_result(record)
    tuning_name = tuning or str(stored.get("tuning_name") or "Standard (EADGBE)")
    if tuning_name not in TUNING_PRESETS:
        tuning_name = "Standard (EADGBE)"
    capo_i = int(stored.get("capo") or 0) if capo is None else int(capo)
    transpose_i = int(stored.get("transpose") or 0) if transpose is None else int(transpose)
    bars_i = int(stored.get("bars_per_line") or 4) if bars is None else int(bars)

    tempo = float(stored.get("tempo_bpm") or 120.0)
    confidence = str(stored.get("tempo_confidence") or "high")
    duration = float(stored.get("duration_sec") or 0.0)
    beats = int(stored.get("beats_per_measure") or 4)
    title = str(stored.get("title") or record.title or "Guitar Tab")
    song_key = str(stored.get("key") or "Unknown")
    lyrics_status = str(stored.get("lyrics_status") or "")
    lyric_lines = _lyric_lines(stored)

    svg = ""
    text = ""
    layout: dict | None = None
    meta = {
        "title": title,
        "key": song_key,
        "tempo_bpm": tempo,
        "tempo_confidence": confidence,
        "duration_sec": duration,
        "beats_per_measure": beats,
        "tuning_name": tuning_name,
        "capo": capo_i,
        "transpose": transpose_i,
        "bars_per_line": bars_i,
        "lyrics_status": lyrics_status,
    }
    chords_payload: list[dict] = []
    tab_payload: dict | None = None

    if midi_path is not None and Path(midi_path).is_file():
        document = tab_document_for(
            Path(midi_path),
            tempo_bpm=tempo,
            tempo_confidence=confidence,
            beats_per_measure=beats,
            tuning_name=tuning_name,
            capo=capo_i,
            transpose=transpose_i,
        )
        chords = bundle_chords(
            Path(midi_path),
            transpose=transpose_i,
            capo=capo_i,
            tuning_name=tuning_name,
        )
        song_key = key_for_midi(Path(midi_path), transpose=transpose_i, capo=capo_i)
        meta["key"] = song_key
        chords_payload = [
            {
                "name": c.name,
                "start": c.start,
                "frets": list(c.frets) if hasattr(c, "frets") else [],
            }
            for c in chords
        ]

        view_key = (view or "staff").lower()
        if view_key == "staff":
            svg = tab_staff_svg(document, bars_per_line=bars_i)
            layout = tab_playhead_layout(document, bars_per_line=bars_i)
            # Bars and beats come from the combined run result (shared by every track).
            tab_payload = build_tab_payload(
                record,
                parts=parts,
                stored=_load_result(record) or stored,
                tuning_name=tuning_name,
                capo=capo_i,
                transpose=transpose_i,
            )
        elif view_key == "piano":
            svg = piano_roll_svg(
                _roll_notes(Path(midi_path)),
                tempo_bpm=tempo,
                beats_per_measure=beats,
                semitones=transpose_i + capo_i,
            )
        elif view_key == "text":
            text = screen_tab_text(document, bars_per_line=bars_i)
        elif view_key == "chords":
            blocks = chord_lyric_blocks(chords, lyric_lines)
            text = "\n".join(
                f"{b.get('chord', '')}  {b.get('lyric', '')}".strip() for b in blocks
            ) or ", ".join(c.name for c in chords)
            if chords:
                first = chords[0]
                frets = list(getattr(first, "frets", []) or [])
                svg = chord_diagram_svg(first.name, frets)
        else:
            svg = tab_staff_svg(document, bars_per_line=bars_i)
    else:
        tab_path = record.artifacts.get("tab")
        if tab_path and Path(tab_path).is_file():
            text = Path(tab_path).read_text(encoding="utf-8", errors="replace")
        if generic and (view or "staff").lower() == "staff":
            # A run with no guitar part (e.g. keys only) still has a viewer payload.
            tab_payload = build_tab_payload(
                record,
                parts=parts,
                stored=_load_result(record) or stored,
                tuning_name=tuning_name,
                capo=capo_i,
                transpose=transpose_i,
            )

    return {
        "view": view,
        "svg": svg,
        "text": text,
        "meta": meta,
        "layout": layout,
        "tab": tab_payload,
        "chords": chords_payload,
        "part": resolved_part,
        "parts": parts,
        "artifacts": {
            name: path.is_file() for name, path in sorted(record.artifacts.items())
        },
    }


class UnsupportedExport(ValueError):
    """The requested format can't be made for this part; the message is user-facing."""


_FORMAT_NAMES = {"pdf": "PDF", "tab": "Text tab", "gp5": "Guitar Pro", "musicxml": "MusicXML"}
_KIND_FORMATS = {
    "tab": {"pdf", "tab", "gp5", "midi", "musicxml"},
    "staff": {"midi", "musicxml"},
    "drums": {"midi", "musicxml"},
}


def _export_all_shown_midi(record: RunRecord, shown: list[str], exports_root: Path) -> Path:
    import pretty_midi

    out = pretty_midi.PrettyMIDI()
    for part in shown:
        spec = REGISTRY.get(part)
        path = record.artifacts.get(spec.midi_key) if spec else None
        if path is None or not Path(path).is_file():
            continue
        source = pretty_midi.PrettyMIDI(str(path))
        merged = pretty_midi.Instrument(
            program=0, is_drum=spec.kind == "drums", name=part_label(part)
        )
        for inst in source.instruments:
            merged.notes.extend(inst.notes)
        merged.notes.sort(key=lambda n: (n.start, n.pitch))
        out.instruments.append(merged)
    if not out.instruments:
        raise FileNotFoundError("No MIDI found for the shown parts.")
    dest = exports_root / record.id
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / "parts.mid"
    out.write(str(target))
    return target


def _musicxml_part(record: RunRecord, part: str, *, tuning: str, capo: int, transpose: int):
    """TabDocument for tab parts, NotationPart for notation/drum parts (None when missing)."""
    from audio_to_tab.musicxml_export import NotationPart
    from audio_to_tab.tuning import BASS_TUNING_NAME

    stored = _load_result(record)
    tempo = float(stored.get("tempo_bpm") or 120.0)
    beats = int(stored.get("beats_per_measure") or 4)
    spec = REGISTRY[part]
    if spec.kind == "tab":
        midi = record.artifacts.get(spec.midi_key)
        if midi is None or not Path(midi).is_file():
            return None
        is_bass = part == "bass"
        return tab_document_for(
            Path(midi),
            tempo_bpm=tempo,
            tempo_confidence=str(stored.get("tempo_confidence") or "high"),
            beats_per_measure=beats,
            tuning_name=BASS_TUNING_NAME if is_bass else tuning,
            capo=0 if is_bass else capo,
            transpose=transpose,
        )
    payload = _load_result_at(record.artifacts.get(spec.result_key))
    if not payload:
        return None
    shift = 0 if spec.kind == "drums" else int(transpose)
    return NotationPart(
        kind=spec.kind,
        clef=payload.get("clef"),
        tempo_bpm=tempo,
        beats_per_measure=beats,
        notes=[{**n, "pitch": int(n["pitch"]) + shift} for n in payload.get("notes") or []],
        hits=list(payload.get("hits") or []),
    )


def _export_musicxml(
    record: RunRecord, parts: list[str], exports_root: Path, *, tuning: str, capo: int, transpose: int
) -> Path:
    from audio_to_tab.musicxml_export import write_musicxml

    built = []
    for part in parts:
        doc = _musicxml_part(record, part, tuning=tuning, capo=capo, transpose=transpose)
        if doc is not None:
            built.append((part_label(part), doc))
    if not built:
        raise FileNotFoundError("Nothing to export for these parts.")
    stored = _load_result(record)
    out_dir = exports_root / record.id
    out_dir.mkdir(parents=True, exist_ok=True)
    name = "parts.musicxml" if len(parts) > 1 else f"{parts[0]}.musicxml"
    return write_musicxml(
        built,
        out_dir / name,
        title=record.title or "Song",
        tempo_bpm=float(stored.get("tempo_bpm") or 120.0),
    )


def _export_bass(
    record: RunRecord, *, fmt: str, transpose: int, bars: int, exports_root: Path
) -> Path:
    """Bass tab exports (PDF, text tab, Guitar Pro, MusicXML) on the 4-string tuning."""
    from audio_to_tab.tuning import BASS_TUNING_NAME

    midi = record.artifacts.get("bass_midi")
    if midi is None or not Path(midi).is_file():
        raise FileNotFoundError("Bass MIDI missing")
    stored = _load_result(record)
    tempo = float(stored.get("tempo_bpm") or 120.0)
    confidence = str(stored.get("tempo_confidence") or "high")
    beats = int(stored.get("beats_per_measure") or 4)
    document = tab_document_for(
        Path(midi),
        tempo_bpm=tempo,
        tempo_confidence=confidence,
        beats_per_measure=beats,
        tuning_name=BASS_TUNING_NAME,
        capo=0,
        transpose=transpose,
    )
    out_dir = exports_root / record.id / "bass"
    out_dir.mkdir(parents=True, exist_ok=True)
    title = f"{record.title or 'Song'} (Bass)"
    written = write_tab_exports(
        document,
        out_dir,
        title=title,
        capo=0,
        transpose=transpose,
        bars_per_line=bars,
        chords=[],
        key=str(stored.get("key") or ""),
        duration_sec=float(stored.get("duration_sec") or 0.0),
        tempo_bpm=tempo,
        tempo_confidence=confidence,
        tuning_name=BASS_TUNING_NAME,
        lyrics=[],
        lyrics_status="",
        beats_per_measure=beats,
        export_gp5=fmt == "gp5",
    )
    path = written.get(fmt)
    if path is None or not Path(path).is_file():
        raise FileNotFoundError(f"{fmt} missing")
    return Path(path)


def export_run(
    record: RunRecord,
    *,
    fmt: str,
    tuning: str,
    capo: int,
    transpose: int,
    bars: int,
    exports_root: Path,
    part: str | None = None,
    all_shown: bool = False,
    shown: list[str] | None = None,
) -> Path:
    if all_shown and fmt in ("midi", "musicxml"):
        parts = available_parts(record)
        chosen = [p for p in (shown or parts) if p in parts]
        if fmt == "midi":
            return _export_all_shown_midi(record, chosen, exports_root)
        return _export_musicxml(record, chosen, exports_root, tuning=tuning, capo=capo, transpose=transpose)
    if part and fmt == "musicxml" and part in available_parts(record):
        # A named part exports alone (legacy calls send no part and keep the combined file).
        return _export_musicxml(record, [part], exports_root, tuning=tuning, capo=capo, transpose=transpose)
    if part and part not in GUITAR_PARTS:
        spec = REGISTRY.get(part)
        if spec is None or part not in available_parts(record):
            raise FileNotFoundError("That part isn't in this run.")
        if fmt not in _KIND_FORMATS.get(spec.kind, set()) and fmt != "guitar_stem":
            noun = "drum parts" if spec.kind == "drums" else "notation parts"
            raise UnsupportedExport(
                f"{_FORMAT_NAMES.get(fmt, fmt)} isn't available for {noun} yet; use MusicXML."
            )
        if fmt == "midi":
            path = record.artifacts.get(spec.midi_key)
            if path is None or not Path(path).is_file():
                raise FileNotFoundError("MIDI missing")
            return Path(path)
        if fmt == "musicxml":
            return _export_musicxml(record, [part], exports_root, tuning=tuning, capo=capo, transpose=transpose)
        if part == "bass":
            return _export_bass(record, fmt=fmt, transpose=transpose, bars=bars, exports_root=exports_root)
        raise UnsupportedExport(
            f"{_FORMAT_NAMES.get(fmt, fmt)} for this part isn't available yet; use MIDI."
        )
    stored = _load_result(record)
    midi_path = record.artifacts.get("midi")
    if part in ("lead", "rhythm"):
        part_midi, part_result = resolve_part_paths(record, part)
        if part_midi is not None and Path(part_midi) != Path(midi_path or ""):
            midi_path = part_midi
            stored = _load_result_at(part_result) or stored
    if fmt == "midi":
        if midi_path is None or not Path(midi_path).is_file():
            raise FileNotFoundError("MIDI missing")
        return Path(midi_path)
    if fmt == "guitar_stem":
        stem = record.artifacts.get("guitar_stem")
        if stem is None or not Path(stem).is_file():
            raise FileNotFoundError("Guitar stem missing")
        return Path(stem)
    if fmt == "musicxml":
        path = record.artifacts.get("musicxml")
        if path is None or not Path(path).is_file():
            raise FileNotFoundError("MusicXML missing")
        return Path(path)

    if midi_path is None or not Path(midi_path).is_file():
        # Fall back to stored artifacts for pdf/tab/gp5
        key = {"pdf": "pdf", "tab": "tab", "gp5": "gp5"}[fmt]
        path = record.artifacts.get(key)
        if path is None or not Path(path).is_file():
            raise FileNotFoundError(f"{fmt} missing")
        return Path(path)

    tempo = float(stored.get("tempo_bpm") or 120.0)
    confidence = str(stored.get("tempo_confidence") or "high")
    beats = int(stored.get("beats_per_measure") or 4)
    document = tab_document_for(
        Path(midi_path),
        tempo_bpm=tempo,
        tempo_confidence=confidence,
        beats_per_measure=beats,
        tuning_name=tuning,
        capo=capo,
        transpose=transpose,
    )
    chords = bundle_chords(Path(midi_path), transpose=transpose, capo=capo, tuning_name=tuning)
    song_key = key_for_midi(Path(midi_path), transpose=transpose, capo=capo)
    out_dir = exports_root / record.id
    out_dir.mkdir(parents=True, exist_ok=True)
    written = write_tab_exports(
        document,
        out_dir,
        title=record.title or "Guitar Tab",
        capo=capo,
        transpose=transpose,
        bars_per_line=bars,
        chords=chords,
        key=song_key,
        duration_sec=float(stored.get("duration_sec") or 0.0),
        tempo_bpm=tempo,
        tempo_confidence=confidence,
        tuning_name=tuning,
        lyrics=_lyric_lines(stored),
        lyrics_status=str(stored.get("lyrics_status") or ""),
        beats_per_measure=beats,
        export_gp5=True,
    )
    key = {"pdf": "pdf", "tab": "tab", "gp5": "gp5"}[fmt]
    path = written.get(key)
    if path is None or not Path(path).is_file():
        raise FileNotFoundError(f"{fmt} missing")
    return Path(path)
