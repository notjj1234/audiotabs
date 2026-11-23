import type { AudioKind } from './api';

export type ScorePart = 'lead' | 'rhythm' | 'combined';

const PART_LABELS: Record<ScorePart, string> = {
  lead: 'Lead',
  rhythm: 'Rhythm',
  combined: 'Combined',
};

/** Prefer lead when present (matches server default). */
export function defaultScorePart(parts: string[] | undefined | null): ScorePart {
  if (parts?.includes('lead')) return 'lead';
  return 'combined';
}

export function partLabel(part: ScorePart): string {
  return PART_LABELS[part];
}

/** Show the part switcher only when Lead or Rhythm exist alongside Combined. */
export function showPartSwitcher(parts: string[] | undefined | null): boolean {
  if (!parts || parts.length < 2) return false;
  return parts.includes('lead') || parts.includes('rhythm');
}

/** When switching score part, prefer the matching stem listen source. */
export function listenForPart(
  part: ScorePart,
  artifacts: Record<string, boolean> | undefined | null,
): AudioKind {
  if (part === 'lead' && artifacts?.lead_guitar) return 'lead';
  if (part === 'rhythm' && artifacts?.rhythm_guitar) return 'rhythm';
  if (artifacts?.guitar_stem) return 'stem';
  return 'original';
}

export function parseScoreParts(raw: unknown): ScorePart[] {
  if (!Array.isArray(raw)) return ['combined'];
  const out: ScorePart[] = [];
  for (const item of raw) {
    if (item === 'lead' || item === 'rhythm' || item === 'combined') out.push(item);
  }
  return out.length ? out : ['combined'];
}
