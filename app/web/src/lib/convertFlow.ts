/** Entry draft, request building and Convert routing (picker vs direct job). */

import {
  DEFAULT_ENTRY_PRESET,
  type EntryPreset,
} from './entryDefaults';

export type SourceTab = 'upload' | 'youtube' | 'url';

/** Everything Entry collects. Owned by App so Back from the picker keeps it. */
export type EntryDraft = {
  restored: boolean;
  sourceTab: SourceTab;
  title: string;
  tuning: string;
  capo: number;
  preset: EntryPreset;
  fingering: string;
  showAdvanced: boolean;
  saferLength: boolean;
  maxDuration: number;
  fullTrackConfirm: boolean;
  separateStems: boolean;
  guitarEngine: string;
  mixAware: boolean;
  vocalDebleed: boolean;
  onset: number;
  frame: number;
  tempoOverride: number;
  uploadId: string | null;
  uploadName: string;
  uploadDuration: number;
  youtubeUrl: string;
  youtubeTitle: string;
  mediaUrl: string;
};

export type ConvertCaps = {
  ffmpeg: boolean;
  demucs: boolean;
  roformer: boolean;
};

export type ConvertRequest = {
  source: Record<string, string>;
  title: string;
  preset: EntryPreset;
  config: Record<string, unknown>;
};

export type ConvertRoute = 'picker' | 'direct' | 'direct_with_notice';

export const NO_SEPARATOR_NOTICE =
  "Instrument detection needs the stem separator, which isn't installed, so this converts the whole recording as one guitar tab.";

export function newDraft(): EntryDraft {
  return {
    restored: false,
    sourceTab: 'upload',
    title: '',
    tuning: 'Standard (EADGBE)',
    capo: 0,
    preset: DEFAULT_ENTRY_PRESET,
    fingering: 'playable',
    showAdvanced: false,
    saferLength: true,
    maxDuration: 90,
    fullTrackConfirm: false,
    separateStems: DEFAULT_ENTRY_PRESET === 'full_mix',
    guitarEngine: 'htdemucs_6s',
    mixAware: DEFAULT_ENTRY_PRESET === 'full_mix',
    vocalDebleed: true,
    onset: 0.5,
    frame: 0.3,
    tempoOverride: 0,
    uploadId: null,
    uploadName: '',
    uploadDuration: 0,
    youtubeUrl: '',
    youtubeTitle: '',
    mediaUrl: '',
  };
}

export function buildRequest(d: EntryDraft): ConvertRequest | { error: string } {
  if (!d.saferLength && !d.fullTrackConfirm) {
    return { error: 'Confirm full-track conversion or enable Safer length.' };
  }
  let source: Record<string, string>;
  if (d.sourceTab === 'upload') {
    if (!d.uploadId) return { error: 'Choose an audio file.' };
    source = { kind: 'upload', upload_id: d.uploadId };
  } else if (d.sourceTab === 'youtube') {
    if (!d.youtubeUrl.trim()) return { error: 'Search YouTube or paste a link.' };
    source = { kind: 'youtube', youtube_url: d.youtubeUrl.trim() };
  } else {
    if (!d.mediaUrl.trim()) return { error: 'Paste a media URL.' };
    source = { kind: 'media_url', media_url: d.mediaUrl.trim() };
  }
  const config: Record<string, unknown> = {
    tuning_name: d.tuning,
    capo: d.capo,
    fingering_preference: d.fingering,
    separate_stems: d.separateStems,
    mix_aware_filtering: d.mixAware,
    onset_threshold: d.onset,
    frame_threshold: d.frame,
    model: d.guitarEngine,
  };
  if (!d.vocalDebleed) config.vocal_debleed = 'off';
  if (d.saferLength) config.max_duration_sec = d.maxDuration;
  if (d.tempoOverride > 0) config.tempo_bpm_override = d.tempoOverride;
  return { source, title: d.title.trim() || 'Guitar Tab', preset: d.preset, config };
}

export function routeForConvert(
  d: Pick<EntryDraft, 'preset' | 'separateStems'>,
  caps: ConvertCaps | null,
): ConvertRoute {
  if (d.preset !== 'full_mix' || !d.separateStems) return 'direct';
  if (caps && !caps.demucs && !caps.roformer) return 'direct_with_notice';
  return 'picker';
}

/** Client-side reuse key; the server re-checks with its own fingerprint (409 on mismatch). */
export function analysisFingerprint(req: ConvertRequest): string {
  const src = req.source;
  const id = src.upload_id ?? src.youtube_url ?? src.media_url ?? '';
  return JSON.stringify([
    src.kind,
    id,
    req.config.model ?? null,
    req.config.max_duration_sec ?? null,
  ]);
}

/** True for youtube.com / youtu.be / music.youtube.com links. */
export function isYoutubeLink(url: string): boolean {
  try {
    const host = new URL(url.trim()).hostname.toLowerCase().replace(/^www\.|^m\./, '');
    return host === 'youtube.com' || host === 'youtu.be' || host === 'music.youtube.com';
  } catch {
    return false;
  }
}

/**
 * Settings for the "pick a source, then see the instruments" flow: full mix with
 * stem separation (so instruments can be detected) and the Lead/Rhythm split.
 * Tab settings (tuning, capo...) are chosen later on the picker.
 */
export function readyForDetection(d: EntryDraft, caps: ConvertCaps | null): EntryDraft {
  // Separation is always wanted here; when no separator is installed the router
  // sends the song straight to a single tab and says why (direct_with_notice).
  return {
    ...d,
    restored: true,
    preset: 'full_mix',
    separateStems: true,
    mixAware: true,
    // Lead/Rhythm is never optional. If the split can't run, the analysis falls
    // back and says why. Without a separator the direct path can't split at all.
    guitarEngine: caps && !caps.demucs && !caps.roformer ? 'htdemucs_6s' : 'lead_rhythm_split',
    fullTrackConfirm: !d.saferLength,
  };
}

/** Tab-only settings the picker can change without re-checking the instruments. */
export type TabOptions = {
  tuning: string;
  capo: number;
  fingering: string;
  vocalDebleed: boolean;
  tempoOverride: number;
};

export function tabOptionsFrom(d: EntryDraft): TabOptions {
  return {
    tuning: d.tuning,
    capo: d.capo,
    fingering: d.fingering,
    vocalDebleed: d.vocalDebleed,
    tempoOverride: d.tempoOverride,
  };
}

/** The job request with the picker's tab settings applied. */
export function withTabOptions(req: ConvertRequest, o: TabOptions): ConvertRequest {
  const config: Record<string, unknown> = {
    ...req.config,
    tuning_name: o.tuning,
    capo: Math.max(0, Math.min(12, Math.round(o.capo || 0))),
    fingering_preference: o.fingering,
  };
  if (o.vocalDebleed) delete config.vocal_debleed;
  else config.vocal_debleed = 'off';
  if (o.tempoOverride > 0) config.tempo_bpm_override = o.tempoOverride;
  else delete config.tempo_bpm_override;
  return { ...req, config };
}

/** "the first 90 seconds" / null for the whole song. */
export function checkedLengthText(req: ConvertRequest): string | null {
  const max = Number(req.config.max_duration_sec ?? 0);
  if (!max) return null;
  if (max % 60 === 0) return `the first ${max / 60} minute${max === 60 ? '' : 's'}`;
  return `the first ${max} seconds`;
}
