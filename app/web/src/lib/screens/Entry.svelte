<script lang="ts">
  import { apiFetch, apiUpload, ApiError } from '../api';

  type Caps = {
    ffmpeg: boolean;
    demucs: boolean;
    roformer: boolean;
    guitar_ft: boolean;
    max_upload_mb: number;
  };

  type YtHit = {
    video_id: string;
    title: string;
    channel: string;
    duration_sec: number | null;
    duration_label: string;
    url: string;
    thumbnail_url: string;
  };

  let {
    onjob,
  }: {
    onjob: (jobId: string) => void;
  } = $props();

  let sourceTab = $state<'upload' | 'youtube' | 'url'>('upload');
  let title = $state('');
  let tuning = $state('Standard (EADGBE)');
  let capo = $state(0);
  let preset = $state<'solo' | 'full_mix'>('solo');
  let fingering = $state('playable');
  let showAdvanced = $state(false);
  let saferLength = $state(true);
  let maxDuration = $state(90);
  let fullTrackConfirm = $state(false);
  let separateStems = $state(false);
  let guitarEngine = $state('htdemucs_6s');
  let mixAware = $state(false);
  let onset = $state(0.5);
  let frame = $state(0.3);
  let tempoOverride = $state(0);

  let uploadId = $state<string | null>(null);
  let uploadName = $state('');
  let uploadDuration = $state(0);
  let youtubeUrl = $state('');
  let youtubeTitle = $state('');
  let mediaUrl = $state('');

  let caps = $state<Caps | null>(null);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let dragOver = $state(false);
  let fileInput: HTMLInputElement | undefined = $state();

  let ytOpen = $state(false);
  let ytQuery = $state('');
  let ytHits = $state<YtHit[]>([]);
  let ytPage = $state(1);
  let ytError = $state<string | null>(null);
  let ytBusy = $state(false);

  let summary = $derived.by(() => {
    const length = saferLength ? `First ${maxDuration} s` : 'Full track';
    const stems = separateStems ? 'stem separation on' : 'no stem separation';
    return `${length} · ${stems}`;
  });

  let canConvert = $derived.by(() => {
    if (busy) return false;
    if (caps && !caps.ffmpeg) return false;
    if (sourceTab === 'upload') return Boolean(uploadId);
    if (sourceTab === 'youtube') return Boolean(youtubeUrl.trim());
    return Boolean(mediaUrl.trim());
  });

  $effect(() => {
    void apiFetch<Caps>('/api/capabilities')
      .then((c) => (caps = c))
      .catch(() => {
        caps = { ffmpeg: true, demucs: false, roformer: false, guitar_ft: false, max_upload_mb: 200 };
      });
  });

  $effect(() => {
    separateStems = preset === 'full_mix';
    mixAware = preset === 'full_mix';
  });

  async function uploadFile(file: File) {
    busy = true;
    error = null;
    try {
      const res = await apiUpload(file);
      uploadId = res.upload_id;
      uploadName = res.name;
      uploadDuration = res.duration_sec;
      if (!title.trim()) title = res.name.replace(/\.[^.]+$/, '');
      sourceTab = 'upload';
    } catch (err) {
      error = err instanceof Error ? err.message : 'Upload failed.';
    } finally {
      busy = false;
    }
  }

  async function onFile(ev: Event) {
    const input = ev.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    await uploadFile(file);
  }

  function onDrop(ev: DragEvent) {
    ev.preventDefault();
    dragOver = false;
    const file = ev.dataTransfer?.files?.[0];
    if (file) void uploadFile(file);
  }

  async function searchYt() {
    ytBusy = true;
    ytError = null;
    try {
      const res = await apiFetch<{ page: number; hits: YtHit[] }>('/api/youtube/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: ytQuery, page: ytPage }),
      });
      ytHits = res.hits;
    } catch (err) {
      ytError = err instanceof ApiError ? err.message : 'Search failed.';
      ytHits = [];
    } finally {
      ytBusy = false;
    }
  }

  function pickYt(hit: YtHit) {
    youtubeUrl = hit.url;
    youtubeTitle = hit.title;
    if (!title.trim()) title = hit.title;
    sourceTab = 'youtube';
    ytOpen = false;
  }

  function clearUpload() {
    uploadId = null;
    uploadName = '';
    uploadDuration = 0;
    if (fileInput) fileInput.value = '';
  }

  async function convert() {
    error = null;
    if (caps && !caps.ffmpeg) {
      error = 'ffmpeg is required. Install it and restart.';
      return;
    }
    if (!saferLength && !fullTrackConfirm) {
      error = 'Confirm full-track conversion or enable Safer length.';
      return;
    }
    let source: Record<string, unknown>;
    if (sourceTab === 'upload') {
      if (!uploadId) {
        error = 'Choose an audio file.';
        return;
      }
      source = { kind: 'upload', upload_id: uploadId };
    } else if (sourceTab === 'youtube') {
      if (!youtubeUrl.trim()) {
        error = 'Search YouTube or paste a link.';
        return;
      }
      source = { kind: 'youtube', youtube_url: youtubeUrl.trim() };
    } else {
      if (!mediaUrl.trim()) {
        error = 'Paste a media URL.';
        return;
      }
      source = { kind: 'media_url', media_url: mediaUrl.trim() };
    }

    const config: Record<string, unknown> = {
      tuning_name: tuning,
      capo,
      fingering_preference: fingering,
      separate_stems: separateStems,
      mix_aware_filtering: mixAware,
      onset_threshold: onset,
      frame_threshold: frame,
      model: guitarEngine,
    };
    if (saferLength) config.max_duration_sec = maxDuration;
    if (tempoOverride > 0) config.tempo_bpm_override = tempoOverride;

    busy = true;
    try {
      const res = await apiFetch<{ job_id: string }>('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source,
          title: title.trim() || 'Guitar Tab',
          preset,
          config,
        }),
      });
      onjob(res.job_id);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Could not start conversion.';
    } finally {
      busy = false;
    }
  }
