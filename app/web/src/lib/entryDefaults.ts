/** Defaults for the conversion Entry screen. */

export type EntryCaps = {
  lead_rhythm?: boolean;
};

export type EntryPreset = 'solo' | 'full_mix';

/** Default preset: full mix so Lead/Rhythm can run. */
export const DEFAULT_ENTRY_PRESET: EntryPreset = 'full_mix';

/**
 * Guitar engine for a new Entry session.
 * Lead+Rhythm only when the Mel-Band split runtime is available.
 */
export function defaultGuitarEngine(caps: EntryCaps | null | undefined): string {
  if (caps?.lead_rhythm) return 'lead_rhythm_split';
  return 'htdemucs_6s';
}

/**
 * When the user picks Solo, drop Lead+Rhythm so we do not force a dual-guitar
 * split on an isolated take. Full mix restores the capability-aware default
 * only if the engine is still the previous default.
 */
export function engineForPreset(
  preset: EntryPreset,
  currentEngine: string,
  caps: EntryCaps | null | undefined,
): string {
  if (preset === 'solo' && currentEngine === 'lead_rhythm_split') {
    return 'htdemucs_6s';
  }
  if (preset === 'full_mix' && currentEngine === 'htdemucs_6s' && caps?.lead_rhythm) {
    return 'lead_rhythm_split';
  }
  return currentEngine;
}
