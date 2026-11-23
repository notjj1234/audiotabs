import { describe, expect, it } from 'vitest';

import { shouldApplyAudioResult } from './audioLoad';

// Stale-response guard for listen-source fetches: only the latest generation
// may commit its blob URL (switching Original ↔ stem races otherwise).
describe('shouldApplyAudioResult', () => {
  it('accepts a result that matches the current generation', () => {
    expect(shouldApplyAudioResult(3, 3)).toBe(true);
  });

  it('rejects a stale result from an older generation', () => {
    expect(shouldApplyAudioResult(2, 3)).toBe(false);
  });

  it('rejects a result newer than current (defensive)', () => {
    expect(shouldApplyAudioResult(5, 3)).toBe(false);
  });
});
