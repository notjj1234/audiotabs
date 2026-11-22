<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import {
    apiFetch,
    downloadExport,
    fetchAudioObjectUrl,
  } from '../api';

  type Score = {
    view: string;
    svg: string;
    text: string;
    meta: {
      title: string;
      key: string;
      tempo_bpm: number;
      duration_sec: number;
      tuning_name: string;
      capo: number;
      transpose: number;
      bars_per_line: number;
      lyrics_status?: string;
    };
    artifacts: Record<string, boolean>;
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
  let listen = $state<'original' | 'stem'>('original');
  let audioSrc = $state<string | null>(null);
  let confirmNew = $state(false);
  let exportOpen = $state(false);

  async function loadScore() {
    try {
      const q = new URLSearchParams({
        view,
        tuning,
        capo: String(capo),
        transpose: String(transpose),
        bars: String(bars),
      });
      score = await apiFetch<Score>(`/api/runs/${encodeURIComponent(runId)}/score?${q}`);
      error = null;
      if (score.meta) {
        // Keep inspector in sync on first load only when still defaults? Always trust response meta for title.
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Could not load score.';
    }
  }

  async function loadAudio() {
    if (audioSrc) URL.revokeObjectURL(audioSrc);
    audioSrc = null;
    try {
      audioSrc = await fetchAudioObjectUrl(runId, listen);
    } catch {
      audioSrc = null;
    }
  }

  onMount(() => {
    void loadScore();
    void loadAudio();
  });

  onDestroy(() => {
    if (audioSrc) URL.revokeObjectURL(audioSrc);
  });

  $effect(() => {
    void view;
    void tuning;
    void capo;
    void transpose;
    void bars;
    void loadScore();
  });

  $effect(() => {
    void listen;
    void loadAudio();
  });

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

  <header class="top">
    <div>
      <h1>{score?.meta.title || 'Result'}</h1>
      {#if score}
        <p class="meta">
          Key {score.meta.key} · {Math.round(score.meta.tempo_bpm)} BPM ·
          {Math.floor(score.meta.duration_sec / 60)}:{String(Math.floor(score.meta.duration_sec % 60)).padStart(2, '0')}
        </p>
      {/if}
    </div>
    <div class="actions">
      <div class="export">
        <button type="button" class="ghost" onclick={() => (exportOpen = !exportOpen)}>Export</button>
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
        <span>Start over?</span>
        <button type="button" class="ghost" onclick={() => (confirmNew = false)}>Keep</button>
        <button type="button" class="danger" onclick={onnew}>Discard</button>
      {:else}
        <button type="button" class="ghost" onclick={() => (confirmNew = true)}>New song</button>
      {/if}
    </div>
  </header>

  <div class="layout">
    <div class="main">
      <div class="views" role="tablist" aria-label="Score view">
        {#each [['staff', 'Tab'], ['chords', 'Chords'], ['piano', 'Piano roll'], ['text', 'Text']] as [id, label]}
          <button
            type="button"
            class:active={view === id}
            onclick={() => (view = id)}>{label}</button
          >
        {/each}
      </div>

      <div class="score" role="img" aria-label="Score">
        {#if score?.svg}
          {@html score.svg}
        {/if}
        {#if score?.text}
          <pre>{score.text}</pre>
        {/if}
        {#if !score}
          <p class="muted"><span class="spinner is-on"></span> Loading score…</p>
        {/if}
      </div>

      <div class="feedback">
        <span>Does this sound right?</span>
        <button type="button" class="ghost" onclick={() => sendFeedback('yes')}>Yes</button>
        <button type="button" class="ghost" onclick={() => sendFeedback('no')}>Not quite</button>
      </div>
    </div>

    <aside class="inspector">
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
    </aside>
  </div>

  <div class="transport">
    <fieldset class="listen">
      <legend>Listen</legend>
      <label><input type="radio" bind:group={listen} value="original" /> Original</label>
      <label><input type="radio" bind:group={listen} value="stem" /> Guitar stem</label>
    </fieldset>
    {#if audioSrc}
      <audio controls src={audioSrc}></audio>
    {:else}
      <p class="muted">Audio not available for this source.</p>
    {/if}
  </div>
</section>

<style>
  .top {
    display: flex;
    justify-content: space-between;
    gap: var(--space-6);
    align-items: flex-start;
    margin-bottom: var(--space-6);
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
    margin-top: var(--space-2);
  }
  .actions {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
  }
  .export {
    position: relative;
  }
  .menu {
    position: absolute;
    right: 0;
    top: 100%;
    margin-top: var(--space-2);
    background: var(--surface);
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-2);
    display: flex;
    flex-direction: column;
    min-width: 140px;
    z-index: 5;
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
  .layout {
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: var(--space-6);
  }
  @media (max-width: 960px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }
  .views {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
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
  .score {
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-4);
    overflow-x: auto;
    min-height: 200px;
  }
  .score :global(svg) {
    max-width: none;
    height: auto;
  }
  pre {
    white-space: pre;
    font-family: var(--font-mono);
    font-size: var(--fs-2);
  }
  .feedback {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    margin-top: var(--space-4);
    color: var(--muted);
  }
  .inspector {
    width: 280px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    height: fit-content;
  }
  .inspector h2 {
    font-size: var(--fs-4);
    font-weight: var(--weight-medium);
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
  }
  .transport {
    margin-top: var(--space-8);
    padding: var(--space-4);
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-2);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    box-shadow: var(--shadow-transport);
  }
  .listen {
    border: 0;
    display: flex;
    gap: var(--space-4);
    color: var(--muted);
  }
  audio {
    width: 100%;
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
    margin-bottom: var(--space-4);
  }
  .muted {
    color: var(--muted);
  }
</style>
