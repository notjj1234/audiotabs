#!/usr/bin/env python3
"""Evaluate audio->tab pipeline output against an optional reference MIDI.

Usage:
    python scripts/eval_tabs.py --audio clip.wav [--reference-midi ref.mid] \
        [--output-dir /tmp/eval_run] [--no-separate] [--tag baseline]

Metrics (JSON on stdout):
    note_f1 / note_precision / note_recall — pitch (MIDI number) + onset (+-50 ms) maximum match
    tempo_rel_error                          — vs reference MIDI tempo if derivable
    playability                              — fret jumps > 4, chord spans > 5 frets
    note_density_ratio                       — notes/sec vs reference (over/under-pruning signal)

Reference MIDI is optional; without it, only playability and density are reported.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import tempfile
from pathlib import Path

ONSET_TOLERANCE_SEC = 0.05
MAX_FRET_JUMP = 4
MAX_CHORD_SPAN = 5


def _notes_from_midi(path: Path) -> list[dict]:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(path))
    notes = []
    for inst in pm.instruments:
        for n in inst.notes:
            notes.append({"pitch": n.pitch, "start": n.start, "end": n.end})
    return notes


def _notes_from_tab_document(doc) -> list[dict]:
    notes = []
    for event in doc.events:
        for n in event.notes:
            notes.append({"pitch": n.pitch, "start": n.start, "end": n.end, "fret": n.fret})
    return notes


def note_match_f1(hyp: list[dict], ref: list[dict]) -> dict:
    """Maximum-cardinality pitch+onset matching (no mir_eval dependency)."""
    tp = 0
    pitches = {note["pitch"] for note in hyp} | {note["pitch"] for note in ref}
    for pitch in pitches:
        hyp_notes = sorted(
            (note for note in hyp if note["pitch"] == pitch),
            key=lambda note: note["start"],
        )
        ref_notes = sorted(
            (note for note in ref if note["pitch"] == pitch),
            key=lambda note: note["start"],
        )
        hyp_index = ref_index = 0
        while hyp_index < len(hyp_notes) and ref_index < len(ref_notes):
            hyp_start = hyp_notes[hyp_index]["start"]
            ref_start = ref_notes[ref_index]["start"]
            if abs(hyp_start - ref_start) <= ONSET_TOLERANCE_SEC:
                tp += 1
                hyp_index += 1
                ref_index += 1
            elif hyp_start < ref_start:
                hyp_index += 1
            else:
                ref_index += 1
    n_hyp, n_ref = len(hyp), len(ref)
    precision = tp / n_hyp if n_hyp else 0.0
    recall = tp / n_ref if n_ref else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "note_f1": round(f1, 4),
        "note_precision": round(precision, 4),
        "note_recall": round(recall, 4),
        "matched": tp,
        "hyp_notes": n_hyp,
        "ref_notes": n_ref,
    }


def tempo_rel_error(bpm: float, reference_midi: Path, ref_notes: list[dict]) -> float | None:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(reference_midi))
    _, tempi = pm.get_tempo_changes()
    if len(tempi):
        ref_bpm = float(tempi[0])
    else:
        if len(ref_notes) < 4:
            return None
        starts = sorted({round(n["start"], 3) for n in ref_notes})
        intervals = [b - a for a, b in itertools.pairwise(starts) if b - a >= 0.1]
        if not intervals:
            return None
        import statistics

        beat_iv = statistics.median(intervals)
        if beat_iv < 0.25:
            beat_iv *= 2
        elif beat_iv > 1.0:
            beat_iv /= 2
        ref_bpm = 60.0 / beat_iv if beat_iv > 0 else None
    if not ref_bpm:
        return None
    return round(abs(bpm - ref_bpm) / ref_bpm, 4)


def playability(hyp: list[dict], tab_doc) -> dict:
    jump_violations = 0
    transitions = 0
    prev_fret: float | None = None
    for event in sorted(tab_doc.events, key=lambda e: e.start):
        frets = [n.fret for n in event.notes]
        if not frets:
            continue
        mean_fret = sum(frets) / len(frets)
        if prev_fret is not None:
            transitions += 1
            if abs(mean_fret - prev_fret) > MAX_FRET_JUMP:
                jump_violations += 1
        prev_fret = mean_fret
    span_violations = sum(
        1
        for e in tab_doc.events
        if len(e.notes) > 1 and max(n.fret for n in e.notes) - min(n.fret for n in e.notes) > MAX_CHORD_SPAN
    )
    chords = sum(1 for e in tab_doc.events if len(e.notes) > 1)
    return {
        "fret_jump_gt4_pct": round(100 * jump_violations / transitions, 2) if transitions else 0.0,
        "chord_span_gt5_pct": round(100 * span_violations / chords, 2) if chords else 0.0,
    }


def evaluate(
    audio: Path,
    reference_midi: Path | None,
    output_dir: Path,
    separate: bool,
    tag: str,
    fingering_preference: str = "playable",
    max_duration_sec: float | None = None,
    model: str = "auto",
    export_gp5: bool = False,
) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from audio_to_tab.pipeline import PipelineConfig, run_pipeline
    from audio_to_tab.tab_bundle import audio_duration_seconds, tab_document_for

    cfg = PipelineConfig(
        separate_stems=separate,
        fingering_preference=fingering_preference,
        max_duration_sec=max_duration_sec,
        model=model,
        export_gp5=export_gp5,
    )
    artifacts = run_pipeline(
        audio_path=audio,
        output_dir=output_dir,
        config=cfg,
        include_tab_source=True,
    )

    midi_notes = _notes_from_midi(artifacts["midi"])
    tab_midi_path = artifacts.get("tab_midi", artifacts["midi"])
    duration = audio_duration_seconds(artifacts["playback"])
    result_data = json.loads(artifacts["result"].read_text(encoding="utf-8"))
    doc = tab_document_for(
        tab_midi_path,
        tempo_bpm=float(result_data.get("tempo_bpm", 120.0)),
        tempo_confidence=str(result_data.get("tempo_confidence", "low")),
        beats_per_measure=int(result_data.get("beats_per_measure", 4)),
        beats=tuple(result_data.get("beats", ())),
        tuning_name=cfg.tuning_name,
        capo=cfg.capo,
        transpose=cfg.transpose,
        fingering_preference=str(
            result_data.get("fingering_preference", cfg.fingering_preference)
        ),
    )
    tab_notes = _notes_from_tab_document(doc)

    result: dict = {"tag": tag, "audio": str(audio), "duration_sec": round(duration, 3),
                    "hyp_notes": len(midi_notes), "notes_per_sec": round(len(midi_notes) / duration, 3) if duration else 0.0}
    result.update(playability(tab_notes, doc))

    if reference_midi:
        ref_notes = _notes_from_midi(reference_midi)
        result.update(note_match_f1(midi_notes, ref_notes))
        ref_duration = max((n["end"] for n in ref_notes), default=0.0)
        if ref_duration > 0:
            result["note_density_ratio"] = round((len(midi_notes) / duration) / (len(ref_notes) / ref_duration), 4)
        t_err = tempo_rel_error(doc.tempo_bpm, reference_midi, ref_notes)
        if t_err is not None:
            result["tempo_rel_error"] = t_err
        result["ref_notes"] = len(ref_notes)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--reference-midi", type=Path, default=None)
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--no-separate", action="store_true", help="skip stem separation")
    ap.add_argument("--tag", default="run")
    ap.add_argument(
        "--fingering-preference",
        choices=("playable", "low_fret", "position"),
        default="playable",
    )
    ap.add_argument("--max-duration-sec", type=float, default=None)
    ap.add_argument("--model", default="auto")
    ap.add_argument("--gp5", action="store_true", help="also write Guitar Pro 5 export")
    args = ap.parse_args()

    out = args.output_dir or Path(tempfile.mkdtemp(prefix="eval_tabs_"))
    result = evaluate(
        args.audio,
        args.reference_midi,
        out,
        separate=not args.no_separate,
        tag=args.tag,
        fingering_preference=args.fingering_preference,
        max_duration_sec=args.max_duration_sec,
        model=args.model,
        export_gp5=args.gp5,
    )
    result["output_dir"] = str(out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
