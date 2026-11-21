"""Local sample-tab pack for destination proof without a full conversion."""

from __future__ import annotations

import json
from pathlib import Path

DEMO_TITLE = "Sample tab"
DEMO_RUN_NAME = "demo-sample-tab"
_META = "meta.json"


def _write_demo_midi(path: Path) -> None:
    import pretty_midi

    music = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    guitar = pretty_midi.Instrument(program=24, name="Guitar")
    # Short C–E–G arpeggio (MIDI 60/64/67).
    for index, pitch in enumerate((60, 64, 67, 60)):
        start = index * 0.5
        guitar.notes.append(
            pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=start + 0.45)
        )
    music.instruments.append(guitar)
    path.parent.mkdir(parents=True, exist_ok=True)
    music.write(str(path))


def _demo_ready(run_dir: Path) -> bool:
    required = (
        run_dir / _META,
        run_dir / "transcription.mid",
        run_dir / "result.json",
        run_dir / "transcription.tab",
        run_dir / "transcription.pdf",
    )
    return all(path.is_file() and path.stat().st_size > 0 for path in required)


def ensure_demo_run(data_dir: Path) -> dict:
    """Materialize a tiny sample conversion under ``data_dir``; idempotent."""
    from audio_to_tab.tab_bundle import (
        bundle_chords,
        key_for_midi,
        tab_document_for,
        write_tab_exports,
    )

    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / DEMO_RUN_NAME
    if _demo_ready(run_dir):
        meta = json.loads((run_dir / _META).read_text(encoding="utf-8"))
        meta["run_dir"] = str(run_dir)
        artifacts = {
            key: str((run_dir / Path(str(value)).name).resolve())
            if Path(str(value)).name
            else str(value)
            for key, value in dict(meta.get("artifacts") or {}).items()
        }
        # Prefer canonical names in this folder.
        artifacts.update(
            {
                "midi": str((run_dir / "transcription.mid").resolve()),
                "result": str((run_dir / "result.json").resolve()),
                "tab": str((run_dir / "transcription.tab").resolve()),
                "pdf": str((run_dir / "transcription.pdf").resolve()),
            }
        )
        meta["artifacts"] = artifacts
        return meta

    run_dir.mkdir(parents=True, exist_ok=True)
    midi_path = run_dir / "transcription.mid"
    _write_demo_midi(midi_path)
    document = tab_document_for(
        midi_path,
        tempo_bpm=120.0,
        tempo_confidence="high",
        beats_per_measure=4,
        tuning_name="Standard (EADGBE)",
        capo=0,
        transpose=0,
    )
    chords = bundle_chords(
        midi_path,
        transpose=0,
        capo=0,
        tuning_name="Standard (EADGBE)",
    )
    song_key = key_for_midi(midi_path, transpose=0, capo=0)
    written = write_tab_exports(
        document,
        run_dir,
        title=DEMO_TITLE,
        capo=0,
        transpose=0,
        bars_per_line=4,
        chords=chords,
        key=song_key,
        duration_sec=2.0,
        tempo_bpm=120.0,
        tempo_confidence="high",
        tuning_name="Standard (EADGBE)",
        lyrics=[],
        lyrics_status="Lyrics were not produced for the sample tab.",
        beats_per_measure=4,
    )
    artifacts = {
        "midi": midi_path.resolve(),
        "result": written["result"].resolve(),
        "tab": written["tab"].resolve(),
        "pdf": written["pdf"].resolve(),
    }
    meta = {
        "page": "tab_pdf",
        "title": DEMO_TITLE,
        "created_at": 0,
        "artifacts": {key: str(path) for key, path in artifacts.items()},
        "run_dir": str(run_dir),
    }
    (run_dir / _META).write_text(json.dumps(meta), encoding="utf-8")
    return meta
