import { describe, expect, it } from 'vitest';

import {
  audibleTracks,
  beatsInMeasure,
  eventAt,
  fractionInMeasure,
  inLoop,
  loopBounds,
  measureAt,
  stepSpeed,
  timeInMeasure,
  type Measure,
  type TabEvent,
} from './tabModel';

const measures: Measure[] = [
  { index: 0, start: 0, end: 2 },
  { index: 1, start: 2, end: 4.1 },
  { index: 2, start: 4.1, end: 6 },
];

const ev = (start: number, measure: number): TabEvent => ({
  start,
  end: start + 0.25,
  measure,
  notes: [{ string: 0, fret: 3, pitch: 43, end: start + 0.25 }],
});

describe('tabModel', () => {
  it('finds the measure for a time, clamped at both ends', () => {
    expect(measureAt(measures, -1)).toBe(0);
    expect(measureAt(measures, 2)).toBe(1);
    expect(measureAt(measures, 4.09)).toBe(1);
    expect(measureAt(measures, 99)).toBe(2);
    expect(measureAt([], 1)).toBe(-1);
  });

  it('highlights the last started note only inside the current measure', () => {
    const events = [ev(0.5, 0), ev(1.0, 0), ev(4.5, 2)];
    expect(eventAt(events, measures, 0.2)).toBe(-1);
    expect(eventAt(events, measures, 1.2)).toBe(1);
    expect(eventAt(events, measures, 3.0)).toBe(-1); // empty measure 1
    expect(eventAt(events, measures, 5)).toBe(2);
  });

  it('maps time and position within a measure both ways', () => {
    expect(fractionInMeasure(measures[0], 1)).toBeCloseTo(0.5);
    expect(timeInMeasure(measures[0], 0.25)).toBeCloseTo(0.5);
    expect(timeInMeasure(measures[0], 2)).toBeCloseTo(2);
  });

  it('turns a measure range into seconds in either order', () => {
    expect(loopBounds(measures, { a: 2, b: 1 })).toEqual({ start: 2, end: 6 });
    expect(inLoop({ a: 2, b: 1 }, 1)).toBe(true);
    expect(inLoop({ a: 2, b: 1 }, 0)).toBe(false);
    expect(inLoop(null, 0)).toBe(false);
  });

  it('steps speed between 25% and 100%', () => {
    expect(stepSpeed(1, -1)).toBe(0.75);
    expect(stepSpeed(0.25, -1)).toBe(0.25);
    expect(stepSpeed(0.75, 1)).toBe(1);
    expect(stepSpeed(1, 1)).toBe(1);
  });

  it('lists the beats inside a measure', () => {
    expect(beatsInMeasure([0, 0.5, 1, 1.5, 2, 2.5], measures[0])).toEqual([0, 0.5, 1, 1.5]);
  });

  it('applies solo before mute', () => {
    const tracks = [
      { id: 'lead', label: 'Lead', events: [] },
      { id: 'rhythm', label: 'Rhythm', events: [] },
    ];
    expect(audibleTracks(tracks, {}, {})).toEqual(['lead', 'rhythm']);
    expect(audibleTracks(tracks, { lead: true }, {})).toEqual(['rhythm']);
    expect(audibleTracks(tracks, { rhythm: true }, { rhythm: true })).toEqual(['rhythm']);
  });
});
