/**
 * Practice transport: plays either the recording (<audio>, speed without pitch change)
 * or a synthesized guitar from the tab (Web Audio, no library), with metronome,
 * count-in and A/B loop on one song clock so the cursor follows whichever is heard.
 */

import { beatLengthAt, type TabData } from './tabModel';

export type Source = 'recording' | 'synth';
export type TransportState = 'stopped' | 'counting' | 'playing';

type FlatNote = { track: string; start: number; end: number; pitch: number; chord: number };

const LOOKAHEAD_SEC = 0.15; // wall-clock seconds scheduled ahead of the cursor
const TICK_MS = 25;

/** Plucked-string tone (Karplus–Strong), rendered once per pitch and cached. */
function pluckBuffer(ctx: BaseAudioContext, pitch: number): AudioBuffer {
  const rate = ctx.sampleRate;
  const freq = 440 * Math.pow(2, (pitch - 69) / 12);
  const length = Math.floor(rate * 2.2);
  const buffer = ctx.createBuffer(1, length, rate);
  const out = buffer.getChannelData(0);
  const period = Math.max(2, Math.round(rate / freq));
  const ring = new Float32Array(period);
  let seed = pitch * 9301 + 49297;
  for (let i = 0; i < period; i += 1) {
    seed = (seed * 9301 + 49297) % 233280;
    ring[i] = seed / 233280 - 0.5;
  }
  // Higher strings decay faster, like a real guitar.
  const decay = 0.996 - Math.min(0.006, Math.max(0, (pitch - 40) * 0.00012));
  let index = 0;
  for (let i = 0; i < length; i += 1) {
    const next = (index + 1) % period;
    const value = decay * 0.5 * (ring[index] + ring[next]);
    out[i] = ring[index];
    ring[index] = value;
    index = next;
  }
  return buffer;
}

export class Transport {
  source: Source = 'recording';
  rate = 1;
  metronome = false;
  countIn = false;
  /** Track ids heard in synth playback (mute/solo), read when notes are scheduled. */
  audible: () => string[] = () => [];
  /** Synth volume (0..1) per track, from the mixer. */
  volume: (trackId: string) => number = () => 1;
  onchange: (state: TransportState) => void = () => {};

  private audio: HTMLAudioElement | null = null;
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private buffers = new Map<number, AudioBuffer>();
  private data: TabData | null = null;
  private notes: FlatNote[] = [];
  private beats: number[] = [];
  private barStarts = new Set<number>();
  private loop: { start: number; end: number } | null = null;

  private state: TransportState = 'stopped';
  private pausedAt = 0;
  private songAnchor = 0; // synth: song time at ctxAnchor
  private ctxAnchor = 0;
  private scheduledUntil = 0; // song time scheduled up to
  private voices = new Set<AudioScheduledSourceNode>();
  private timer: ReturnType<typeof setInterval> | undefined;
  private countTimer: ReturnType<typeof setTimeout> | undefined;

  attach(audio: HTMLAudioElement | null): void {
    this.audio = audio;
    if (audio) this.applyRate();
  }

  setData(data: TabData | null): void {
    this.data = data;
    const flat: FlatNote[] = [];
    for (const track of data?.tracks ?? []) {
      for (const event of track.events) {
        for (const note of event.notes) {
          // Drum hits have no pitch; the plucked-string synth stays silent for them.
          if (typeof note.pitch !== 'number') continue;
          flat.push({
            track: track.id,
            start: event.start,
            end: Math.max(note.end, event.start + 0.08),
            pitch: note.pitch,
            chord: event.notes.length,
          });
        }
      }
    }
    flat.sort((a, b) => a.start - b.start);
    this.notes = flat;
    this.beats = data?.beats ?? [];
    this.barStarts = new Set((data?.measures ?? []).map((m) => Math.round(m.start * 1000)));
  }

  setLoop(loop: { start: number; end: number } | null): void {
    this.loop = loop && loop.end > loop.start ? loop : null;
    if (this.loop && this.state === 'playing') {
      const t = this.time;
      if (t < this.loop.start || t >= this.loop.end) this.seek(this.loop.start);
    }
  }

  get playing(): boolean {
    return this.state === 'playing';
  }

  get duration(): number {
    if (this.source === 'recording' && this.audio && Number.isFinite(this.audio.duration)) {
      return this.audio.duration;
    }
    return this.data?.duration_sec ?? 0;
  }

