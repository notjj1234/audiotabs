/** Picker selection rules for the instruments screen (pure, unit-tested). */

export type InventoryRow = {
  id: string;
  label: string;
  family: string;
  stem: string;
  detected: boolean;
  confidence: number;
  reason: string;
  tabbable: boolean;
  tab_kind: 'tab' | 'staff' | 'drums';
  default_selected: boolean;
  note: string | null;
};

const isSplitPart = (id: string) => id === 'lead' || id === 'rhythm';

/**
 * Everything detected starts selected. Lead and Rhythm are selected whenever the
 * guitar was split, even if barely audible, and then Combined is not: it is those
 * same guitars merged.
 */
export function defaultSelection(inv: InventoryRow[]): string[] {
  const split = inv.some((r) => isSplitPart(r.id) && r.tabbable);
  return inv
    .filter(
      (r) =>
        r.tabbable && (r.detected || isSplitPart(r.id)) && !(r.id === 'combined' && split),
    )
    .map((r) => r.id);
}

/** Combined can't be picked while Lead or Rhythm is. */
export function isLocked(id: string, sel: string[]): boolean {
  return id === 'combined' && sel.some(isSplitPart);
}

/** Lead and Rhythm stay in the main grid even when not detected. */
export function isMainRow(row: Pick<InventoryRow, 'id' | 'detected'>): boolean {
  return row.detected || isSplitPart(row.id);
}

/** Short plain status for a tile: the first clause of the server's reason. */
export function shortReason(row: Pick<InventoryRow, 'detected' | 'reason' | 'tabbable'>): string {
  if (!row.tabbable) return 'Not separated';
  if (!row.detected) return 'Barely audible';
  const head = (row.reason || '').split(':')[0].trim();
  return head || 'Detected';
}

export function toggle(sel: string[], id: string, inv: InventoryRow[]): string[] {
  const next = new Set(sel);
  if (next.has(id)) next.delete(id);
  else if (!isLocked(id, sel)) {
    next.add(id);
    if (isSplitPart(id)) next.delete('combined');
  }
  return inv.map((r) => r.id).filter((rid) => next.has(rid));
}

export function canStart(sel: string[]): boolean {
  return sel.length > 0;
}

export function kindHint(row: Pick<InventoryRow, 'tab_kind'>): string {
  if (row.tab_kind === 'staff') return 'Notation';
  if (row.tab_kind === 'drums') return 'Drum hits (rough)';
  return 'Tab';
}

export function startLabel(count: number): string {
  if (count <= 0) return 'Choose an instrument';
  return `Make ${count} ${count === 1 ? 'tab' : 'tabs'}`;
}

export function groupRows(inv: InventoryRow[]): { guitar: InventoryRow[]; others: InventoryRow[] } {
  return {
    guitar: inv.filter((r) => r.family === 'guitar'),
    others: inv.filter((r) => r.family !== 'guitar'),
  };
}
