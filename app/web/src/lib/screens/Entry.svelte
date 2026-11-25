<script lang="ts">
  import { apiFetch, apiUpload, ApiError } from '../api';
  import {
    buildRequest,
    isYoutubeLink,
    readyForDetection,
    type ConvertCaps,
    type ConvertRequest,
    type EntryDraft,
  } from '../convertFlow';

  type Caps = ConvertCaps & {
    guitar_ft: boolean;
    lead_rhythm?: boolean;
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
    draft = $bindable(),
    onconvert,
  }: {
    draft: EntryDraft;
    onconvert: (request: ConvertRequest, caps: Caps | null) => Promise<void>;
  } = $props();

  let caps = $state<Caps | null>(null);
  let busy = $state<string | null>(null); // what we're doing right now, in words
  let error = $state<string | null>(null);
  let dragOver = $state(false);
  let fileInput: HTMLInputElement | undefined = $state();

  let linkOpen = $state(false);
  let linkValue = $state('');

  let ytOpen = $state(false);
  let ytQuery = $state('');
  let ytHits = $state<YtHit[]>([]);
  let ytPage = $state(1);
  let ytError = $state<string | null>(null);
  let ytBusy = $state(false);

  let blocked = $derived(Boolean(caps && !caps.ffmpeg));

  $effect(() => {
    void apiFetch<Caps>('/api/capabilities')
      .then((c) => {
        caps = c;
      })
      .catch(() => {
        caps = {
          ffmpeg: true,
          demucs: false,
          roformer: false,
          guitar_ft: false,
          lead_rhythm: false,
          max_upload_mb: 200,
        };
      });
  });

  /** Fill the draft for one source and go straight on to the instruments check. */
  async function go(source: Partial<EntryDraft>, doing: string) {
    error = null;
    if (blocked) {
      error = 'ffmpeg is required. Install it and restart the app.';
      return;
    }
    Object.assign(draft, readyForDetection({ ...draft, ...source }, caps));
    const request = buildRequest(draft);
    if ('error' in request) {
      error = request.error;
      return;
    }
    busy = doing;
    try {
      await onconvert(request, caps);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Could not start.';
    } finally {
      busy = null;
    }
  }

  async function uploadFile(file: File) {
    if (busy) return;
    error = null;
    busy = `Uploading ${file.name}…`;
    try {
      const res = await apiUpload(file);
      busy = null;
      await go(
        {
          sourceTab: 'upload',
          uploadId: res.upload_id,
          uploadName: res.name,
          uploadDuration: res.duration_sec,
          title: res.name.replace(/\.[^.]+$/, ''),
        },
        'Starting…',
      );
    } catch (err) {
      error = err instanceof Error ? err.message : 'Upload failed.';
      busy = null;
    } finally {
      if (fileInput) fileInput.value = '';
    }
  }

  function onFile(ev: Event) {
    const file = (ev.currentTarget as HTMLInputElement).files?.[0];
    if (file) void uploadFile(file);
  }

  function onDrop(ev: DragEvent) {
    ev.preventDefault();
    dragOver = false;
    const file = ev.dataTransfer?.files?.[0];
    if (file) void uploadFile(file);
  }

  async function searchYt() {
    if (!ytQuery.trim()) return;
    ytBusy = true;
    ytError = null;
    try {
      const res = await apiFetch<{ page: number; hits: YtHit[] }>('/api/youtube/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: ytQuery, page: ytPage }),
      });
      ytHits = res.hits;
      if (!res.hits.length) ytError = 'No results. Try other words.';
    } catch (err) {
      ytError = err instanceof ApiError ? err.message : 'Search failed.';
      ytHits = [];
    } finally {
      ytBusy = false;
    }
  }

  function pickYt(hit: YtHit) {
    ytOpen = false;
    void go(
      { sourceTab: 'youtube', youtubeUrl: hit.url, youtubeTitle: hit.title, title: hit.title },
      `Starting “${hit.title}”…`,
    );
  }

  function submitLink() {
    const url = linkValue.trim();
    if (!url) return;
    if (isYoutubeLink(url)) {
      void go({ sourceTab: 'youtube', youtubeUrl: url, youtubeTitle: '', title: '' }, 'Starting…');
    } else {
      void go({ sourceTab: 'url', mediaUrl: url, title: '' }, 'Starting…');
    }
  }
