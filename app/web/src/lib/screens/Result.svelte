<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte';

  import {
    apiFetch,
    downloadExport,
    fetchAudioObjectUrl,
    type AudioKind,
  } from '../api';
  import { shouldApplyAudioResult } from '../audioLoad';
  import TabPlayer from '../components/TabPlayer.svelte';
  import {
    defaultScorePart,
    listenForPart,
    parseScoreParts,
    partLabel,
    showPartSwitcher,
    type ScorePart,
  } from '../scoreParts';

  type ScoreLayout = {
    measure_sec: number;
    measure_width: number;
    row_height: number;
    bars_per_line: number;
    measure_count: number;
    row_count: number;
    origin_x: number;
    origin_y: number;
    note_inset: number;
    note_span: number;
    width: number;
    height: number;
  };

  type Score = {
    view: string;
    svg: string;
    text: string;
    meta: {
      title: string;
      key: string;
      tempo_bpm: number;
      duration_sec: number;
      beats_per_measure?: number;
      tuning_name: string;
      capo: number;
      transpose: number;
      bars_per_line: number;
      lyrics_status?: string;
    };
    layout?: ScoreLayout | null;
    artifacts: Record<string, boolean>;
    part?: string;
    parts?: string[];
  };

  type RunMeta = {
    details?: {
      lead_rhythm_fallback?: boolean;
      lead_rhythm_fallback_reason?: string;
    } | null;
  };

  let {
    runId,
    onnew,
  }: {
    runId: string;
    onnew: () => void;
  } = $props();

  let view = $state('staff');
  let tuning = $state('Standard (EADGBE)');
  let capo = $state(0);
  let transpose = $state(0);
  let bars = $state(4);
  let score = $state<Score | null>(null);
  let error = $state<string | null>(null);
  let part = $state<ScorePart>('lead');
  let parts = $state<ScorePart[]>(['combined']);
  let listen = $state<AudioKind>('original');
  let audioSrc = $state<string | null>(null);
  let audioPending = $state(false);
  let confirmNew = $state(false);
  let exportOpen = $state(false);
  let panelOpen = $state(false);
  let fallbackNotice = $state<string | null>(null);
  let didInitialListenSync = false;

  let audioEl = $state<HTMLAudioElement | null>(null);
  let scoreEl = $state<HTMLDivElement | null>(null);
  let playing = $state(false);
  let playTime = $state(0);
  let audioDuration = $state(0);
  // Non-reactive generation counter so $effect does not re-subscribe on bumps.
  let audioLoadGen = 0;

  async function loadRunMeta() {
    try {
      const meta = await apiFetch<RunMeta>(`/api/runs/${encodeURIComponent(runId)}`);
      if (meta.details?.lead_rhythm_fallback) {
        fallbackNotice =
          meta.details.lead_rhythm_fallback_reason ||
          'Lead/rhythm split was unavailable; showing a single guitar tab.';
      } else {
        fallbackNotice = null;
      }
    } catch {
      fallbackNotice = null;
    }
  }

  async function loadScore() {
    try {
      const q = new URLSearchParams({
        view,
        tuning,
        capo: String(capo),
        transpose: String(transpose),
        bars: String(bars),
        part,
      });
      const next = await apiFetch<Score>(`/api/runs/${encodeURIComponent(runId)}/score?${q}`);
      score = next;
      const parsed = parseScoreParts(next.parts);
      parts = parsed;
      if (next.part === 'lead' || next.part === 'rhythm' || next.part === 'combined') {
        part = next.part;
      } else {
        part = defaultScorePart(parsed);
      }
      if (!didInitialListenSync) {
        listen = listenForPart(part, next.artifacts);
        didInitialListenSync = true;
      }
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Could not load score.';
    }
  }

  function selectPart(next: ScorePart) {
    if (next === part) return;
    part = next;
    listen = listenForPart(next, score?.artifacts);
  }

  async function loadAudio(kind: AudioKind) {
    // untrack: reading/writing audioSrc must not re-subscribe the listen effect
    // (that loop nulls the blob forever and storms /audio with 200s).
    const prev = untrack(() => audioSrc);
    if (prev) URL.revokeObjectURL(prev);
    audioLoadGen += 1;
    const gen = audioLoadGen;
    untrack(() => {
      audioSrc = null;
      audioPending = true;
    });
    try {
      const url = await fetchAudioObjectUrl(runId, kind);
      if (!shouldApplyAudioResult(gen, audioLoadGen)) {
        URL.revokeObjectURL(url);
        return;
      }
      untrack(() => {
        audioSrc = url;
        audioPending = false;
      });
    } catch {
      if (!shouldApplyAudioResult(gen, audioLoadGen)) return;
      untrack(() => {
        audioSrc = null;
        audioPending = false;
      });
    }
  }

  onMount(() => {
    void loadRunMeta();
    void loadScore();
  });

  onDestroy(() => {
    audioLoadGen += 1;
    const prev = untrack(() => audioSrc);
    if (prev) URL.revokeObjectURL(prev);
  });

  $effect(() => {
    void view;
    void tuning;
    void capo;
    void transpose;
    void bars;
    void part;
    void loadScore();
  });

  // Depends only on listen (+ runId from props). loadAudio uses untrack for audioSrc.
  $effect(() => {
    const kind = listen;
    void runId;
    playing = false;
    playTime = 0;
    audioDuration = 0;
    void loadAudio(kind);
  });

  function togglePlay() {
    if (!audioEl || !audioSrc) return;
    if (audioEl.paused) void audioEl.play();
    else audioEl.pause();
  }

  function seekTo(time: number) {
    if (!audioEl) return;
    audioEl.currentTime = time;
    playTime = time;
  }

  // Percentage position of the playhead within the SVG box. The SVG scales
  // uniformly (width:100%, height:auto), so percentages track it exactly as
  // long as the generator keeps that scaling; if it ever changes, switch to
  // getScreenCTM() math.
  let playhead = $derived.by(() => {
    const layout = score?.layout;
    if (view !== 'staff' || !layout || !audioEl) return null;
    const measureSec = layout.measure_sec > 0 ? layout.measure_sec : 1;
    const barsPerLine = Math.max(1, layout.bars_per_line);
    let measureIndex = Math.floor(playTime / measureSec);
    measureIndex = Math.max(0, Math.min(layout.measure_count - 1, measureIndex));
    const row = Math.floor(measureIndex / barsPerLine);
    const col = measureIndex % barsPerLine;
    const rel = Math.max(0, Math.min(1, (playTime - measureIndex * measureSec) / measureSec));
    const x = layout.origin_x + col * layout.measure_width + layout.note_inset + rel * layout.note_span;
    const top = layout.origin_y + row * layout.row_height;
    // Cover the six staff lines (5 × 12px span) plus a small margin, like the
    // row markers in notation_view.score_playhead_html.
    const blockH = Math.min(64, layout.height - top);
    return {
      left: `${(x / layout.width) * 100}%`,
      top: `${(top / layout.height) * 100}%`,
      height: `${(blockH / layout.height) * 100}%`,
    };
  });

  $effect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      playTime = audioEl?.currentTime ?? 0;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  });

  // Keep the active staff row in view while playing so the tab moves with the song.
  let followedRow = -1;
  $effect(() => {
    if (!playing) {
      followedRow = -1;
      return;
    }
    const layout = score?.layout;
    if (!layout || !scoreEl || view !== 'staff') return;
    const measureSec = layout.measure_sec > 0 ? layout.measure_sec : 1;
    const barsPerLine = Math.max(1, layout.bars_per_line);
    const measureIndex = Math.max(
      0,
      Math.min(layout.measure_count - 1, Math.floor(playTime / measureSec)),
    );
    const row = Math.floor(measureIndex / barsPerLine);
    if (row === followedRow) return;
    followedRow = row;
    const reduce =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    scoreEl
      .querySelector('.playhead')
      ?.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
  });

  $effect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if (ev.code !== 'Space') return;
      const target = ev.target as HTMLElement | null;
      if (target && ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(target.tagName)) return;
      if (exportOpen || confirmNew || !audioSrc) return;
      ev.preventDefault();
      togglePlay();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  function onScoreClick(ev: MouseEvent) {
    const layout = score?.layout;
    if (view !== 'staff' || !layout || !audioEl || !scoreEl) return;
    if ((ev.target as HTMLElement).closest('.float')) return;
    const svg = scoreEl.querySelector('svg');
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const scaleX = rect.width / layout.width;
    const scaleY = rect.height / layout.height;
    if (scaleX <= 0 || scaleY <= 0) return;
    const x = (ev.clientX - rect.left) / scaleX;
    const y = (ev.clientY - rect.top) / scaleY;
    const barsPerLine = Math.max(1, layout.bars_per_line);
    const measureSec = layout.measure_sec > 0 ? layout.measure_sec : 1;
    const row = Math.max(
      0,
      Math.min(layout.row_count - 1, Math.floor((y - layout.origin_y) / layout.row_height)),
    );
    const col = Math.max(
      0,
      Math.min(barsPerLine - 1, Math.floor((x - layout.origin_x) / layout.measure_width)),
    );
    const rel = Math.max(
      0,
      Math.min(
        1,
        (x - layout.origin_x - col * layout.measure_width - layout.note_inset) / layout.note_span,
      ),
    );
    seekTo((row * barsPerLine + col + rel) * measureSec);
  }

  async function sendFeedback(answer: 'yes' | 'no') {
    await apiFetch(`/api/runs/${encodeURIComponent(runId)}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer }),
    });
  }

  async function doExport(format: string) {
    await downloadExport(runId, { format, tuning, capo, transpose, bars });
    exportOpen = false;
  }
</script>

<section class="result rise-in">
  {#if error}
    <p class="banner" role="alert">{error}</p>
  {/if}
  {#if fallbackNotice}
    <p class="banner warn" role="status">{fallbackNotice}</p>
  {/if}

  <header class="chrome">
    <div class="identity">
      <h1>{score?.meta.title || 'Result'}</h1>
      {#if score}
        <p class="meta">
          Key {score.meta.key} · {Math.round(score.meta.tempo_bpm)} BPM ·
          {Math.floor(score.meta.duration_sec / 60)}:{String(Math.floor(score.meta.duration_sec % 60)).padStart(2, '0')}
        </p>
      {/if}
    </div>
    <div class="views" role="tablist" aria-label="Score view">
      {#each [['staff', 'Tab'], ['chords', 'Chords'], ['piano', 'Piano roll'], ['text', 'Text']] as [id, label]}
        <button
          type="button"
          class:active={view === id}
          onclick={() => (view = id)}>{label}</button
        >
      {/each}
    </div>
  </header>

  {#if showPartSwitcher(parts)}
    <div class="parts" role="tablist" aria-label="Guitar part">
      {#each parts as id}
        <button
          type="button"
          class:active={part === id}
          onclick={() => selectPart(id)}>{partLabel(id)}</button
        >
      {/each}
    </div>
  {/if}

  <div class="score-stage">
    <!-- Click-to-seek on the score surface; keyboard users get the same via the transport slider. -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions, a11y_click_events_have_key_events -->
    <div class="score" role="img" aria-label="Score" bind:this={scoreEl} onclick={onScoreClick}>
      {#if score?.svg}
        {@html score.svg}
      {/if}
      {#if playhead}
        <div class="playhead-layer" aria-hidden="true">
          <div
            class="playhead"
            style:left={playhead.left}
            style:top={playhead.top}
            style:height={playhead.height}
          ></div>
        </div>
      {/if}
      {#if score?.text}
        <pre>{score.text}</pre>
      {/if}
      {#if !score}
        <p class="muted"><span class="spinner is-on"></span> Loading score…</p>
      {/if}
    </div>

    <div class="float" class:open={panelOpen}>
      <button
        type="button"
        class="fab"
        aria-expanded={panelOpen}
        aria-controls="result-controls"
        onclick={() => (panelOpen = !panelOpen)}
      >
        {#if panelOpen}
          Close
        {:else}
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M4 7h16M4 12h16M4 17h10"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
          Controls
        {/if}
      </button>

      {#if panelOpen}
        <div class="panel" id="result-controls" role="dialog" aria-label="Score controls">
          <div class="panel-actions">
            <div class="export">
              <button type="button" class="ghost" onclick={() => (exportOpen = !exportOpen)}
                >Export</button
              >
              {#if exportOpen}
                <div class="menu">
                  {#each ['pdf', 'midi', 'tab', 'gp5'] as fmt}
                    {#if !score || score.artifacts[fmt] !== false}
                      <button type="button" onclick={() => doExport(fmt)}>{fmt.toUpperCase()}</button>
                    {/if}
                  {/each}
                  {#if score?.artifacts.guitar_stem}
                    <button type="button" onclick={() => doExport('guitar_stem')}>Guitar stem</button>
                  {/if}
                  {#if score?.artifacts.musicxml}
                    <button type="button" onclick={() => doExport('musicxml')}>MusicXML</button>
                  {/if}
                </div>
              {/if}
            </div>
            {#if confirmNew}
              <span class="confirm">Start over?</span>
              <button type="button" class="ghost" onclick={() => (confirmNew = false)}>Keep</button>
              <button type="button" class="danger" onclick={onnew}>Discard</button>
            {:else}
              <button type="button" class="ghost" onclick={() => (confirmNew = true)}>New song</button>
            {/if}
          </div>

          <h2>Inspector</h2>
          <label class="field"
            ><span>Tuning</span>
            <select bind:value={tuning}>
              <option>Standard (EADGBE)</option>
              <option>Drop D</option>
              <option>Half-step down</option>
            </select></label
          >
          <label class="field"
            ><span>Capo</span>
            <input type="number" min="0" max="12" bind:value={capo} /></label
          >
          <label class="field"
            ><span>Transpose</span>
            <input type="number" min="-12" max="12" bind:value={transpose} /></label
          >
          <label class="field"
            ><span>Bars per line</span>
            <input type="number" min="1" max="8" bind:value={bars} /></label
          >

          <div class="feedback">
            <span>Does this sound right?</span>
            <button type="button" class="ghost" onclick={() => sendFeedback('yes')}>Yes</button>
            <button type="button" class="ghost" onclick={() => sendFeedback('no')}>Not quite</button>
          </div>
        </div>
      {/if}
    </div>
  </div>

  <div class="transport">
    <fieldset class="listen">
      <legend>Listen</legend>
      <label><input type="radio" bind:group={listen} value="original" /> Original</label>
      {#if score?.artifacts.guitar_stem}
        <label><input type="radio" bind:group={listen} value="stem" /> Guitar stem</label>
      {/if}
      {#if score?.artifacts.lead_guitar}
        <label><input type="radio" bind:group={listen} value="lead" /> Lead</label>
      {/if}
      {#if score?.artifacts.rhythm_guitar}
        <label><input type="radio" bind:group={listen} value="rhythm" /> Rhythm</label>
      {/if}
    </fieldset>
    <audio
      bind:this={audioEl}
      src={audioSrc}
      preload="metadata"
      class="sr-audio"
      onplay={() => (playing = true)}
      onpause={() => (playing = false)}
      onended={() => (playing = false)}
      onloadedmetadata={() => (audioDuration = audioEl?.duration ?? 0)}
    ></audio>
    <TabPlayer
      available={audioSrc !== null}
      pending={audioPending}
      {playing}
      currentTime={playTime}
      duration={audioDuration}
      ontoggle={togglePlay}
      onseek={seekTo}
    />
  </div>
</section>

<style>
  .result {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-height: calc(100vh - 120px);
  }
  .chrome {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    flex-shrink: 0;
  }
  .identity {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-3) var(--space-4);
  }
  h1 {
    font-family: var(--font-display);
    font-size: var(--fs-5);
    font-weight: var(--weight-medium);
  }
  .meta {
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: var(--fs-2);
  }
  .views {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .views button {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 0;
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .views button.active {
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
  }
  .parts {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .parts button {
    min-height: 40px;
    padding: 0 var(--space-3);
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .parts button.active {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 22%, transparent);
    color: var(--text);
    font-weight: var(--weight-semibold);
  }
  .score-stage {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .score {
    position: relative;
    flex: 1 1 auto;
    background: color-mix(in srgb, var(--art) 72%, var(--surface));
    border: 1px solid color-mix(in srgb, var(--line) 14%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-3);
    overflow-x: hidden;
    overflow-y: auto;
    min-height: calc(100vh - 280px);
  }
  .playhead-layer {
    position: absolute;
    top: var(--space-3);
    bottom: var(--space-3);
    left: var(--space-3);
    right: var(--space-3);
    pointer-events: none;
  }
  .playhead {
    position: absolute;
    width: 2px;
    background: var(--accent);
    border-radius: 1px;
    box-shadow: 0 0 6px color-mix(in srgb, var(--accent) 65%, transparent);
  }
  .score :global(svg) {
    display: block;
    width: 100%;
    max-width: 100%;
    height: auto;
  }
  pre {
    white-space: pre;
    font-family: var(--font-mono);
    font-size: var(--fs-3);
    line-height: 1.45;
  }
  .float {
    position: absolute;
    right: var(--space-4);
    bottom: var(--space-4);
    z-index: 6;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: var(--space-2);
  }
  .fab {
    min-height: 44px;
    padding: 0 var(--space-4);
    border: 0;
    border-radius: var(--radius-3);
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
  }
  .panel {
    width: min(280px, calc(100vw - 96px));
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 18%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
  }
  .panel h2 {
    font-size: var(--fs-4);
    font-weight: var(--weight-medium);
  }
  .panel-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
  }
  .export {
    position: relative;
  }
  .menu {
    position: absolute;
    left: 0;
    bottom: 100%;
    margin-bottom: var(--space-2);
    background: var(--bg);
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-2);
    display: flex;
    flex-direction: column;
    min-width: 140px;
    z-index: 7;
  }
  .menu button {
    min-height: 44px;
    border: 0;
    background: transparent;
    color: var(--text);
    text-align: left;
    padding: 0 var(--space-4);
    cursor: pointer;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .field span {
    font-size: var(--fs-2);
    color: var(--muted);
  }
  input,
  select {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 1px solid rgba(168, 184, 204, 0.4);
    border-radius: var(--radius-1);
    background: var(--bg);
    color: var(--text);
  }
  .feedback {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    color: var(--muted);
    padding-top: var(--space-2);
    border-top: 1px solid color-mix(in srgb, var(--line) 12%, transparent);
  }
  .confirm {
    color: var(--muted);
    font-size: var(--fs-2);
  }
  .transport {
    flex-shrink: 0;
    padding: var(--space-3) var(--space-4);
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-2);
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: var(--space-4);
    flex-wrap: wrap;
    box-shadow: var(--shadow-transport);
  }
  .listen {
    border: 0;
    display: flex;
    gap: var(--space-4);
    color: var(--muted);
  }
  .sr-audio {
    display: none;
  }
  .ghost {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 1px solid rgba(168, 184, 204, 0.4);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--text);
    cursor: pointer;
  }
  .danger {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 0;
    border-radius: var(--radius-1);
    background: var(--danger);
    color: #fff;
    cursor: pointer;
  }
  .banner {
    background: var(--surface-2);
    border-radius: var(--radius-2);
    padding: var(--space-4);
  }
  .banner.warn {
    border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
    color: var(--text);
  }
  .muted {
    color: var(--muted);
  }
</style>
