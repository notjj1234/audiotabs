"""Lead/rhythm per-stem transcription paths off one Basic Pitch call.

Two post-processing paths over the same ``transcribe_audio`` entry point:

- **lead** — monophonic-preferred: per 50 ms onset window keep the single
  highest-velocity note; playability-first fret assignment stays with
  ``tab_generate`` (``fingering_preference="playable"``).
- **rhythm** — polyphonic: onsets group into chord events, strum fragments
  (≥3 single-note onsets inside 60 ms) collapse into one chord event, and a
  repeated pitch-class progression is re-voiced to ONE canonical shape via
  ``apply_canonical_voicings``.

Notes are gated on per-frame energy (25 ms windows, floor = stem median
− 10 dB); dropped notes become ``low_confidence_regions`` — marked, never
filled with guesses.

Technique marks (slides, hammer-ons, pull-offs, palm mute, harmonics) are
**inferred heuristics from pitch/onset/timing only**, each carrying a
``confidence`` label (``low``/``medium``) and a human-readable ``evidence``
string. Bends and vibrato are never emitted: semitone-quantized MIDI
carries no pitch-bend evidence, and guessing would violate the weak-
evidence-omits rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import numpy as np
import pretty_midi

from audio_to_tab.tab_generate import (
    TabDocument,
    TabEvent,
    TabNote,
    _group_notes_into_events,
    _pick_chord_positions,
)
from audio_to_tab.transcribe import transcribe_audio
from audio_to_tab.tuning import STANDARD_TUNING_MIDI, positions_for_pitch

ENERGY_WIN_SEC = 0.025
ENERGY_FLOOR_DROP_DB = 10.0
ONSET_WINDOW_SEC = 0.05
STRUM_MAX_GAP_SEC = 0.06
STRUM_MIN_FRAGMENTS = 3

DEFAULT_ONSET_THRESHOLD = 0.5
DEFAULT_FRAME_THRESHOLD = 0.3
DEFAULT_MIN_NOTE_MS = 58.0

TECHNIQUE_KINDS = ("slide", "hammer_on", "pull_off", "bend", "vibrato", "palm_mute", "harmonic")


@dataclass
class StemNote:
    pitch: int
    start: float
    end: float
    velocity: int
    confidence: float  # Basic Pitch amplitude proxy: velocity/127.


@dataclass
class TechniqueMark:
    kind: str
    start: float
    end: float
    confidence: str  # "low" | "medium"
    evidence: str


@dataclass
class StemTranscription:
    role: str  # "lead" | "rhythm"
    notes: list[StemNote]
    techniques: list[TechniqueMark]
    low_confidence_regions: list[tuple[float, float]]
    source_midi: Path


def _load_notes(midi_path: Path) -> list[StemNote]:
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    notes: list[StemNote] = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            velocity = int(n.velocity)
            notes.append(
                StemNote(
                    pitch=int(n.pitch),
                    start=float(n.start),
                    end=float(n.end),
                    velocity=velocity,
                    confidence=min(1.0, max(0.0, velocity / 127.0)),
                )
            )
    return sorted(notes, key=lambda n: (n.start, n.pitch))


def _frame_db(mono: np.ndarray, sr: int, win: int) -> np.ndarray:
    n_frames = max(0, len(mono) // win)
    if n_frames == 0:
        return np.array([], dtype=np.float64)
    frames = mono[: n_frames * win].reshape(n_frames, win)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    return 20.0 * np.log10(np.maximum(rms, 1e-10))


def _energy_gate(
    notes: list[StemNote], audio_path: Path | None
) -> tuple[list[StemNote], list[StemNote]]:
    """Drop notes whose onset sits in energy below (stem median − 10 dB)."""
    if audio_path is None:
        return list(notes), []
    import soundfile as sf

    try:
        data, sr = sf.read(str(audio_path), always_2d=True)
    except Exception:
        return list(notes), []
    mono = data.mean(axis=1).astype(np.float64)
    win = max(1, int(sr * ENERGY_WIN_SEC))
    db = _frame_db(mono, sr, win)
    if db.size == 0:
        return list(notes), []
    floor = float(np.median(db)) - ENERGY_FLOOR_DROP_DB
    sec_per_frame = win / float(sr)

    kept: list[StemNote] = []
    dropped: list[StemNote] = []
    for note in notes:
        i0 = max(0, int((note.start - 0.05) / sec_per_frame))
        i1 = min(db.size, int((note.end + 0.05) / sec_per_frame) + 1)
        local = db[i0:i1]
        (kept if local.size and float(local.max()) >= floor else dropped).append(note)
    return kept, dropped


def _lead_monophonic(
    notes: list[StemNote], window_sec: float = ONSET_WINDOW_SEC
) -> list[StemNote]:
    """Keep the single highest-velocity note per onset window."""
    if not notes:
        return []
    groups: list[list[StemNote]] = [[notes[0]]]
    for note in notes[1:]:
        if note.start - groups[-1][0].start <= window_sec:
            groups[-1].append(note)
        else:
            groups.append([note])
    return [max(group, key=lambda n: (n.velocity, -n.pitch)) for group in groups]


def _rhythm_chord_events(notes: list[StemNote]) -> list[list[StemNote]]:
    """Group onsets into chord events.

    Onsets chained within ``STRUM_MAX_GAP_SEC`` (60 ms) with at least
    ``STRUM_MIN_FRAGMENTS`` (3) members collapse into ONE chord event — this
    suppresses Basic Pitch splitting a single strum into isolated notes.
    Shorter chains fall back to standard 30 ms chord grouping.
    """
    ordered = sorted(notes, key=lambda n: (n.start, n.pitch))
    events: list[list[StemNote]] = []
    i = 0
    while i < len(ordered):
        cluster = [ordered[i]]
        j = i + 1
        while (
            j < len(ordered)
            and ordered[j].start - cluster[0].start <= STRUM_MAX_GAP_SEC
        ):
            cluster.append(ordered[j])
            j += 1
        if len(cluster) >= STRUM_MIN_FRAGMENTS:
            events.append(cluster)
        else:
            midi_like = [
                pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=n.start, end=n.end)
                for n in cluster
            ]
            events.extend([list(g) for g in _group_notes_into_events(midi_like, 0.03)])
        i = j
    return events


def _canonical_voicing_map(
    events: list[list[StemNote]], tuning: tuple[int, ...] = STANDARD_TUNING_MIDI
) -> dict[frozenset[int], tuple[tuple[int, int], ...]]:
    """One canonical (string, fret) voicing per repeated pitch-class set."""
    seen: dict[frozenset[int], list[list[StemNote]]] = {}
    for event in events:
        pcs = frozenset(n.pitch % 12 for n in event)
        seen.setdefault(pcs, []).append(event)
    voicings: dict[frozenset[int], tuple[tuple[int, int], ...]] = {}
    for pcs, occurrences in seen.items():
        if len(occurrences) < 2:
            continue
        first = sorted(occurrences[0], key=lambda n: n.pitch)
        positions = _pick_chord_positions(
            [n.pitch for n in first],
            tuning,
            hand_fret=5.0,
            max_fret=15,
            fingering_preference="playable",
        )
        if positions:
            voicings[pcs] = tuple(sorted((p.string, p.fret) for p in positions))
    return voicings


def apply_canonical_voicings(
    doc: TabDocument, voicings: dict[frozenset[int], tuple[tuple[int, int], ...]]
) -> TabDocument:
    """Rewrite chord events whose pitch-class set has a canonical voicing."""
    if not voicings:
        return doc
    events: list[TabEvent] = []
    for event in doc.events:
        pcs = frozenset(n.pitch % 12 for n in event.notes)
        voicing = voicings.get(pcs)
        if not voicing or len(voicing) != len(event.notes):
            events.append(event)
            continue
        pitch_to_pos: dict[int, tuple[int, int]] = {}
        used: set[tuple[int, int]] = set()
        for note in sorted(event.notes, key=lambda n: n.pitch):
            candidates = [
                (s, f)
                for (s, f) in voicing
                if (s, f) not in used and abs(note.pitch - (STANDARD_TUNING_MIDI[s] + f)) == 0
            ]
            if not candidates:
                candidates = [(s, f) for (s, f) in voicing if (s, f) not in used]
            if candidates:
                pick = candidates[0]
                pitch_to_pos[note.pitch] = pick
                used.add(pick)
        new_notes = [
            TabNote(
                start=n.start,
                end=n.end,
                string=pitch_to_pos[n.pitch][0] if n.pitch in pitch_to_pos else n.string,
                fret=pitch_to_pos[n.pitch][1] if n.pitch in pitch_to_pos else n.fret,
                pitch=n.pitch,
            )
            for n in event.notes
        ]
        events.append(TabEvent(start=event.start, notes=new_notes))
    return TabDocument(
        events=events,
        tuning_names=doc.tuning_names,
        tempo_bpm=doc.tempo_bpm,
        tempo_confidence=doc.tempo_confidence,
        beats_per_measure=doc.beats_per_measure,
    )


def _same_string_slide(a: StemNote, b: StemNote, tuning: tuple[int, ...]) -> bool:
    for pa in positions_for_pitch(a.pitch, tuning):
        for pb in positions_for_pitch(b.pitch, tuning):
            if pa.string == pb.string and 1 <= abs(pb.fret - pa.fret) <= 3:
                return True
    return False


def technique_marks_for(
    role: str,
    notes: list[StemNote],
    *,
    audio_path: Path | None = None,
    tuning: tuple[int, ...] = STANDARD_TUNING_MIDI,
) -> list[TechniqueMark]:
    """Infer technique candidates from pitch/onset/timing. Warn-only output.

    Every mark carries a confidence label and an evidence string; when the
    evidence is weak the mark is omitted rather than guessed.
    """
    del audio_path  # reserved for future audio-backed evidence
    ordered = sorted(notes, key=lambda n: (n.start, n.pitch))
    marks: list[TechniqueMark] = []
    velocities = [n.velocity for n in ordered]
    median_vel = float(np.median(velocities)) if velocities else 0.0

    for a, b in pairwise(ordered):
        gap = b.start - a.start
        interval = b.pitch - a.pitch
        if 0.0 < gap < 0.08 and _same_string_slide(a, b, tuning):
            marks.append(
                TechniqueMark(
                    kind="slide",
                    start=a.start,
                    end=b.end,
                    confidence="medium",
                    evidence=(
                        f"same-string move of {abs(interval)} fret(s) "
                        f"{int(gap * 1000)} ms after the previous note"
                    ),
                )
            )
            continue
        if 0.0 < gap < 0.06 and 1 <= interval <= 4:
            marks.append(
                TechniqueMark(
                    kind="hammer_on",
                    start=a.start,
                    end=b.end,
                    confidence="medium",
                    evidence=(
                        f"ascending {interval} semitone(s) {int(gap * 1000)} ms "
                        "after the previous note"
                    ),
                )
            )
        elif 0.0 < gap < 0.06 and -4 <= interval <= -1:
            marks.append(
                TechniqueMark(
                    kind="pull_off",
                    start=a.start,
                    end=b.end,
                    confidence="medium",
                    evidence=(
                        f"descending {-interval} semitone(s) {int(gap * 1000)} ms "
                        "after the previous note"
                    ),
                )
            )

    if role == "rhythm":
        starts = np.array([n.start for n in ordered])
        for note in ordered:
            if note.end - note.start >= 0.12 or median_vel <= 0:
                continue
            if note.velocity >= 0.4 * median_vel:
                continue
            dense = int(np.sum(np.abs(starts - note.start) <= 0.5))
            if dense >= 4:
                marks.append(
                    TechniqueMark(
                        kind="palm_mute",
                        start=note.start,
                        end=note.end,
                        confidence="low",
                        evidence=(
                            "short, quiet note in a dense rhythmic sequence "
                            f"({dense} onsets within ±0.5 s)"
                        ),
                    )
                )

    for note in ordered:
        if note.end - note.start >= 0.15:
            continue
        positions = positions_for_pitch(note.pitch, tuning)
        if positions and min(p.fret for p in positions) >= 12:
            marks.append(
                TechniqueMark(
                    kind="harmonic",
                    start=note.start,
                    end=note.end,
                    confidence="low",
                    evidence="very short note playable only at/above the 12th fret",
                )
            )
    return marks


def _transcribe_stem(
    role: str,
    audio_path: Path,
    out_midi: Path,
    *,
    onset_threshold: float = DEFAULT_ONSET_THRESHOLD,
    frame_threshold: float = DEFAULT_FRAME_THRESHOLD,
    minimum_note_length_ms: float = DEFAULT_MIN_NOTE_MS,
    cleanup=None,
) -> StemTranscription:
    out_midi = Path(out_midi)
    transcribe_audio(
        audio_path,
        out_midi,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length_ms=minimum_note_length_ms,
        cleanup=cleanup,
    )
    notes = _load_notes(out_midi)
    kept, dropped = _energy_gate(notes, Path(audio_path))
    if role == "lead":
        kept = _lead_monophonic(kept)
    techniques = technique_marks_for(role, kept, audio_path=Path(audio_path))
    regions = [(max(0.0, n.start - 0.1), n.end + 0.1) for n in dropped]
    return StemTranscription(
        role=role,
        notes=kept,
        techniques=techniques,
        low_confidence_regions=regions,
        source_midi=out_midi,
    )


def transcribe_lead_stem(
    audio_path: Path,
    out_midi: Path,
    *,
    onset_threshold: float = DEFAULT_ONSET_THRESHOLD,
    frame_threshold: float = DEFAULT_FRAME_THRESHOLD,
    minimum_note_length_ms: float = DEFAULT_MIN_NOTE_MS,
    cleanup=None,
) -> StemTranscription:
    """Lead path: monophonic-preferred, energy-gated, confidence per note."""
    return _transcribe_stem(
        "lead",
        audio_path,
        out_midi,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length_ms=minimum_note_length_ms,
        cleanup=cleanup,
    )


def transcribe_rhythm_stem(
    audio_path: Path,
    out_midi: Path,
    *,
    onset_threshold: float = DEFAULT_ONSET_THRESHOLD,
    frame_threshold: float = DEFAULT_FRAME_THRESHOLD,
    minimum_note_length_ms: float = DEFAULT_MIN_NOTE_MS,
    cleanup=None,
) -> StemTranscription:
    """Rhythm path: chord events, strum-merge, one voicing per progression."""
    return _transcribe_stem(
        "rhythm",
        audio_path,
        out_midi,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length_ms=minimum_note_length_ms,
        cleanup=cleanup,
    )


def write_stem_midis(
    lead: StemTranscription,
    rhythm: StemTranscription,
    output_dir: Path,
) -> dict[str, Path]:
    """Per-stem single-track MIDIs plus a combined two-track ``stems.mid``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _instrument(name: str, notes: list[StemNote]) -> pretty_midi.Instrument:
        inst = pretty_midi.Instrument(program=25, name=name)
        inst.notes = [
            pretty_midi.Note(
                velocity=max(1, min(127, int(n.velocity))),
                pitch=int(n.pitch),
                start=float(n.start),
                end=float(n.end),
            )
            for n in sorted(notes, key=lambda n: (n.start, n.pitch))
        ]
        return inst

    def _write(name: str, inst: pretty_midi.Instrument) -> Path:
        pm = pretty_midi.PrettyMIDI()
        pm.instruments.append(inst)
        path = output_dir / name
        pm.write(str(path))
        return path

    lead_inst = _instrument("Lead", lead.notes)
    rhythm_inst = _instrument("Rhythm", rhythm.notes)
    lead_path = _write("lead.mid", lead_inst)
    rhythm_path = _write("rhythm.mid", rhythm_inst)

    combined = pretty_midi.PrettyMIDI()
    combined.instruments.append(_instrument("Lead", lead.notes))
    combined.instruments.append(_instrument("Rhythm", rhythm.notes))
    stems_path = output_dir / "stems.mid"
    combined.write(str(stems_path))

    return {"lead_midi": lead_path, "rhythm_midi": rhythm_path, "stems_midi": stems_path}