</script>

<section class="entry rise-in">
  <div class="promise">
    <h1>Turn a song into tabs.</h1>
    <p>Choose where your song comes from. We'll find the instruments in it next.</p>
  </div>

  {#if blocked}
    <p class="banner danger" role="alert">ffmpeg is missing. Install it and restart the app.</p>
  {/if}
  {#if error}
    <p class="banner danger" role="alert">{error}</p>
  {/if}

  <div class="choices" aria-busy={Boolean(busy)}>
    <button
      type="button"
      class="choice"
      class:drag={dragOver}
      disabled={Boolean(busy) || blocked}
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
      <span class="icon" aria-hidden="true">
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
      <span class="choice-title">Upload a file</span>
      <span class="choice-sub">From this device, or drop it here · MP3, WAV, M4A, FLAC</span>
    </button>

    <button
      type="button"
      class="choice"
      disabled={Boolean(busy) || blocked}
      onclick={() => {
        ytOpen = true;
        linkOpen = false;
      }}
    >
      <span class="icon" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <circle cx="10.5" cy="10.5" r="6" stroke="currentColor" stroke-width="1.75" />
          <path d="m15 15 5 5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          <path d="M9 8.3v4.4l3.6-2.2L9 8.3Z" fill="currentColor" />
        </svg>
      </span>
      <span class="choice-title">Search YouTube</span>
      <span class="choice-sub">Find a song by its name or artist</span>
    </button>

    <button
      type="button"
      class="choice"
      class:open={linkOpen}
      aria-expanded={linkOpen}
      disabled={Boolean(busy) || blocked}
      onclick={() => (linkOpen = !linkOpen)}
    >
      <span class="icon" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
          <path
            d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
      <span class="choice-title">Paste a link</span>
      <span class="choice-sub">A YouTube link or a direct link to an audio file</span>
    </button>
  </div>

  {#if linkOpen}
    <form
      class="link-form"
      onsubmit={(e) => {
        e.preventDefault();
        submitLink();
      }}
    >
      <label class="sr-only" for="link-input">Song link</label>
      <!-- svelte-ignore a11y_autofocus -->
      <input
        id="link-input"
        type="url"
        bind:value={linkValue}
        placeholder="https://…"
        autofocus
        disabled={Boolean(busy)}
      />
      <button type="submit" class="primary" disabled={!linkValue.trim() || Boolean(busy)}>
        Continue
      </button>
    </form>
  {/if}

  {#if busy}
    <p class="status" role="status"><span class="spinner is-on" aria-hidden="true"></span> {busy}</p>
  {/if}

  <input
    bind:this={fileInput}
    class="sr-only"
    type="file"
    accept=".mp3,.wav,.m4a,.flac,.ogg,.aac,audio/*"
    onchange={onFile}
  />
</section>

{#if ytOpen}
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="yt-title"
    tabindex="-1"
    onkeydown={(e) => {
      if (e.key === 'Escape') ytOpen = false;
    }}
  >
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
        <!-- svelte-ignore a11y_autofocus -->
        <input
          type="search"
          bind:value={ytQuery}
          placeholder="Song or artist"
          aria-label="Song or artist"
          autofocus
        />
        <button type="submit" class="primary compact" disabled={ytBusy || !ytQuery.trim()}>
          {#if ytBusy}<span class="spinner is-on" aria-hidden="true"></span>{/if}
          Search
        </button>
      </form>
      {#if ytError}<p class="banner danger" role="alert">{ytError}</p>{/if}
      {#if ytHits.length}
        <ul class="yt-hits">
          {#each ytHits as hit (hit.video_id)}
            <li>
              <span class="yt-hit-text" title={hit.title}
                >{hit.title}<small>{hit.channel} · {hit.duration_label}</small></span
              >
              <button type="button" class="pick" onclick={() => pickYt(hit)}>Choose</button>
            </li>
          {/each}
        </ul>
      {/if}
      <div class="yt-nav">
        {#if ytHits.length}
          <button
            type="button"
            class="ghost"
            disabled={ytPage <= 1 || ytBusy}
            onclick={() => {
              ytPage -= 1;
              void searchYt();
            }}>Previous</button
          >
          <button
            type="button"
            class="ghost"
            disabled={ytBusy || ytHits.length < 5}
            onclick={() => {
              ytPage += 1;
              void searchYt();
            }}>More results</button
          >
        {/if}
        <button type="button" class="ghost close" onclick={() => (ytOpen = false)}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .entry {
    width: 100%;
  }

  .promise {
    max-width: 40ch;
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

  .choices {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-4);
  }

  .choice {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
    min-height: 176px;
    padding: var(--space-6);
    border: 1.5px solid color-mix(in srgb, var(--line) 18%, transparent);
    border-radius: var(--radius-3);
    background: var(--surface);
    color: var(--text);
    text-align: left;
    cursor: pointer;
    transition:
      border-color var(--motion),
      background var(--motion),
      transform var(--motion);
  }

  .choice:hover:not(:disabled),
  .choice.drag,
  .choice.open {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 7%, var(--surface));
  }

  .choice:active:not(:disabled) {
    transform: translateY(1px);
  }

  .choice:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 52px;
    height: 52px;
    margin-bottom: var(--space-2);
    border-radius: var(--radius-2);
    background: color-mix(in srgb, var(--accent) 14%, var(--art));
    color: var(--accent);
  }

  .choice-title {
    font-size: var(--fs-4);
    line-height: var(--lh-4);
    font-weight: var(--weight-semibold);
  }

  .choice-sub {
    color: var(--muted);
    font-size: var(--fs-2);
    line-height: var(--lh-2);
  }

  .link-form {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }

  .link-form input {
    flex: 1;
    min-width: 0;
  }

  .status {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-4);
    color: var(--text-secondary);
  }

  input[type='url'],
  input[type='search'] {
    min-height: 48px;
    padding: 0 var(--space-3);
    border: 1px solid color-mix(in srgb, var(--line) 28%, transparent);
    border-radius: var(--radius-1);
    background: var(--art);
    transition: border-color var(--motion);
  }

  input:hover {
    border-color: color-mix(in srgb, var(--line) 55%, transparent);
  }

  input:focus {
    border-color: var(--accent);
    outline: none;
  }

  .primary {
    min-height: 48px;
    padding: 0 var(--space-6);
    border: 0;
    border-radius: var(--radius-2);
    background: var(--accent);
    color: var(--accent-ink);
    font-size: var(--fs-3);
    font-weight: var(--weight-semibold);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    transition: filter var(--motion);
  }

  .primary:hover:not(:disabled) {
    filter: brightness(1.05);
  }

  .primary:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .primary.compact {
    min-height: 48px;
  }

  .ghost,
  .pick {
    min-height: 40px;
    padding: 0 var(--space-3);
    border: 1px solid color-mix(in srgb, var(--line) 35%, transparent);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--text);
    font-size: var(--fs-2);
    cursor: pointer;
  }

  .ghost:hover:not(:disabled),
  .pick:hover {
    background: color-mix(in srgb, var(--surface-2) 50%, transparent);
  }

  .ghost:disabled {
    opacity: 0.45;
    cursor: default;
  }

  .pick {
    flex: 0 0 auto;
    border-color: var(--accent);
    color: var(--accent);
    font-weight: var(--weight-semibold);
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
    min-width: 0;
    max-height: calc(100dvh - 2 * var(--space-6));
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
    min-width: 0;
  }

  .yt-hits {
    list-style: none;
    padding: 0;
    max-height: min(44vh, 360px);
    overflow-y: auto;
    overflow-x: hidden;
  }

  .yt-hits li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) 0;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 22%, transparent);
  }

  .yt-hit-text {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .yt-hits small {
    display: block;
    color: var(--muted);
  }

  .yt-nav {
    display: flex;
    gap: var(--space-2);
  }

  .yt-nav .close {
    margin-left: auto;
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

  @media (max-width: 760px) {
    .choices {
      grid-template-columns: 1fr;
    }
    .choice {
      min-height: 0;
      padding: var(--space-4);
    }
  }
</style>
