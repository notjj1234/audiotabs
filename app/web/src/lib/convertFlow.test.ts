import { describe, expect, it } from 'vitest';

import {
  analysisFingerprint,
  buildRequest,
  checkedLengthText,
  isYoutubeLink,
  newDraft,
  readyForDetection,
  routeForConvert,
  withTabOptions,
  type ConvertCaps,
} from './convertFlow';

const caps = (over: Partial<ConvertCaps> = {}): ConvertCaps => ({
  ffmpeg: true,
  demucs: true,
  roformer: false,
  ...over,
});

function uploadDraft() {
  const d = newDraft();
  d.uploadId = 'u1';
  d.title = 'Song';
  return d;
}

describe('buildRequest', () => {
  it('builds an upload request with settings', () => {
    const d = uploadDraft();
    d.capo = 2;
    const r = buildRequest(d);
    if ('error' in r) throw new Error(r.error);
    expect(r.source).toEqual({ kind: 'upload', upload_id: 'u1' });
    expect(r.config.capo).toBe(2);
    expect(r.config.max_duration_sec).toBe(90);
    expect(r.title).toBe('Song');
  });

  it('reports a missing source', () => {
    expect(buildRequest(newDraft())).toEqual({ error: 'Choose an audio file.' });
    const d = newDraft();
    d.sourceTab = 'youtube';
    expect(buildRequest(d)).toEqual({ error: 'Search YouTube or paste a link.' });
  });

  it('requires full-track confirmation when safer length is off', () => {
    const d = uploadDraft();
    d.saferLength = false;
    expect(buildRequest(d)).toEqual({
      error: 'Confirm full-track conversion or enable Safer length.',
    });
  });
});

describe('routeForConvert', () => {
  const full = () => {
    const d = uploadDraft();
    d.preset = 'full_mix';
    d.separateStems = true;
    return d;
  };

  it('opens the picker for a separated full mix', () => {
    expect(routeForConvert(full(), caps())).toBe('picker');
    expect(routeForConvert(full(), caps({ demucs: false, roformer: true }))).toBe('picker');
  });

  it('goes direct for solo or separation off, without a notice', () => {
    const solo = full();
    solo.preset = 'solo';
    expect(routeForConvert(solo, caps())).toBe('direct');
    const off = full();
    off.separateStems = false;
    expect(routeForConvert(off, caps())).toBe('direct');
  });

  it('goes direct with a notice when no separator is installed', () => {
    expect(routeForConvert(full(), caps({ demucs: false, roformer: false }))).toBe(
      'direct_with_notice',
    );
  });
});

describe('analysisFingerprint', () => {
  const fp = (edit: (d: ReturnType<typeof newDraft>) => void) => {
    const d = uploadDraft();
    edit(d);
    const r = buildRequest(d);
    if ('error' in r) throw new Error(r.error);
    return analysisFingerprint(r);
  };
  const base = fp(() => {});

  it('ignores tuning, capo, fingering and title', () => {
    expect(
      fp((d) => {
        d.tuning = 'Drop D';
        d.capo = 3;
        d.fingering = 'low_fret';
        d.title = 'Other';
      }),
    ).toBe(base);
  });

  it('changes with source, engine and length', () => {
    expect(fp((d) => (d.uploadId = 'u2'))).not.toBe(base);
    expect(fp((d) => (d.guitarEngine = 'bs_roformer_sw'))).not.toBe(base);
    expect(fp((d) => (d.maxDuration = 60))).not.toBe(base);
  });
});

describe('vocal de-bleed switch', () => {
  it('sends nothing by default and "off" when unticked', () => {
    const d = uploadDraft();
    const on = buildRequest(d);
    if ('error' in on) throw new Error(on.error);
    expect('vocal_debleed' in on.config).toBe(false);
    d.vocalDebleed = false;
    const off = buildRequest(d);
    if ('error' in off) throw new Error(off.error);
    expect(off.config.vocal_debleed).toBe('off');
  });
});

describe('pick-a-source flow', () => {
  it('recognises YouTube links and nothing else', () => {
    expect(isYoutubeLink('https://www.youtube.com/watch?v=abc')).toBe(true);
    expect(isYoutubeLink('https://youtu.be/abc')).toBe(true);
    expect(isYoutubeLink('https://music.youtube.com/watch?v=abc')).toBe(true);
    expect(isYoutubeLink('https://cdn.example.com/song.mp3')).toBe(false);
    expect(isYoutubeLink('not a link')).toBe(false);
  });

  it('always routes a chosen song to the instruments check when a separator exists', () => {
    const d = readyForDetection({ ...newDraft(), preset: 'solo', separateStems: false }, caps());
    expect(d.preset).toBe('full_mix');
    expect(d.separateStems).toBe(true);
    expect(routeForConvert(d, caps())).toBe('picker');
  });

  it('always asks for the Lead/Rhythm split, even if the engine looks missing', () => {
    expect(readyForDetection(newDraft(), caps()).guitarEngine).toBe('lead_rhythm_split');
    expect(readyForDetection(newDraft(), null).guitarEngine).toBe('lead_rhythm_split');
  });

  it('falls back to the direct path with a notice when no separator is installed', () => {
    const none = caps({ demucs: false, roformer: false });
    const d = readyForDetection(newDraft(), none);
    expect(routeForConvert(d, none)).toBe('direct_with_notice');
  });

  it('applies tab settings to the job without touching the source', () => {
    const d = uploadDraft();
    const r = buildRequest(d);
    if ('error' in r) throw new Error(r.error);
    const out = withTabOptions(r, {
      tuning: 'Drop D',
      capo: 3,
      fingering: 'low_fret',
      vocalDebleed: false,
      tempoOverride: 0,
    });
    expect(out.source).toEqual(r.source);
    expect(out.config.tuning_name).toBe('Drop D');
    expect(out.config.capo).toBe(3);
    expect(out.config.fingering_preference).toBe('low_fret');
    expect(out.config.vocal_debleed).toBe('off');
    expect(out.config.tempo_bpm_override).toBeUndefined();
    expect(analysisFingerprint(out)).toBe(analysisFingerprint(r));
  });

  it('says how much of the song was checked', () => {
    const d = uploadDraft();
    const r = buildRequest(d);
    if ('error' in r) throw new Error(r.error);
    expect(checkedLengthText({ ...r, config: { max_duration_sec: 90 } })).toBe('the first 90 seconds');
    expect(checkedLengthText({ ...r, config: { max_duration_sec: 120 } })).toBe('the first 2 minutes');
    expect(checkedLengthText({ ...r, config: {} })).toBeNull();
  });
});
