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

import { exportFormats, nextTab, restoreView, toggleShown } from './scoreParts';

describe('multi-part helpers', () => {
  const ids = ['lead', 'rhythm', 'bass'];

  it('moves between part tabs with arrows, Home and End', () => {
    expect(nextTab(ids, 'lead', 'ArrowRight')).toBe('rhythm');
    expect(nextTab(ids, 'bass', 'ArrowRight')).toBe('lead');
    expect(nextTab(ids, 'lead', 'ArrowLeft')).toBe('bass');
    expect(nextTab(ids, 'rhythm', 'Home')).toBe('lead');
    expect(nextTab(ids, 'lead', 'End')).toBe('bass');
    expect(nextTab(ids, 'lead', 'x')).toBeNull();
  });

  it('restores a saved view, dropping parts the run no longer has', () => {
    expect(restoreView({ mode: 'together', part: 'bass', shown: ['bass', 'kazoo', 'lead'] }, ids)).toEqual({
      mode: 'together',
      part: 'bass',
      shown: ['lead', 'bass'],
    });
    expect(restoreView(null, ids)).toEqual({ mode: 'single', part: 'lead', shown: ids });
    expect(restoreView({ mode: 'together', part: 'gone', shown: [] }, ids)).toEqual({
      mode: 'together',
      part: 'lead',
      shown: ids,
    });
  });

  it('keeps at least one part shown together', () => {
    expect(toggleShown(['lead', 'bass'], 'lead', ids)).toEqual(['bass']);
    expect(toggleShown(['bass'], 'bass', ids)).toEqual(['bass']);
    expect(toggleShown(['bass'], 'lead', ids)).toEqual(['lead', 'bass']);
  });

  it('maps new parts to their stem listen source', () => {
    expect(listenForPart('bass', { bass_stem: true })).toBe('part:bass');
    expect(listenForPart('keys', { piano_stem: true })).toBe('part:keys');
    expect(listenForPart('vocals', {})).toBe('original');
    expect(parseScoreParts(['lead', 'bass', 'drums'])).toEqual(['lead', 'bass', 'drums']);
  });

  it('offers export formats each part kind supports', () => {
    expect(exportFormats('lead', 'tab').map((f) => [f.format, f.reason])).toEqual([
      ['pdf', null], ['midi', null], ['tab', null], ['gp5', null], ['musicxml', null],
    ]);
    expect(exportFormats('drums', 'drums').find((f) => f.format === 'musicxml')?.reason).toBeNull();
    const vocals = exportFormats('vocals', 'staff');
    expect(vocals.find((f) => f.format === 'pdf')?.reason).toBe(
      "PDF isn't available for notation parts yet; use MusicXML.",
    );
    expect(vocals.find((f) => f.format === 'midi')?.reason).toBeNull();
  });
});

describe('bass exports', () => {
  it('offers every tab format for bass', () => {
    expect(exportFormats('bass', 'tab').every((f) => f.reason === null)).toBe(true);
  });
});

import { isGenericRun, isGuitarPart, otherViewNote } from './scoreParts';

describe('picker runs outside the Tab view', () => {
  it('knows guitar parts', () => {
    expect(isGuitarPart('lead')).toBe(true);
    expect(isGuitarPart('combined')).toBe(true);
    expect(isGuitarPart('keys')).toBe(false);
  });

  it('detects picker runs from track kinds', () => {
    expect(isGenericRun([{ id: 'keys', kind: 'staff' }])).toBe(true);
    expect(isGenericRun([{ id: 'lead' }, { id: 'rhythm' }])).toBe(false);
    expect(isGenericRun(null)).toBe(false);
  });

  it('explains that non-guitar parts live in the Tab view', () => {
    expect(otherViewNote('keys', 'Piano / keys', 'piano')).toBe(
      'Piano / keys is shown in the Tab view. Chords, Piano roll and Text cover the guitar parts.',
    );
    expect(otherViewNote('lead', 'Lead guitar', 'piano')).toBeNull();
    expect(otherViewNote('keys', 'Piano / keys', 'staff')).toBeNull();
  });
});
