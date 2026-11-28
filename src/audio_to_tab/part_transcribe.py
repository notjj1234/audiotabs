"""Transcribe one non-guitar part (bass, vocals, keys, drums, other) from its stem.

Each part writes ``<part>.mid`` and ``<part>.json``. The JSON is what the score
payload reads::

    tab:   {"kind": "tab", "instrument": "bass", "tuning_midi": [...], "tuning_names": [...], "notes": [...]}
    staff: {"kind": "staff", "clef": "treble" | "grand", "notes": [...]}
    drums: {"kind": "drums", "hits": [{"start", "piece", "velocity"}]}

A part with no notes still writes both files and reports ``empty_reason``;
it never fails the job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pretty_midi

from audio_to_tab.midi_cleanup import CleanupConfig
from audio_to_tab.transcribe import transcribe_audio

EMPTY_PART_REASON = "No notes found in this part."
BASS_TUNING_MIDI = (28, 33, 38, 43)
BASS_TUNING_NAMES = ("E", "A", "D", "G")


@dataclass(frozen=True)
class _PitchedSpec:
    kind: str
    clef: str | None
    pitch_min: int
    pitch_max: int
    max_notes_per_onset: int
    min_len_ms: float


_PITCHED: dict[str, _PitchedSpec] = {
    "bass": _PitchedSpec("tab", None, 28, 67, 2, 80.0),
    "keys": _PitchedSpec("staff", "grand", 21, 108, 8, 58.0),
    "other": _PitchedSpec("staff", "treble", 21, 108, 6, 58.0),
}


@dataclass
class PartResult:
    part_id: str
    kind: str
    midi: Path
    result: Path
    note_count: int
    empty_reason: str | None


def _note_dicts(notes: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "pitch": int(n.pitch),
            "start": round(float(n.start), 4),
            "end": round(float(n.end), 4),
            "velocity": int(n.velocity),
        }
        for n in sorted(notes, key=lambda n: (n.start, n.pitch))
    ]


def _write_midi(path: Path, notes: list[Any], *, program: int = 0, is_drum: bool = False) -> None:
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum)
    for n in notes:
        inst.notes.append(pretty_midi.Note(int(n.velocity), int(n.pitch), float(n.start), float(n.end)))
    pm.instruments.append(inst)
    pm.write(str(path))


def _pitched(part_id: str, stem: Path, out_dir: Path, cfg: Any) -> tuple[str, dict, int]:
    spec = _PITCHED[part_id]
    midi_path = out_dir / f"{part_id}.mid"
    transcribe_audio(
        stem,
        midi_path,
        onset_threshold=float(getattr(cfg, "onset_threshold", 0.5)),
        frame_threshold=float(getattr(cfg, "frame_threshold", 0.3)),
        minimum_note_length_ms=spec.min_len_ms,
        cleanup=CleanupConfig(
            pitch_min=spec.pitch_min,
            pitch_max=spec.pitch_max,
            max_notes_per_onset=spec.max_notes_per_onset,
            quantize_sec=None,
        ),
        normalize=False,
        allow_yourmt3=False,  # measured on guitar only (docs/guitar-separation-eval.md)
    )
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    notes = [n for inst in pm.instruments for n in inst.notes]
    payload: dict[str, Any] = {"kind": spec.kind, "notes": _note_dicts(notes)}
    if part_id == "bass":
        payload.update(
            instrument="bass",
            tuning_midi=list(BASS_TUNING_MIDI),
            tuning_names=list(BASS_TUNING_NAMES),
        )
    else:
        payload["clef"] = spec.clef
    return spec.kind, payload, len(notes)


def _vocals(stem: Path, out_dir: Path) -> tuple[str, dict, int]:
    from audio_to_tab.vocal_notes import pyin_notes

    notes = pyin_notes(stem)
    _write_midi(out_dir / "vocals.mid", notes, program=53)
    return "staff", {"kind": "staff", "clef": "treble", "notes": _note_dicts(notes)}, len(notes)


def _drums(stem: Path, out_dir: Path) -> tuple[str, dict, int]:
    from audio_to_tab.drum_transcribe import GM_NOTES, transcribe_drums

    hits = transcribe_drums(stem)
    midi_notes = [
        pretty_midi.Note(h.velocity, GM_NOTES[h.piece], h.start, h.start + 0.1) for h in hits
    ]
    _write_midi(out_dir / "drums.mid", midi_notes, is_drum=True)
    payload = {
        "kind": "drums",
        "hits": [{"start": h.start, "piece": h.piece, "velocity": h.velocity} for h in hits],
    }
    return "drums", payload, len(hits)


def transcribe_part(part_id: str, stem: Path, out_dir: Path, *, cfg: Any) -> PartResult:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if part_id == "vocals":
        kind, payload, count = _vocals(Path(stem), out)
    elif part_id == "drums":
        kind, payload, count = _drums(Path(stem), out)
    elif part_id in _PITCHED:
        kind, payload, count = _pitched(part_id, Path(stem), out, cfg)
    else:
        raise ValueError(f"Unknown part: {part_id}")
    empty = None if count else EMPTY_PART_REASON
    payload["empty_reason"] = empty
    result = out / f"{part_id}.json"
    result.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return PartResult(
        part_id=part_id,
        kind=kind,
        midi=out / f"{part_id}.mid",
        result=result,
        note_count=count,
        empty_reason=empty,
    )