  /** Current song position in seconds (what the cursor shows). */
  get time(): number {
    if (this.state !== 'playing') return this.pausedAt;
    if (this.source === 'recording') return this.audio?.currentTime ?? this.pausedAt;
    if (!this.ctx) return this.pausedAt;
    return this.songAnchor + (this.ctx.currentTime - this.ctxAnchor) * this.rate;
  }

  async play(): Promise<void> {
    if (this.state !== 'stopped') return;
    if (this.source === 'recording' && !this.audio?.src) return;
    const ctx = this.ensureContext();
    if (ctx.state === 'suspended') await ctx.resume();
    if (this.loop && (this.pausedAt < this.loop.start || this.pausedAt >= this.loop.end)) {
      this.pausedAt = this.loop.start;
    }
    if (this.pausedAt >= this.duration - 0.05) this.pausedAt = this.loop?.start ?? 0;
    if (this.source === 'recording' && this.audio) this.audio.currentTime = this.pausedAt;

    if (this.countIn && this.data) {
      const per = Math.max(1, this.data.beats_per_measure);
      const beat = beatLengthAt(this.data, this.pausedAt) / this.rate;
      const t0 = ctx.currentTime + 0.05;
      for (let k = 0; k < per; k += 1) this.click(t0 + k * beat, k === 0);
      this.setState('counting');
      this.countTimer = setTimeout(() => {
        this.countTimer = undefined;
        void this.start(t0 + per * beat);
      }, (t0 + per * beat - ctx.currentTime) * 1000);
      return;
    }
    await this.start(ctx.currentTime + 0.03);
  }

  pause(): void {
    if (this.countTimer) clearTimeout(this.countTimer);
    this.countTimer = undefined;
    if (this.state === 'playing') this.pausedAt = this.time;
    if (this.audio && !this.audio.paused) this.audio.pause();
    this.stopTicker();
    this.stopVoices();
    this.setState('stopped');
  }

  toggle(): void {
    if (this.state === 'stopped') void this.play();
    else this.pause();
  }

  seek(t: number): void {
    const target = Math.max(0, Math.min(t, this.duration || t));
    this.stopVoices();
    this.scheduledUntil = target;
    this.pausedAt = target;
    if (this.source === 'recording' && this.audio) this.audio.currentTime = target;
    if (this.state === 'playing' && this.source === 'synth' && this.ctx) {
      this.songAnchor = target;
      this.ctxAnchor = this.ctx.currentTime;
    }
  }

  setRate(rate: number): void {
    const t = this.time;
    this.rate = rate;
    this.applyRate();
    if (this.state === 'playing' && this.source === 'synth' && this.ctx) {
      this.songAnchor = t;
      this.ctxAnchor = this.ctx.currentTime;
      this.stopVoices();
      this.scheduledUntil = t;
    }
  }

  setSource(source: Source): void {
    if (source === this.source) return;
    const t = this.time;
    this.pause();
    this.source = source;
    this.pausedAt = t;
    if (source === 'recording' && this.audio) this.audio.currentTime = t;
  }

  /** Recording ended on its own. */
  handleEnded(): void {
    this.pausedAt = this.audio?.duration ?? this.pausedAt;
    this.stopTicker();
    this.stopVoices();
    this.setState('stopped');
  }

  /** Recording reset (new file loaded). */
  reset(): void {
    this.pause();
    this.pausedAt = 0;
  }

  dispose(): void {
    this.pause();
    void this.ctx?.close();
    this.ctx = null;
  }

  private async start(at: number): Promise<void> {
    const ctx = this.ensureContext();
    this.scheduledUntil = this.pausedAt;
    if (this.source === 'recording') {
      if (!this.audio) return;
      this.applyRate();
      this.audio.currentTime = this.pausedAt;
      try {
        await this.audio.play();
      } catch {
        this.setState('stopped');
        return;
      }
    } else {
      this.songAnchor = this.pausedAt;
      this.ctxAnchor = Math.max(at, ctx.currentTime);
    }
    this.setState('playing');
    this.stopTicker();
    this.timer = setInterval(() => this.tick(), TICK_MS);
    this.tick();
  }

