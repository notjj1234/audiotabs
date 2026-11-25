"""Bar-level lead/rhythm role check on the two transcribed guitar stems.

Lead and rhythm are *functional roles*, not timbres (Régnier, Martin & Bigo,
ISMIR 2021: rhythm = sections that make the listener perceive the chord
progression; lead = foreground line). The audio splitter
(``lead_rhythm_sep``) decides roles from sound alone, so it can misfile
material: lead notes leak into the rhythm residual, a solo/fill played while
the lead stem is silent ends up in "rhythm", or the only guitar playing an
arpeggiated riff lands in "lead".

In isolated stems only textural cues survive, so this pass uses those, per bar:

- **texture** — simultaneous notes per onset (chords vs single notes);
- **chord-progression realisation** — how much of the bar's sounding time sits
  on one triad's pitch classes (arpeggios and chords outline the harmony);
- **pitch-contour continuity** — share of small melodic steps (lead lines move
  stepwise and legato);
- **repetition** — similarity to other bars of the same stem (riffs and
  accompaniment repeat; solos usually don't — Pati & Lerch, AES 2017).

Roles switch inside songs (lead changes every ~23 s live; Ou et al., ICASSP
2025), so decisions are per bar, and a move needs either a neighbouring bar
that agrees or strong evidence in the bar itself. Every move is reported with
its reason; when the cues are ambiguous nothing moves (warn-only, no guessing).
Bends/vibrato and foreground salience are not used: semitone MIDI has no bend
evidence, and salience against the band is not recoverable from a stem.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Protocol

ONSET_GROUP_SEC = 0.05  # notes starting this close together form one event (chord)
BLEED_ONSET_SEC = 0.06  # same pitch this close in both stems = one performance heard twice
REPEAT_SIMILAR = 0.6  # Jaccard similarity at which a bar counts as a repeat
CHORD_FIT_MIN = 0.8  # share of sounding time on one triad to "outline a chord"
MELODIC_POLYPHONY_MAX = 1.25  # mean notes per event for a single-note line
CONTOUR_MIN = 0.6  # share of steps of <= 4 semitones for a continuous line
MIN_LINE_EVENTS = 4  # a line needs at least this many onsets in the bar
STRONG_LINE_EVENTS = 6  # this many onsets moves a bar without a neighbour agreeing
EMPTY_EVENTS_MAX = 1  # the other stem counts as silent with at most this many onsets

# None of these thresholds has been fitted to labelled segments yet; they are
# written into lead_rhythm_roles.json so they can be tuned from real songs.
CONSTANT_PROVENANCE: dict[str, str] = dict.fromkeys(("ONSET_GROUP_SEC", "BLEED_ONSET_SEC", "REPEAT_SIMILAR", "CHORD_FIT_MIN", "MELODIC_POLYPHONY_MAX", "CONTOUR_MIN", "MIN_LINE_EVENTS", "STRONG_LINE_EVENTS", "EMPTY_EVENTS_MAX"), "UNCALIBRATED: hand-set guess")

_TRIADS: tuple[tuple[str, frozenset[int]], ...] = tuple(
    (f"{root}{kind}", frozenset({root % 12, (root + third) % 12, (root + 7) % 12}))
    for root in range(12)
    for kind, third in (("maj", 4), ("min", 3))
)


class NoteLike(Protocol):
    pitch: int
    start: float
    end: float


@dataclass(frozen=True)
class BarFeatures:
    events: int
    notes: int
    polyphony: float  # mean simultaneous notes per event
    chord_ratio: float  # share of events with >= 3 notes
    chord_fit: float  # best share of sounding time on one triad
    contour: float  # share of small melodic steps between successive events
    repeat: float  # best similarity to another bar of the same stem


@dataclass
class RoleMove:
    bar: int
    start: float
    end: float
    from_stem: str
    to_stem: str
    notes: int
    reason: str


@dataclass
class RoleReport:
    bars: list[dict] = field(default_factory=list)
    moves: list[RoleMove] = field(default_factory=list)
    bleed_removed: int = 0
    chords_to_rhythm: int = 0  # chord attacks from the lead stem given to rhythm
    chords_left: int = 0  # lead-stem chords left alone because rhythm was already playing

    def to_dict(self) -> dict:
        return {
            "method": "bar-level texture cues (polyphony, chord outline, contour, repetition)",
            "constants": CONSTANT_PROVENANCE,
            "chords_to_rhythm": self.chords_to_rhythm,
            "chords_left_in_lead": self.chords_left,
            "bleed_removed": self.bleed_removed,
            "moves": [m.__dict__ for m in self.moves],
            "bars": self.bars,
        }


def _beat_bars(
    beats: Sequence[float], downbeats: Sequence[float], per: int, end_time: float
) -> list[float]:
    """Every ``per`` detected beats, phased to agree with most downbeats (holes filled)."""
    times = sorted(t for t in beats if math.isfinite(t) and t >= 0)
    gaps = sorted(b - a for a, b in pairwise(times) if b > a)
    if len(times) < per + 1 or not gaps:
        return []
    beat = gaps[(len(gaps) - 1) // 2]
    grid = [times[0]]
    for t in times[1:]:
        if t - grid[-1] < 0.6 * beat:
            continue
        while t - grid[-1] > 1.6 * beat:
            grid.append(grid[-1] + beat)
        grid.append(t)
    while grid[-1] + beat < end_time:
        grid.append(grid[-1] + beat)
    tolerance = 0.25 * beat

    def hits(phase: int) -> int:
        return sum(1 for t in grid[phase::per] if any(abs(t - d) <= tolerance for d in downbeats))

    phase = max(range(per), key=hits) if downbeats else 0
    starts = grid[phase::per]
    if starts[0] > 0.25 * beat * per:
        starts.insert(0, 0.0)
    else:
        starts[0] = 0.0
    return starts


def bar_starts(
    *,
    downbeats: Sequence[float],
    tempo_bpm: float,
    beats_per_measure: int,
    end_time: float,
    beats: Sequence[float] = (),
) -> list[float]:
    """Bar start times: the beat grid phased to the downbeats, else downbeats, else fixed tempo."""
    from_beats = _beat_bars(beats, downbeats, max(1, beats_per_measure), end_time)
    if from_beats:
        return from_beats
    fixed = 60.0 / (tempo_bpm if tempo_bpm and tempo_bpm > 0 else 120.0) * max(1, beats_per_measure)
    times = sorted(t for t in downbeats if math.isfinite(t) and t >= 0)
    gaps = sorted(b - a for a, b in pairwise(times) if b > a)
    if not gaps:
        return [i * fixed for i in range(max(1, math.ceil(end_time / fixed)))]
    # Lower median: missed downbeats only ever make gaps longer.
    length = gaps[(len(gaps) - 1) // 2]
    starts = [0.0]
    for t in times:
        if t - starts[-1] < 0.5 * length:
            continue
        while t - starts[-1] > 1.6 * length:
            starts.append(starts[-1] + length)
        starts.append(t)
    while starts[-1] + length < end_time:
        starts.append(starts[-1] + length)
    return starts


def _bar_index(starts: Sequence[float], t: float) -> int:
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= t:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _events(notes: Sequence[NoteLike]) -> list[list[NoteLike]]:
    ordered = sorted(notes, key=lambda n: (n.start, n.pitch))
    groups: list[list[NoteLike]] = []
    for note in ordered:
        if groups and note.start - groups[-1][0].start <= ONSET_GROUP_SEC:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups


def _chord_fit(notes: Sequence[NoteLike]) -> float:
    weights: dict[int, float] = {}
    for n in notes:
        weights[n.pitch % 12] = weights.get(n.pitch % 12, 0.0) + max(0.01, n.end - n.start)
    total = sum(weights.values())
    if total <= 0 or len(weights) < 3:
        return 0.0
    best = 0.0
    for _, pcs in _TRIADS:
        covered = [pc for pc in pcs if pc in weights]
        if len(covered) < 3:
            continue
        best = max(best, sum(weights[pc] for pc in covered) / total)
    return best


def _fingerprint(notes: Sequence[NoteLike], start: float, length: float) -> frozenset[tuple[int, int]]:
    """Onset (in 16ths of the bar) and pitch class, so transposed-octave repeats still match."""
    step = length / 16 if length > 0 else 0.125
    return frozenset((round((n.start - start) / step), n.pitch % 12) for n in notes)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def bar_features(
    notes: Sequence[NoteLike], starts: Sequence[float], end_time: float
) -> list[BarFeatures]:
    """Texture features for every bar of one stem."""
    per_bar: list[list[NoteLike]] = [[] for _ in starts]
    for n in notes:
        per_bar[_bar_index(starts, n.start)].append(n)
    lengths = [
        (starts[i + 1] if i + 1 < len(starts) else max(end_time, starts[i] + 0.5)) - starts[i]
        for i in range(len(starts))
    ]
    prints = [_fingerprint(b, starts[i], lengths[i]) for i, b in enumerate(per_bar)]
    out: list[BarFeatures] = []
    for i, bar_notes in enumerate(per_bar):
        events = _events(bar_notes)
        n_events = len(events)
        tops = [max(e, key=lambda n: n.pitch).pitch for e in events]
        steps = [abs(b - a) for a, b in pairwise(tops)]
        repeat = max(
            (_jaccard(prints[i], prints[j]) for j in range(len(prints)) if j != i),
            default=0.0,
        )
        out.append(
            BarFeatures(
                events=n_events,
                notes=len(bar_notes),
                polyphony=(len(bar_notes) / n_events) if n_events else 0.0,
                chord_ratio=(sum(1 for e in events if len(e) >= 3) / n_events) if n_events else 0.0,
                chord_fit=_chord_fit(bar_notes),
                contour=(sum(1 for s in steps if s <= 4) / len(steps)) if steps else 0.0,
                repeat=repeat,
            )
        )
    return out


def texture_label(f: BarFeatures) -> str:
    """'silent', 'chords', 'line' (single-note), 'arpeggio' (chord spelled out) or 'mixed'."""
    if f.events <= EMPTY_EVENTS_MAX:
        return "silent"
    if f.chord_ratio >= 0.5:
        return "chords"
    if f.polyphony <= MELODIC_POLYPHONY_MAX:
        return "arpeggio" if f.chord_fit >= CHORD_FIT_MIN else "line"
    return "mixed"


def remove_bleed(lead: list, rhythm: list) -> tuple[list, int]:
    """Drop rhythm notes that repeat a lead note on their own (the lead heard in the residual).

    A same-pitch copy that sits inside a rhythm chord stays: the chord needs it.
    """
    rhythm_sorted = sorted(rhythm, key=lambda n: n.start)
    onsets = [n.start for n in rhythm_sorted]
    lead_keys = sorted((n.start, n.pitch) for n in lead)
    kept = []
    removed = 0
    for i, note in enumerate(rhythm_sorted):
        neighbours = sum(
            1
            for j in range(max(0, i - 6), min(len(onsets), i + 7))
            if j != i and abs(onsets[j] - note.start) <= ONSET_GROUP_SEC
        )
        duplicate = any(
            pitch == note.pitch and abs(start - note.start) <= BLEED_ONSET_SEC
            for start, pitch in lead_keys
            if abs(start - note.start) <= BLEED_ONSET_SEC
        )
        if duplicate and neighbours == 0:
            removed += 1
            continue
        kept.append(note)
    return kept, removed


def route_lead_chords(
    lead: list, rhythm: list, chords: Sequence[Sequence]
) -> tuple[list, list, int, int]:
    """Give chord attacks found in the lead stem to rhythm (rhythm tends to play chords).

    A chord moves, all its notes, when the rhythm stem has no attack at that moment;
    the single note the monophonic lead path kept from it leaves the lead. When rhythm
    is already playing there, the chord is most likely rhythm heard in the lead stem
    (already tabbed in rhythm), so nothing changes. Returns
    (lead, rhythm, chords_moved, chords_left).
    """
    if not chords:
        return lead, rhythm, 0, 0
    rhythm_onsets = sorted(n.start for n in rhythm)
    moved_notes: list = []
    drop: list[tuple[float, set[int]]] = []
    moved = left = 0
    for chord in chords:
        if not chord:
            continue
        t0 = min(n.start for n in chord)
        i = bisect.bisect_left(rhythm_onsets, t0 - BLEED_ONSET_SEC)
        if i < len(rhythm_onsets) and rhythm_onsets[i] <= t0 + BLEED_ONSET_SEC:
            left += 1
            continue
        moved += 1
        moved_notes.extend(chord)
        drop.append((t0, {n.pitch for n in chord}))
    if not moved:
        return lead, rhythm, 0, left
    kept_lead = [
        n
        for n in lead
        if not any(abs(n.start - t0) <= ONSET_GROUP_SEC and n.pitch in pitches for t0, pitches in drop)
    ]
    new_rhythm = sorted([*rhythm, *moved_notes], key=lambda n: (n.start, n.pitch))
    return kept_lead, new_rhythm, moved, left


def assign_roles(
    lead: Iterable,
    rhythm: Iterable,
    *,
    downbeats: Sequence[float] = (),
    beats: Sequence[float] = (),
    tempo_bpm: float = 120.0,
    beats_per_measure: int = 4,
    lead_chords: Sequence[Sequence] = (),
) -> tuple[list, list, RoleReport]:
    """Return corrected (lead, rhythm) note lists and a report of what moved and why.

    ``lead_chords`` are whole chord attacks the lead stem held (its monophonic path
    kept one note of each); they go to rhythm first, since rhythm tends to play chords.
    """
    lead_notes = list(lead)
    rhythm_notes = list(rhythm)
    report = RoleReport()
    lead_notes, rhythm_notes, report.chords_to_rhythm, report.chords_left = route_lead_chords(
        lead_notes, rhythm_notes, lead_chords
    )
    rhythm_notes, report.bleed_removed = remove_bleed(lead_notes, rhythm_notes)

    end_time = max((n.end for n in [*lead_notes, *rhythm_notes]), default=0.0)
    if end_time <= 0:
        return lead_notes, rhythm_notes, report
    starts = bar_starts(
        downbeats=downbeats,
        tempo_bpm=tempo_bpm,
        beats_per_measure=beats_per_measure,
        end_time=end_time,
        beats=beats,
    )
    lead_f = bar_features(lead_notes, starts, end_time)
    rhythm_f = bar_features(rhythm_notes, starts, end_time)

    # Candidate moves per bar: ("to_lead" | "to_rhythm", reason, strong).
    candidates: list[tuple[str, str, bool] | None] = []
    for lf, rf in zip(lead_f, rhythm_f, strict=True):
        lead_tex, rhythm_tex = texture_label(lf), texture_label(rf)
        move: tuple[str, str, bool] | None = None
        if (
            lead_tex == "silent"
            and rhythm_tex == "line"
            and rf.events >= MIN_LINE_EVENTS
            and rf.contour >= CONTOUR_MIN
            and rf.repeat < REPEAT_SIMILAR
        ):
            move = (
                "to_lead",
                "single-note line that moves stepwise and doesn't repeat, with no lead playing",
                rf.events >= STRONG_LINE_EVENTS,
            )
        elif (
            rhythm_tex == "silent"
            and lead_tex == "arpeggio"
            and lf.repeat >= REPEAT_SIMILAR
        ):
            move = (
                "to_rhythm",
                "repeating figure that spells out a chord, with no rhythm guitar playing",
                lf.events >= STRONG_LINE_EVENTS,
            )
        candidates.append(move)

    accepted: list[tuple[str, str] | None] = []
    for i, cand in enumerate(candidates):
        if cand is None:
            accepted.append(None)
            continue
        kind, reason, strong = cand
        prev_same = i > 0 and candidates[i - 1] is not None and candidates[i - 1][0] == kind
        next_same = (
            i + 1 < len(candidates)
            and candidates[i + 1] is not None
            and candidates[i + 1][0] == kind
        )
        accepted.append((kind, reason) if strong or prev_same or next_same else None)

    moved_to_lead: list = []
    moved_to_rhythm: list = []
    keep_lead: list = []
    keep_rhythm: list = []
    for n in rhythm_notes:
        a = accepted[_bar_index(starts, n.start)]
        (moved_to_lead if a and a[0] == "to_lead" else keep_rhythm).append(n)
    for n in lead_notes:
        a = accepted[_bar_index(starts, n.start)]
        (moved_to_rhythm if a and a[0] == "to_rhythm" else keep_lead).append(n)

    for i, (lf, rf) in enumerate(zip(lead_f, rhythm_f, strict=True)):
        end = starts[i + 1] if i + 1 < len(starts) else end_time
        decision = accepted[i]
        report.bars.append(
            {
                "bar": i + 1,
                "start": round(starts[i], 3),
                "lead_texture": texture_label(lf),
                "rhythm_texture": texture_label(rf),
                "lead_repeat": round(lf.repeat, 2),
                "rhythm_repeat": round(rf.repeat, 2),
                "moved": decision[0] if decision else None,
            }
        )
        if decision:
            kind, reason = decision
            count = rf.notes if kind == "to_lead" else lf.notes
            report.moves.append(
                RoleMove(
                    bar=i + 1,
                    start=round(starts[i], 3),
                    end=round(end, 3),
                    from_stem="rhythm" if kind == "to_lead" else "lead",
                    to_stem="lead" if kind == "to_lead" else "rhythm",
                    notes=count,
                    reason=reason,
                )
            )

    new_lead = sorted([*keep_lead, *moved_to_lead], key=lambda n: (n.start, n.pitch))
    new_rhythm = sorted([*keep_rhythm, *moved_to_rhythm], key=lambda n: (n.start, n.pitch))
    return new_lead, new_rhythm, report
