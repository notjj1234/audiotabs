import { describe, expect, it } from 'vitest';

import { formatBytes, formatDuration, joinSentence } from './format';

describe('formatBytes', () => {
  it('switches to MB with one decimal', () => {
    expect(formatBytes(4537.1 * 1024)).toBe('4.4 MB');
  });

  it('keeps KB under a megabyte', () => {
    expect(formatBytes(512 * 1024)).toBe('512.0 KB');
  });

  it('handles zero and garbage', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(Number.NaN)).toBe('0 B');
  });
});

describe('formatDuration', () => {
  it('formats minutes and zero-padded seconds', () => {
    expect(formatDuration(284)).toBe('4:44');
    expect(formatDuration(84)).toBe('1:24');
  });

  it('handles zero and negatives', () => {
    expect(formatDuration(0)).toBe('0:00');
    expect(formatDuration(-3)).toBe('0:00');
  });
});

describe('joinSentence', () => {
  it('joins with a period and capitalizes the second sentence', () => {
    expect(joinSentence('Playing the original audio.', 'ran without stem separation')).toBe(
      'Playing the original audio. Ran without stem separation',
    );
    expect(joinSentence('a.', 'b')).toBe('a. B');
  });

  it('adds a period when the lead has none', () => {
    expect(joinSentence('No chords recognized', 'try a cleaner section')).toBe(
      'No chords recognized. Try a cleaner section',
    );
  });

  it('passes through single empty halves', () => {
    expect(joinSentence('', 'b')).toBe('b');
    expect(joinSentence('a.', '')).toBe('a.');
  });
});
