import { describe, expect, it } from 'vitest';

import {
  canStart,
  defaultSelection,
  groupRows,
  isLocked,
  isMainRow,
  kindHint,
  shortReason,
  startLabel,
  toggle,
  type InventoryRow,
} from './partsSelection';

function row(id: string, over: Partial<InventoryRow> = {}): InventoryRow {
  return {
    id,
    label: id,
    family: ['lead', 'rhythm', 'combined'].includes(id) ? 'guitar' : id,
    stem: id,
    detected: true,
    confidence: 0.8,
    reason: 'Clearly present: about 30% of the mix',
    tabbable: true,
    tab_kind: 'tab',
    default_selected: true,
    note: null,
    ...over,
  };
}

const INV: InventoryRow[] = [
  row('lead'),
  row('rhythm'),
  row('combined', { default_selected: false }),
  row('bass'),
  row('vocals', { tab_kind: 'staff' }),
  row('keys', { tab_kind: 'staff', detected: false, default_selected: false }),
  row('drums', { tab_kind: 'drums' }),
  row('other', { tab_kind: 'staff', default_selected: false }),
];

describe('partsSelection', () => {
  it('selects every detected instrument, but not Combined when Lead/Rhythm exist', () => {
    expect(defaultSelection(INV)).toEqual(['lead', 'rhythm', 'bass', 'vocals', 'drums', 'other']);
  });

  it('selects Combined when the guitar could not be split', () => {
    const off = { detected: false, tabbable: false };
    const inv = [row('lead', off), row('rhythm', off), row('combined')];
    expect(defaultSelection(inv)).toEqual(['combined']);
  });

  it('never pre-selects a part that was not detected', () => {
    expect(defaultSelection([row('keys', { detected: false, default_selected: true })])).toEqual([]);
  });

  it('turns the reason into a short status', () => {
    expect(shortReason(row('bass'))).toBe('Clearly present');
    expect(shortReason(row('keys', { detected: false }))).toBe('Barely audible');
  });

  it('toggles while keeping inventory order', () => {
    const sel = toggle(['rhythm'], 'lead', INV);
    expect(sel).toEqual(['lead', 'rhythm']);
    expect(toggle(sel, 'lead', INV)).toEqual(['rhythm']);
  });

  it('requires at least one part', () => {
    expect(canStart([])).toBe(false);
    expect(canStart(['bass'])).toBe(true);
  });

  it('locks Combined while Lead or Rhythm is ticked', () => {
    expect(isLocked('combined', ['lead'])).toBe(true);
    expect(isLocked('combined', ['rhythm', 'bass'])).toBe(true);
    expect(isLocked('combined', ['bass'])).toBe(false);
    expect(isLocked('lead', ['rhythm'])).toBe(false);
    expect(toggle(['lead'], 'combined', INV)).toEqual(['lead']);
    expect(toggle([], 'combined', INV)).toEqual(['combined']);
  });

  it('drops Combined when Lead or Rhythm is ticked', () => {
    expect(toggle(['combined', 'bass'], 'rhythm', INV)).toEqual(['rhythm', 'bass']);
  });

  it('pre-ticks barely audible Lead and Rhythm, never Combined with them', () => {
    const inv = [row('lead', { detected: false }), row('rhythm', { detected: false }), row('combined')];
    expect(defaultSelection(inv)).toEqual(['lead', 'rhythm']);
  });

  it('keeps Lead and Rhythm in the main grid even when not detected', () => {
    expect(isMainRow(row('lead', { detected: false }))).toBe(true);
    expect(isMainRow(row('rhythm', { detected: false }))).toBe(true);
    expect(isMainRow(row('keys', { detected: false }))).toBe(false);
  });

  it('says when Lead or Rhythm could not be separated', () => {
    expect(shortReason(row('lead', { tabbable: false, detected: false }))).toBe('Not separated');
  });

  it('names each kind of output plainly', () => {
    expect(kindHint(row('lead'))).toBe('Tab');
    expect(kindHint(row('vocals', { tab_kind: 'staff' }))).toBe('Notation');
    expect(kindHint(row('drums', { tab_kind: 'drums' }))).toBe('Drum hits (rough)');
  });

  it('labels the start button with the count', () => {
    expect(startLabel(1)).toBe('Make 1 tab');
    expect(startLabel(3)).toBe('Make 3 tabs');
    expect(startLabel(0)).toBe('Choose an instrument');
  });

  it('groups guitar rows first', () => {
    const g = groupRows(INV);
    expect(g.guitar.map((r) => r.id)).toEqual(['lead', 'rhythm', 'combined']);
    expect(g.others.map((r) => r.id)).toEqual(['bass', 'vocals', 'keys', 'drums', 'other']);
  });
});