  private tick(): void {
    if (this.state !== 'playing' || !this.ctx) return;
    const t = this.time;
    if (this.loop && t >= this.loop.end - 0.005) {
      this.seek(this.loop.start);
      return;
    }
    if (this.source === 'synth' && t >= this.duration) {
      this.pausedAt = this.duration;
      this.pause();
      return;
    }
    let horizon = t + LOOKAHEAD_SEC * this.rate;
    if (this.loop) horizon = Math.min(horizon, this.loop.end);
    const from = Math.max(this.scheduledUntil, t);
    if (horizon <= from) return;

    if (this.source === 'synth') {
      const heard = new Set(this.audible());
      for (const note of this.notesBetween(from, horizon)) {
        if (heard.has(note.track)) this.pluck(note, t);
      }
    }
    if (this.metronome) {
      for (const beat of this.beatsBetween(from, horizon)) {
        this.click(this.ctxTimeFor(beat, t), this.barStarts.has(Math.round(beat * 1000)));
      }
    }
    this.scheduledUntil = horizon;
  }

  private ctxTimeFor(songTime: number, now: number): number {
    const ctx = this.ctx as AudioContext;
    if (this.source === 'synth') return this.ctxAnchor + (songTime - this.songAnchor) / this.rate;
    return ctx.currentTime + (songTime - now) / this.rate;
  }

  private firstAtOrAfter(times: { length: number }, get: (i: number) => number, t: number): number {
    let lo = 0;
    let hi = times.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (get(mid) < t) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  private notesBetween(from: number, to: number): FlatNote[] {
    const out: FlatNote[] = [];
    for (
      let i = this.firstAtOrAfter(this.notes, (k) => this.notes[k].start, from);
      i < this.notes.length && this.notes[i].start < to;
      i += 1
    ) {
      out.push(this.notes[i]);
    }
    return out;
  }

  private beatsBetween(from: number, to: number): number[] {
    const out: number[] = [];
    for (
      let i = this.firstAtOrAfter(this.beats, (k) => this.beats[k], from);
      i < this.beats.length && this.beats[i] < to;
      i += 1
    ) {
      out.push(this.beats[i]);
    }
    return out;
  }

  private pluck(note: FlatNote, now: number): void {
    const ctx = this.ctx;
    if (!ctx || !this.master) return;
    let buffer = this.buffers.get(note.pitch);
    if (!buffer) {
      buffer = pluckBuffer(ctx, note.pitch);
      this.buffers.set(note.pitch, buffer);
    }
    const at = Math.max(ctx.currentTime, this.ctxTimeFor(note.start, now));
    const length = Math.min(2, Math.max(0.08, (note.end - note.start) / this.rate));
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const gain = ctx.createGain();
    const level = (0.35 * Math.max(0, Math.min(1, this.volume(note.track)))) / Math.sqrt(Math.max(1, note.chord));
    if (level <= 0) return;
    gain.gain.setValueAtTime(level, at);
    gain.gain.setTargetAtTime(0, at + length, 0.04);
    src.connect(gain).connect(this.master);
    src.start(at);
    src.stop(at + length + 0.3);
    this.track(src);
  }

  private click(at: number, accent: boolean): void {
    const ctx = this.ctx;
    if (!ctx || !this.master) return;
    const osc = ctx.createOscillator();
    osc.frequency.value = accent ? 1600 : 1100;
    const gain = ctx.createGain();
    const start = Math.max(ctx.currentTime, at);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(accent ? 0.5 : 0.3, start + 0.002);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.05);
    osc.connect(gain).connect(this.master);
    osc.start(start);
    osc.stop(start + 0.06);
    this.track(osc);
  }

  private track(node: AudioScheduledSourceNode): void {
    this.voices.add(node);
    node.onended = () => this.voices.delete(node);
  }

  private stopVoices(): void {
    for (const node of this.voices) {
      try {
        node.stop();
      } catch {
        // Already stopped.
      }
    }
    this.voices.clear();
  }

  private stopTicker(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
  }

  private applyRate(): void {
    if (!this.audio) return;
    const audio = this.audio as HTMLAudioElement & { webkitPreservesPitch?: boolean };
    audio.preservesPitch = true;
    audio.webkitPreservesPitch = true;
    audio.playbackRate = this.rate;
  }

  private ensureContext(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0.8;
      this.master.connect(this.ctx.destination);
    }
    return this.ctx;
  }

  private setState(next: TransportState): void {
    if (next === this.state) return;
    this.state = next;
    this.onchange(next);
  }
}