</script>

<section class="entry rise-in">
  <div class="promise">
    <h1>Turn a recording into guitar tab.</h1>
    <p>Drop an audio file or paste a YouTube link. You get tab, chords, and a practice player.</p>
  </div>

  {#if caps && !caps.ffmpeg}
    <p class="banner danger" role="alert">ffmpeg is missing — Convert stays disabled until it is on PATH.</p>
  {/if}
  {#if error}
    <p class="banner danger" role="alert">{error}</p>
  {/if}

  <div class="card">
    <div class="tabs" role="tablist" aria-label="Source">
      <button type="button" role="tab" aria-selected={sourceTab === 'upload'} class:active={sourceTab === 'upload'} onclick={() => (sourceTab = 'upload')}>File</button>
      <button type="button" role="tab" aria-selected={sourceTab === 'youtube'} class:active={sourceTab === 'youtube'} onclick={() => (sourceTab = 'youtube')}>YouTube</button>
      <button type="button" role="tab" aria-selected={sourceTab === 'url'} class:active={sourceTab === 'url'} onclick={() => (sourceTab = 'url')}>Media URL</button>
    </div>

    {#if sourceTab === 'upload'}
      {#if uploadName}
        <div class="source-chip">
          <div class="source-chip-body">
            <span class="source-chip-label">Ready</span>
            <strong>{uploadName}</strong>
            {#if uploadDuration}
              <span class="meta">{Math.round(uploadDuration)} s</span>
            {/if}
          </div>
          <div class="source-chip-actions">
            <button type="button" class="ghost" onclick={() => fileInput?.click()}>Change</button>
            <button type="button" class="ghost" onclick={clearUpload}>Remove</button>
          </div>
        </div>
      {:else}
        <button
          type="button"
          class="dropzone"
          class:drag={dragOver}
          disabled={busy}
          ondragenter={(e) => {
            e.preventDefault();
            dragOver = true;
          }}
          ondragover={(e) => {
            e.preventDefault();
            dragOver = true;
          }}
          ondragleave={() => (dragOver = false)}
          ondrop={onDrop}
          onclick={() => fileInput?.click()}
        >
          <span class="drop-icon" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 16V4m0 0 4 4m-4-4-4 4M4 16.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </span>
          <span class="drop-title">Drop an audio file here</span>
          <span class="drop-sub">or click to browse · MP3, WAV, M4A, FLAC · up to {caps?.max_upload_mb ?? 200} MB</span>
        </button>
      {/if}
      <input
        bind:this={fileInput}
        class="sr-only"
        type="file"
        accept=".mp3,.wav,.m4a,.flac,audio/*"
        onchange={onFile}
      />
    {:else if sourceTab === 'youtube'}
      {#if youtubeUrl}
        <div class="source-chip">
          <div class="source-chip-body">
            <span class="source-chip-label">YouTube</span>
            <strong>{youtubeTitle || youtubeUrl}</strong>
          </div>
          <div class="source-chip-actions">
            <button type="button" class="ghost" onclick={() => (ytOpen = true)}>Change</button>
            <button
              type="button"
              class="ghost"
              onclick={() => {
                youtubeUrl = '';
                youtubeTitle = '';
              }}>Remove</button
            >
          </div>
        </div>
      {:else}
        <div class="source-panel">
          <button type="button" class="cta-secondary" onclick={() => (ytOpen = true)}>Search YouTube</button>
          <label class="field grow">
            <span>Or paste a YouTube URL</span>
            <input type="url" bind:value={youtubeUrl} placeholder="https://youtube.com/…" />
          </label>
        </div>
      {/if}
    {:else}
      <label class="field">
        <span>Direct media URL</span>
        <input type="url" bind:value={mediaUrl} placeholder="https://…" />
      </label>
    {/if}

    <div class="setup">
      <label class="field wide">
        <span>Title</span>
        <input type="text" bind:value={title} placeholder="Song title" />
      </label>
      <label class="field">
        <span>Tuning</span>
        <select bind:value={tuning}>
          <option>Standard (EADGBE)</option>
          <option>Drop D</option>
          <option>Half-step down</option>
        </select>
      </label>
      <label class="field capo">
        <span>Capo</span>
        <input type="number" min="0" max="12" bind:value={capo} />
      </label>
      <label class="field">
        <span>Fingering</span>
        <select bind:value={fingering}>
          <option value="playable">Playable</option>
          <option value="low_fret">Low fret</option>
          <option value="position">Position</option>
        </select>
      </label>
      <div class="field wide">
        <span id="preset-label">Preset</span>
        <div class="segment" role="group" aria-labelledby="preset-label">
          <button type="button" class:active={preset === 'solo'} onclick={() => (preset = 'solo')}>Solo guitar</button>
          <button type="button" class:active={preset === 'full_mix'} onclick={() => (preset = 'full_mix')}>Full mix</button>
        </div>
      </div>
    </div>

    <button type="button" class="advanced-toggle" onclick={() => (showAdvanced = !showAdvanced)}>
      <span>{showAdvanced ? 'Hide advanced' : 'Advanced'}</span>
      <span class="chev" class:open={showAdvanced} aria-hidden="true">▾</span>
    </button>

    {#if showAdvanced}
      <div class="advanced">
        <label class="check"
          ><input type="checkbox" bind:checked={saferLength} /> Safer length (clip to max duration)</label
        >
        <label class="field">
          <span>Max duration (s)</span>
          <input type="number" min="15" max="300" bind:value={maxDuration} disabled={!saferLength} />
        </label>
        {#if !saferLength}
          <label class="check"
            ><input type="checkbox" bind:checked={fullTrackConfirm} /> I confirm full-track conversion</label
          >
        {/if}
        <label class="check">
          <input
            type="checkbox"
            bind:checked={separateStems}
            disabled={caps !== null && !caps.demucs && !caps.roformer}
          />
          Separate guitar stem
        </label>
        <label class="field">
          <span>Guitar engine</span>
          <select bind:value={guitarEngine}>
            <option value="htdemucs_6s">Demucs 6s</option>
            <option value="bs_roformer_sw">RoFormer</option>
            <option value="melband_roformer_guitar">RoFormer + refine</option>
            <option value="lead_rhythm_split">Lead + Rhythm</option>
          </select>
        </label>
        <label class="check"><input type="checkbox" bind:checked={mixAware} /> Mix-aware filtering</label>
        <div class="advanced-grid">
          <label class="field"
            ><span>Onset threshold</span>
            <input type="number" min="0" max="1" step="0.05" bind:value={onset} /></label
          >
          <label class="field"
            ><span>Frame threshold</span>
            <input type="number" min="0" max="1" step="0.05" bind:value={frame} /></label
          >
          <label class="field"
            ><span>Tempo override (BPM, 0 = auto)</span>
            <input type="number" min="0" max="300" bind:value={tempoOverride} /></label
          >
        </div>
      </div>
    {/if}

    <div class="footer">
      <p class="summary">
        {summary}
        <button type="button" class="linkish" onclick={() => (showAdvanced = true)}>Change</button>
      </p>
      <button type="button" class="primary" disabled={!canConvert} onclick={convert}>
        {#if busy}<span class="spinner is-on" aria-hidden="true"></span>{/if}
        Convert
      </button>
    </div>
  </div>
</section>

{#if ytOpen}
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="yt-title">
    <div class="modal-card">
      <h2 id="yt-title">Search YouTube</h2>
      <form
        class="yt-form"
        onsubmit={(e) => {
          e.preventDefault();
          ytPage = 1;
          void searchYt();
        }}
      >
        <input type="search" bind:value={ytQuery} placeholder="Song or artist" />
        <button type="submit" class="primary compact" disabled={ytBusy}>Search</button>
      </form>
      {#if ytError}<p class="banner danger" role="alert">{ytError}</p>{/if}
      <ul class="yt-hits">
        {#each ytHits as hit (hit.video_id)}
          <li>
            <span>{hit.title}<small>{hit.channel} · {hit.duration_label}</small></span>
            <button type="button" class="ghost" onclick={() => pickYt(hit)}>Use</button>
          </li>
        {/each}
      </ul>
      <div class="yt-nav">
        <button
          type="button"
          class="ghost"
          disabled={ytPage <= 1 || ytBusy}
          onclick={() => {
            ytPage -= 1;
            void searchYt();
          }}>Prev</button
        >
        <button
          type="button"
          class="ghost"
          disabled={ytBusy || ytHits.length < 5}
          onclick={() => {
            ytPage += 1;
            void searchYt();
          }}>Next</button
        >
        <button type="button" class="ghost" onclick={() => (ytOpen = false)}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .entry {
    width: 100%;
  }

  .promise {
    text-align: left;
    max-width: 42ch;
    margin: 0 0 var(--space-8);
  }

  .promise h1 {
    font-size: var(--fs-6);
    line-height: var(--lh-6);
    font-weight: var(--weight-semibold);
    letter-spacing: -0.025em;
    margin-bottom: var(--space-3);
  }

  .promise p {
    color: var(--muted);
    font-size: var(--fs-3);
    line-height: var(--lh-4);
  }

  .card {
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-6);
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .tabs {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-1);
    padding: var(--space-1);
    background: var(--art);
    border-radius: var(--radius-2);
  }

  .tabs button {
    min-height: 44px;
    border: 0;
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    font-weight: var(--weight-medium);
    cursor: pointer;
    transition:
      background var(--motion),
      color var(--motion);
  }

  .tabs button:hover {
    color: var(--text);
  }

  .tabs button.active {
    color: var(--accent-ink);
    background: var(--accent);
    font-weight: var(--weight-semibold);
  }

  .dropzone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    min-height: 168px;
    padding: var(--space-8);
    border: 1.5px dashed color-mix(in srgb, var(--line) 45%, transparent);
    border-radius: var(--radius-2);
    background: color-mix(in srgb, var(--art) 70%, var(--surface));
    color: var(--text);
    cursor: pointer;
    text-align: center;
    transition:
      border-color var(--motion),
      background var(--motion);
  }

  .dropzone:hover,
  .dropzone.drag {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 8%, var(--art));
  }

  .dropzone:disabled {
    opacity: 0.6;
    cursor: wait;
  }

  .drop-icon {
    color: var(--accent);
    margin-bottom: var(--space-1);
  }

  .drop-title {
    font-size: var(--fs-4);
    font-weight: var(--weight-semibold);
  }

  .drop-sub {
    color: var(--muted);
    font-size: var(--fs-2);
  }

  .source-chip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-4);
    border-radius: var(--radius-2);
    background: var(--art);
  }

  .source-chip-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .source-chip-label {
    font-size: var(--fs-1);
    color: var(--accent);
    font-weight: var(--weight-medium);
  }

  .source-chip strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .source-chip .meta,
  .source-chip-actions {
    color: var(--muted);
    font-size: var(--fs-2);
  }

  .source-chip-actions {
    display: flex;
    gap: var(--space-2);
    flex-shrink: 0;
  }

  .source-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .cta-secondary {
    min-height: 48px;
    border: 0;
    border-radius: var(--radius-2);
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
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
    font-weight: var(--weight-medium);
  }

  .field.grow {
    width: 100%;
  }

  input[type='text'],
  input[type='url'],
  input[type='number'],
  input[type='search'],
  select {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 1px solid color-mix(in srgb, var(--line) 28%, transparent);
    border-radius: var(--radius-1);
    background: var(--art);
    transition: border-color var(--motion);
  }

  input:hover,
  select:hover {
    border-color: color-mix(in srgb, var(--line) 55%, transparent);
  }

  input:focus,
  select:focus {
    border-color: var(--accent);
    outline: none;
  }

  input:disabled,
  select:disabled {
    opacity: 0.5;
  }

  .setup {
    display: grid;
    gap: var(--space-4);
    grid-template-columns: 1.4fr 0.55fr 1fr;
  }

  .setup .wide {
    grid-column: 1 / -1;
  }

  .setup .capo input {
    max-width: 88px;
  }

  .segment button.active {
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
  }

  .segment {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2px;
    padding: 2px;
    background: var(--art);
    border-radius: var(--radius-1);
    min-height: 44px;
  }

  .segment button {
    border: 0;
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    font-size: var(--fs-2);
    font-weight: var(--weight-medium);
    cursor: pointer;
  }


  .advanced-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 1px solid color-mix(in srgb, var(--line) 28%, transparent);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .chev {
    transition: transform var(--motion);
  }

  .chev.open {
    transform: rotate(180deg);
  }

  .advanced {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4);
    background: var(--art);
    border-radius: var(--radius-2);
  }

  .advanced-grid {
    display: grid;
    gap: var(--space-3);
    grid-template-columns: repeat(3, 1fr);
  }

  .check {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-height: 44px;
    color: var(--text-secondary);
  }

  .check input {
    width: 18px;
    height: 18px;
    accent-color: var(--accent);
  }

  .footer {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }

  .summary {
    color: var(--muted);
    font-size: var(--fs-2);
    text-align: center;
  }

  .linkish {
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-weight: var(--weight-medium);
    cursor: pointer;
    padding: 0;
    margin-left: var(--space-1);
  }

  .primary {
    min-height: 52px;
    width: 100%;
    padding: 0 var(--space-6);
    border: 0;
    border-radius: var(--radius-2);
    background: var(--accent);
    color: var(--accent-ink);
    font-size: var(--fs-4);
    font-weight: var(--weight-semibold);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    transition:
      filter var(--motion),
      transform var(--motion);
  }

  .primary:hover:not(:disabled) {
    filter: brightness(1.05);
  }

  .primary:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .primary.compact {
    width: auto;
    min-height: 44px;
    font-size: var(--fs-3);
  }

  .ghost {
    min-height: 36px;
    padding: 0 var(--space-3);
    border: 1px solid color-mix(in srgb, var(--line) 35%, transparent);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--text);
    font-size: var(--fs-2);
    cursor: pointer;
  }

  .ghost:hover {
    background: color-mix(in srgb, var(--surface-2) 50%, transparent);
  }

  .banner {
    border-radius: var(--radius-2);
    padding: var(--space-4);
    margin-bottom: var(--space-4);
    background: var(--surface);
  }

  .banner.danger {
    border: 1px solid color-mix(in srgb, var(--danger) 45%, transparent);
    color: #ffc9c6;
  }

  .modal {
    position: fixed;
    inset: 0;
    background: rgba(15, 20, 35, 0.72);
    display: grid;
    place-items: center;
    z-index: 40;
    padding: var(--space-6);
  }

  .modal-card {
    width: min(560px, 100%);
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-3);
    padding: var(--space-6);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .modal-card h2 {
    font-size: var(--fs-5);
    font-weight: var(--weight-semibold);
  }

  .yt-form {
    display: flex;
    gap: var(--space-2);
  }

  .yt-form input {
    flex: 1;
  }

  .yt-hits {
    list-style: none;
    padding: 0;
    max-height: 280px;
    overflow: auto;
  }

  .yt-hits li {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) 0;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 22%, transparent);
  }

  .yt-hits small {
    display: block;
    color: var(--muted);
  }

  .yt-nav {
    display: flex;
    gap: var(--space-2);
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  @media (max-width: 960px) {
    .setup,
    .advanced-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
