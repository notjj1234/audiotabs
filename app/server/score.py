"""Build on-screen score payloads from a completed run."""

from __future__ import annotations

import json
from pathlib import Path

from audio_to_tab.notation_view import (
    chord_diagram_svg,
    chord_lyric_blocks,
    piano_roll_svg,
    screen_tab_text,
    tab_playhead_layout,
    tab_staff_svg,
)
from audio_to_tab.tab_bundle import bundle_chords, key_for_midi, tab_document_for, write_tab_exports
from audio_to_tab.lyrics import LyricLine
from audio_to_tab.tuning import TUNING_PRESETS

from .store import RunRecord


def _load_result(record: RunRecord) -> dict:
    path = record.artifacts.get("result")
    if path is None or not Path(path).is_file():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


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


def build_score(
    record: RunRecord,
    *,
    view: str = "staff",
    tuning: str | None = None,
    capo: int | None = None,
    transpose: int | None = None,
    bars: int | None = None,
) -> dict:
    stored = _load_result(record)
    tuning_name = tuning or str(stored.get("tuning_name") or "Standard (EADGBE)")
    if tuning_name not in TUNING_PRESETS:
        tuning_name = "Standard (EADGBE)"
    capo_i = int(stored.get("capo") or 0) if capo is None else int(capo)
    transpose_i = int(stored.get("transpose") or 0) if transpose is None else int(transpose)
    bars_i = int(stored.get("bars_per_line") or 4) if bars is None else int(bars)

    midi_path = record.artifacts.get("midi")
    tempo = float(stored.get("tempo_bpm") or 120.0)
    confidence = str(stored.get("tempo_confidence") or "high")
    duration = float(stored.get("duration_sec") or 0.0)
    beats = int(stored.get("beats_per_measure") or 4)
    title = record.title or str(stored.get("title") or "Guitar Tab")
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

    return {
        "view": view,
        "svg": svg,
        "text": text,
        "meta": meta,
        "layout": layout,
        "chords": chords_payload,
        "artifacts": {
            name: path.is_file() for name, path in sorted(record.artifacts.items())
        },
    }


def export_run(
    record: RunRecord,
    *,
    fmt: str,
    tuning: str,
    capo: int,
    transpose: int,
    bars: int,
    exports_root: Path,
) -> Path:
    stored = _load_result(record)
    midi_path = record.artifacts.get("midi")
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
