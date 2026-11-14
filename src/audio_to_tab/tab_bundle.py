"""Write the tab, PDF, and result sheet from an existing MIDI file."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from audio_to_tab.chords import (
    ChordHit,
    chords_from_midi,
    detect_key,
    pitches_in_midi,
    shifted_midi,
    sounding_semitones,
)
from audio_to_tab.gp5_export import write_guitar_pro
from audio_to_tab.ingest import is_youtube_url
from audio_to_tab.lyrics import LyricLine
from audio_to_tab.pdf_render import render_structured_tab_pdf
from audio_to_tab.rhythm import quantize_tab_document
from audio_to_tab.tab_generate import TabDocument, midi_to_tab, tab_to_ascii
from audio_to_tab.tuning import tuning_preset

DOWNLOAD_SPECS = (
    ("pdf", "PDF", "application/pdf"),
    ("midi", "MIDI", "audio/midi"),
    ("tab", "ASCII tab", "text/plain"),
    ("gp5", "Guitar Pro 5", "application/x-guitar-pro"),
    ("guitar_stem", "Guitar stem", "audio/wav"),
)


def format_size_kb(num_bytes: int) -> str:
    return f"{max(0, int(num_bytes)) / 1024:.1f} KB"


def show_convert_action(*, has_file: bool, youtube_url: str) -> bool:
    if has_file:
        return True
    text = (youtube_url or "").strip()
    if not text:
        return False
    if is_youtube_url(text):
        return True
    from audio_to_tab.ingest import is_direct_media_url

    return is_direct_media_url(text)


def download_menu(artifacts: dict | None) -> list[dict]:
    if not artifacts:
        return []
    items: list[dict] = []
    for key, label, mime in DOWNLOAD_SPECS:
        raw = artifacts.get(key)
        if not raw:
            continue
        path = Path(str(raw))
        if path.is_file():
            items.append({"key": key, "label": label, "path": path, "mime": mime})
    return items


def downloads_after_run(artifacts: dict | None, *, failed: bool) -> list[dict]:
    if failed:
        return []
    return download_menu(artifacts)


def audio_duration_seconds(path: Path) -> float:
    try:
        import soundfile as sf

        return float(sf.info(str(path)).duration)
    except Exception:
        return 0.0


def tab_document_for(
    midi_path: Path,
    *,
    tempo_bpm: float,
    tempo_confidence: str,
    beats_per_measure: int,
    tuning_name: str,
    capo: int,
    transpose: int,
    beats: tuple[float, ...] = (),
    fingering_preference: str = "playable",
) -> TabDocument:
    semitones = sounding_semitones(transpose=transpose, capo=capo)
    opens, names = tuning_preset(tuning_name)
    capo_opens = tuple(min(127, note + int(capo)) for note in opens)
    music = shifted_midi(midi_path, semitones)
    fd, name = tempfile.mkstemp(suffix=".mid")
    os.close(fd)
    temporary = Path(name)
    try:
        music.write(str(temporary))
        document = midi_to_tab(
            str(temporary),
            tuning=capo_opens,
            tuning_names=names,
            tempo_bpm=tempo_bpm,
            tempo_confidence=tempo_confidence,
            beats_per_measure=beats_per_measure,
            fingering_preference=fingering_preference,
        )
    finally:
        temporary.unlink(missing_ok=True)
    return quantize_tab_document(document, beats_per_measure=beats_per_measure, beats=beats)


def ascii_export(doc: TabDocument, *, capo: int, transpose: int) -> str:
    """Unwrapped tab text. Capo and transpose are header lines, not a reflow."""
    lines: list[str] = []
    if capo:
        lines.append(f"Capo: {capo}")
    if transpose:
        lines.append(f"Transpose: {transpose:+d}")
    body = tab_to_ascii(doc)
    if lines:
        return "\n".join(lines) + "\n" + body
    return body


def _chord_payload(hits: list[ChordHit]) -> list[dict]:
    return [
        {
            "start": hit.start,
            "end": hit.end,
            "name": hit.name,
            "frets": [None if fret is None else int(fret) for fret in hit.frets],
        }
        for hit in hits
    ]


def _lyric_payload(lines: list[LyricLine]) -> list[dict]:
    return [{"start": line.start, "end": line.end, "text": line.text} for line in lines]


def write_tab_exports(
    doc: TabDocument,
    output_dir: Path,
    *,
    title: str,
    capo: int,
    transpose: int,
    bars_per_line: int,
    chords: list[ChordHit],
    key: str,
    duration_sec: float,
    tempo_bpm: float,
    tempo_confidence: str,
    tuning_name: str,
    lyrics: list[LyricLine],
    lyrics_status: str,
    beats_per_measure: int,
    downbeats: tuple[float, ...] = (),
    anacrusis_sec: float = 0.0,
    beats: tuple[float, ...] = (),
    fingering_preference: str = "playable",
    export_gp5: bool = False,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tab_path = output_dir / "transcription.tab"
    tab_path.write_text(ascii_export(doc, capo=capo, transpose=transpose), encoding="utf-8")
    pdf_path = output_dir / "transcription.pdf"
    render_structured_tab_pdf(
        doc,
        str(pdf_path),
        title=title,
        measures_per_row=bars_per_line,
        capo=capo,
        transpose=transpose,
    )
    result_path = output_dir / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "title": title,
                "key": key,
                "tempo_bpm": tempo_bpm,
                "tempo_confidence": tempo_confidence,
                "duration_sec": duration_sec,
                "tuning_name": tuning_name,
                "capo": capo,
                "transpose": transpose,
                "bars_per_line": bars_per_line,
                "beats_per_measure": beats_per_measure,
                "beats": list(beats),
                "downbeats": list(downbeats),
                "anacrusis_sec": anacrusis_sec,
                "fingering_preference": fingering_preference,
                "chords": _chord_payload(chords),
                "lyrics": _lyric_payload(lyrics),
                "lyrics_status": lyrics_status,
            }
        ),
        encoding="utf-8",
    )
    written = {"tab": tab_path, "pdf": pdf_path, "result": result_path}
    if export_gp5:
        written["gp5"] = write_guitar_pro(
            doc,
            output_dir / "transcription.gp5",
            title=title,
        )
    return written


def key_for_midi(midi_path: Path, *, transpose: int, capo: int) -> str:
    return detect_key(pitches_in_midi(midi_path, semitones=sounding_semitones(transpose=transpose, capo=capo)))


def bundle_chords(midi_path: Path, *, transpose: int, capo: int, tuning_name: str) -> list[ChordHit]:
    return chords_from_midi(midi_path, transpose=transpose, capo=capo, tuning_name=tuning_name)
