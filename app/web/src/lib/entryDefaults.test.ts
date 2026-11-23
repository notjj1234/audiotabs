import { describe, expect, it } from 'vitest';

import {
  DEFAULT_ENTRY_PRESET,
  defaultGuitarEngine,
  engineForPreset,
} from './entryDefaults';

describe('entryDefaults', () => {
  it('defaults preset to full_mix', () => {
    expect(DEFAULT_ENTRY_PRESET).toBe('full_mix');
  });

  it('defaults engine to lead_rhythm_split when capability is on', () => {
    expect(defaultGuitarEngine({ lead_rhythm: true })).toBe('lead_rhythm_split');
  });

  it('defaults engine to demucs when lead_rhythm is unavailable', () => {
    expect(defaultGuitarEngine({ lead_rhythm: false })).toBe('htdemucs_6s');
    expect(defaultGuitarEngine(null)).toBe('htdemucs_6s');
  });

  it('drops lead_rhythm_split when switching to solo', () => {
    expect(engineForPreset('solo', 'lead_rhythm_split', { lead_rhythm: true })).toBe(
      'htdemucs_6s',
    );
  });

  it('restores lead_rhythm_split when switching back to full_mix', () => {
    expect(engineForPreset('full_mix', 'htdemucs_6s', { lead_rhythm: true })).toBe(
      'lead_rhythm_split',
    );
  });

  it('does not force lead_rhythm_split when capability is off', () => {
    expect(engineForPreset('full_mix', 'htdemucs_6s', { lead_rhythm: false })).toBe(
      'htdemucs_6s',
    );
  });
});
