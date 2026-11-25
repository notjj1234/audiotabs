/** Structured tab from /score (view=staff) and pure helpers for the viewer and player. */

export type Technique = 'hammer_on' | 'pull_off' | 'slide' | 'palm_mute' | 'harmonic';

/** One sounding note. Tab parts carry string/fret, notation parts spelling, drums piece. */
export type TabNote = {
  string: number;
  fret: number;
  pitch: number;
  end: number;
  spelling?: string;
  piece?: 'kick' | 'snare' | 'hihat';
};

export type TabEvent = {
  start: number;
  end: number;
  measure: number;
  notes: TabNote[];
  rhythm?: { type: string; flags: number; dotted: boolean };
  beam?: number;
  techniques?: Technique[];
};

export type TrackKind = 'tab' | 'staff' | 'drums';

export type TabTrack = {
  id: string;
  label: string;
  events: TabEvent[];
  /** Missing on legacy runs, which are always guitar tab. */
  kind?: TrackKind;
  /** Open-string names, low to high (tab parts). */
  strings?: string[];
  clef?: 'treble' | 'grand';
  empty_reason?: string;
};

export function trackKind(track: Pick<TabTrack, 'kind'>): TrackKind {
  return track.kind ?? 'tab';
}

export type Measure = { index: number; start: number; end: number };

export type TabData = {
  ai_generated: boolean;
  tempo_bpm: number;
  beats_per_measure: number;
  duration_sec: number;
  tuning: string[];
  capo: number;
  beats: number[];
  measures: Measure[];
  tracks: TabTrack[];
  techniques_available: boolean;
};

export type LoopRange = { a: number; b: number };

export const SPEEDS = [0.25, 0.5, 0.75, 1] as const;

/** Index of the last item whose `start` is <= t (-1 before the first). */
function lastStartAtOrBefore<T>(items: T[], t: number, start: (item: T) => number): number {
  let lo = 0;
  let hi = items.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (start(items[mid]) <= t) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found;
}

/** Measure playing at time t (clamped to the first and last measure). */
export function measureAt(measures: Measure[], t: number): number {
  if (!measures.length) return -1;
  return Math.max(0, lastStartAtOrBefore(measures, t, (m) => m.start));
}

/** Note/chord being played at t: the last one started inside the current measure. */
export function eventAt(events: TabEvent[], measures: Measure[], t: number): number {
  const index = lastStartAtOrBefore(events, t + 1e-3, (e) => e.start);
  if (index < 0) return -1;
  const m = measureAt(measures, t);
  return events[index].measure === m ? index : -1;
}

/** 0..1 position of t across a measure. */
export function fractionInMeasure(measure: Measure, t: number): number {
  const span = measure.end - measure.start;
  if (span <= 0) return 0;
  return Math.max(0, Math.min(1, (t - measure.start) / span));
}

/** Time at a 0..1 position across a measure (inverse of fractionInMeasure). */
export function timeInMeasure(measure: Measure, fraction: number): number {
  const f = Math.max(0, Math.min(1, fraction));
  return measure.start + f * (measure.end - measure.start);
}

/** Seconds covered by an inclusive measure range, whichever order a and b were picked in. */
export function loopBounds(measures: Measure[], loop: LoopRange): { start: number; end: number } {
  const lo = Math.max(0, Math.min(loop.a, loop.b));
  const hi = Math.min(measures.length - 1, Math.max(loop.a, loop.b));
  return { start: measures[lo]?.start ?? 0, end: measures[hi]?.end ?? 0 };
}

export function inLoop(loop: LoopRange | null, measure: number): boolean {
  if (!loop) return false;
  return measure >= Math.min(loop.a, loop.b) && measure <= Math.max(loop.a, loop.b);
}

/** Next speed step up (+1) or down (-1). */
export function stepSpeed(current: number, direction: 1 | -1): number {
  const index = SPEEDS.findIndex((s) => Math.abs(s - current) < 1e-6);
  const from = index < 0 ? SPEEDS.length - 1 : index;
  const next = Math.max(0, Math.min(SPEEDS.length - 1, from + direction));
  return SPEEDS[next];
}

/** Beats inside a measure (for count-in and metronome accents). */
export function beatsInMeasure(beats: number[], measure: Measure): number[] {
  return beats.filter((b) => b >= measure.start - 1e-3 && b < measure.end - 1e-3);
}

/** Seconds per beat around time t (used for count-in spacing). */
export function beatLengthAt(data: Pick<TabData, 'measures' | 'beats_per_measure'>, t: number): number {
  const m = data.measures[measureAt(data.measures, t)];
  if (!m) return 0.5;
  return (m.end - m.start) / Math.max(1, data.beats_per_measure);
}

/** Relative layout width of a measure: busier bars get more room so digits never collide. */
export function measureMinWidth(eventCount: number): number {
  return Math.max(120, 28 + eventCount * 26);
}

const TECH_LABELS: Record<Technique, string> = {
  hammer_on: 'H',
  pull_off: 'P',
  slide: 'sl.',
  palm_mute: 'P.M.',
  harmonic: 'Harm.',
};

export function techniqueLabel(kind: Technique): string {
  return TECH_LABELS[kind] ?? '';
}

/** Tracks heard in synth playback after mute/solo. */
export function audibleTracks(
  tracks: TabTrack[],
  muted: Record<string, boolean>,
  solo: Record<string, boolean>,
): string[] {
  const soloed = tracks.filter((t) => solo[t.id]).map((t) => t.id);
  if (soloed.length) return soloed;
  return tracks.filter((t) => !muted[t.id]).map((t) => t.id);
}
