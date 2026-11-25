import type { AudioKind } from './api';

/** Part ids from the server: guitar parts plus the picker's other instruments. */
export type ScorePart = string;

const PART_LABELS: Record<string, string> = {
  lead: 'Lead',
  rhythm: 'Rhythm',
  combined: 'Combined',
  bass: 'Bass',
  vocals: 'Vocals',
  keys: 'Piano / keys',
  drums: 'Drums',
  other: 'Other',
};

const KNOWN = new Set(Object.keys(PART_LABELS));
const GUITAR = new Set(['lead', 'rhythm', 'combined']);
// Part id → stem artifact used as its listen source.
const STEM_ARTIFACT: Record<string, string> = {
  bass: 'bass_stem',
  vocals: 'vocals_stem',
  keys: 'piano_stem',
  drums: 'drums_stem',
  other: 'other_stem',
};

/** Prefer lead when present (matches server default). */
export function defaultScorePart(parts: string[] | undefined | null): ScorePart {
  if (parts?.includes('lead')) return 'lead';
  return 'combined';
}

export function partLabel(part: ScorePart): string {
  return PART_LABELS[part] ?? part;
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
  const stem = STEM_ARTIFACT[part];
  if (stem) return artifacts?.[stem] ? `part:${part}` : 'original';
  if (artifacts?.guitar_stem) return 'stem';
  return 'original';
}

export function parseScoreParts(raw: unknown): ScorePart[] {
  if (!Array.isArray(raw)) return ['combined'];
  const out = raw.filter((item): item is string => typeof item === 'string' && KNOWN.has(item));
  return out.length ? out : ['combined'];
}

/** Roving-tab navigation for the part tablist; null for keys it doesn't handle. */
export function nextTab(ids: string[], current: string, key: string): string | null {
  if (!ids.length) return null;
  const i = Math.max(0, ids.indexOf(current));
  if (key === 'ArrowRight') return ids[(i + 1) % ids.length];
  if (key === 'ArrowLeft') return ids[(i - 1 + ids.length) % ids.length];
  if (key === 'Home') return ids[0];
  if (key === 'End') return ids[ids.length - 1];
  return null;
}

export type ViewMode = 'single' | 'together';
export type SavedView = { mode: ViewMode; part: string; shown: string[] };

export function restoreView(
  saved: { mode?: string; part?: string | null; shown?: string[] } | null | undefined,
  available: string[],
): SavedView {
  const shown = available.filter((id) => saved?.shown?.includes(id));
  const part = saved?.part && available.includes(saved.part) ? saved.part : available[0];
  return {
    mode: saved?.mode === 'together' ? 'together' : 'single',
    part,
    shown: shown.length ? shown : [...available],
  };
}

/** Toggle a part in the Together set, in score order, never emptying it. */
export function toggleShown(shown: string[], id: string, order: string[]): string[] {
  const next = new Set(shown);
  if (next.has(id)) {
    if (next.size === 1) return shown;
    next.delete(id);
  } else {
    next.add(id);
  }
  return order.filter((x) => next.has(x));
}

export type ExportOption = {
  format: 'pdf' | 'midi' | 'tab' | 'gp5' | 'musicxml';
  label: string;
  reason: string | null;
};

const FORMAT_LABELS: Record<ExportOption['format'], string> = {
  pdf: 'PDF',
  midi: 'MIDI',
  tab: 'Text tab',
  gp5: 'Guitar Pro',
  musicxml: 'MusicXML',
};

/** Single-part export choices; unsupported ones stay visible with the reason. */
export function exportFormats(part: string, kind: 'tab' | 'staff' | 'drums'): ExportOption[] {
  const formats: ExportOption['format'][] = ['pdf', 'midi', 'tab', 'gp5', 'musicxml'];
  return formats.map((format) => {
    let reason: string | null = null;
    // Tab parts (guitar and bass) export every format; notation and drums are MIDI-only here.
    if (format !== 'midi' && format !== 'musicxml' && !GUITAR.has(part) && kind !== 'tab') {
      if (kind === 'staff') reason = `${FORMAT_LABELS[format]} isn't available for notation parts yet; use MusicXML.`;
      else reason = `${FORMAT_LABELS[format]} isn't available for drum parts yet; use MusicXML.`;
    }
    return { format, label: FORMAT_LABELS[format], reason };
  });
}

export function isGuitarPart(part: string): boolean {
  return GUITAR.has(part);
}

/** Runs made through the instrument picker carry a kind on every track. */
export function isGenericRun(tracks: { id: string; kind?: string }[] | null | undefined): boolean {
  return Boolean(tracks?.some((t) => t.kind !== undefined));
}

/** Chords / Piano roll / Text are guitar views; say so instead of showing guitar data. */
export function otherViewNote(part: string, label: string, view: string): string | null {
  if (view === 'staff' || GUITAR.has(part)) return null;
  return `${label} is shown in the Tab view. Chords, Piano roll and Text cover the guitar parts.`;
}
