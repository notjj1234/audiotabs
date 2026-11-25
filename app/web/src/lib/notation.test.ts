import { describe, expect, it } from 'vitest';

import { accidental, drumStep, grandStaffFor, ledgerLines, staffStep, tabLine } from './notation';

describe('notation helpers', () => {
  it('places E4 on the bottom line of the treble staff', () => {
    expect(staffStep(64, 'treble')).toBe(0);
    expect(staffStep(77, 'treble')).toBe(8); // F5 top line
  });

  it('puts middle C one ledger line below the treble staff', () => {
    expect(staffStep(60, 'treble')).toBe(-2);
    expect(ledgerLines(-2)).toEqual([-2]);
    expect(ledgerLines(-3)).toEqual([-2]);
    expect(ledgerLines(-4)).toEqual([-2, -4]);
    expect(ledgerLines(4)).toEqual([]);
    expect(ledgerLines(10)).toEqual([10]);
    expect(ledgerLines(11)).toEqual([10]);
  });

  it('places G2 on the bottom line of the bass staff', () => {
    expect(staffStep(43, 'bass')).toBe(0);
    expect(staffStep(57, 'bass')).toBe(8); // A3 top line
  });

  it('spells sharps on their natural letter with a sharp sign', () => {
    expect(accidental(66)).toBe('#');
    expect(accidental(64)).toBeNull();
    expect(staffStep(66, 'treble')).toBe(staffStep(65, 'treble'));
  });

  it('splits the grand staff at middle C', () => {
    expect(grandStaffFor(60)).toBe('treble');
    expect(grandStaffFor(59)).toBe('bass');
  });

  it('puts kick, snare and hi-hat on distinct rows', () => {
    expect(drumStep('kick')).toBe(1);
    expect(drumStep('snare')).toBe(5);
    expect(drumStep('hihat')).toBe(9);
  });

  it('maps tab strings to lines from the top for any string count', () => {
    expect(tabLine(0, 6)).toBe(5); // low E at the bottom
    expect(tabLine(5, 6)).toBe(0);
    expect(tabLine(0, 4)).toBe(3); // bass low E at the bottom
  });
});

import { fitStep } from './notation';

describe('fitStep', () => {
  it('leaves notes within three ledger lines alone', () => {
    expect(fitStep(-6)).toEqual({ step: -6, ottava: null });
    expect(fitStep(14)).toEqual({ step: 14, ottava: null });
  });

  it('folds very low notes up an octave and marks 8vb', () => {
    expect(fitStep(-9)).toEqual({ step: -2, ottava: '8vb' });
    expect(fitStep(-20)).toEqual({ step: -6, ottava: '15mb' });
  });

  it('folds very high notes down and marks 8va', () => {
    expect(fitStep(17)).toEqual({ step: 10, ottava: '8va' });
  });
});
