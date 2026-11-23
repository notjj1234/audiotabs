import { describe, expect, it } from 'vitest';

import {
  defaultScorePart,
  listenForPart,
  parseScoreParts,
  showPartSwitcher,
} from './scoreParts';

describe('scoreParts', () => {
  it('defaults to lead when available', () => {
    expect(defaultScorePart(['lead', 'rhythm', 'combined'])).toBe('lead');
    expect(defaultScorePart(['combined'])).toBe('combined');
  });

  it('shows switcher only when stem parts exist', () => {
    expect(showPartSwitcher(['lead', 'rhythm', 'combined'])).toBe(true);
    expect(showPartSwitcher(['combined'])).toBe(false);
    expect(showPartSwitcher(null)).toBe(false);
  });

  it('maps part to matching listen source', () => {
    const arts = { lead_guitar: true, rhythm_guitar: true, guitar_stem: true };
    expect(listenForPart('lead', arts)).toBe('lead');
    expect(listenForPart('rhythm', arts)).toBe('rhythm');
    expect(listenForPart('combined', arts)).toBe('stem');
    expect(listenForPart('combined', {})).toBe('original');
  });

  it('parses parts from API payload', () => {
    expect(parseScoreParts(['lead', 'rhythm', 'combined'])).toEqual([
      'lead',
      'rhythm',
      'combined',
    ]);
    expect(parseScoreParts(['nope'])).toEqual(['combined']);
  });
});
