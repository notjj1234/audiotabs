/** Staff-position helpers for the notation and drum staves (sharps only, no key signature). */

export type Clef = 'treble' | 'bass';
export type DrumPiece = 'kick' | 'snare' | 'hihat';

// Pitch class → letter index (C=0 … B=6); sharps sit on the natural below.
const LETTER = [0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 5, 6];
const SHARP = new Set([1, 3, 6, 8, 10]);
// Diatonic index of each clef's bottom line: treble E4, bass G2.
const BOTTOM_LINE: Record<Clef, number> = { treble: 4 * 7 + 2, bass: 2 * 7 + 4 };

function diatonic(pitch: number): number {
  const octave = Math.floor(pitch / 12) - 1;
  return octave * 7 + LETTER[((pitch % 12) + 12) % 12];
}

/** Diatonic steps above the bottom staff line (lines are even steps 0–8). */
export function staffStep(pitch: number, clef: Clef): number {
  return diatonic(pitch) - BOTTOM_LINE[clef];
}

export function accidental(pitch: number): '#' | null {
  return SHARP.has(((pitch % 12) + 12) % 12) ? '#' : null;
}

/** Ledger-line steps needed to reach a note outside the five lines. */
export function ledgerLines(step: number): number[] {
  const out: number[] = [];
  for (let s = -2; s >= step; s -= 2) out.push(s);
  for (let s = 10; s <= step; s += 2) out.push(s);
  return out;
}

export function grandStaffFor(pitch: number, split = 60): Clef {
  return pitch >= split ? 'treble' : 'bass';
}

/** Staff step for each kit piece on a five-line percussion staff. */
export function drumStep(piece: DrumPiece): number {
  return piece === 'kick' ? 1 : piece === 'snare' ? 5 : 9;
}

/** Line index from the top for a tab string (string 0 = lowest). */
export function tabLine(string: number, strings: number): number {
  return strings - 1 - string;
}

export type Ottava = '8va' | '15ma' | '8vb' | '15mb' | null;

/** Keep a note within three ledger lines by octave folding; returns the mark to print. */
export function fitStep(step: number, lo = -6, hi = 14): { step: number; ottava: Ottava } {
  let shift = 0;
  let s = step;
  while (s < lo && shift < 2) {
    s += 7;
    shift += 1;
  }
  if (shift) return { step: s, ottava: shift === 1 ? '8vb' : '15mb' };
  while (s > hi && shift < 2) {
    s -= 7;
    shift += 1;
  }
  if (shift) return { step: s, ottava: shift === 1 ? '8va' : '15ma' };
  return { step, ottava: null };
}
