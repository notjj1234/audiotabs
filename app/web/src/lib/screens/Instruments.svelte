<script lang="ts">
  import { onMount } from 'svelte';

  import { apiFetch, ApiError } from '../api';
  import {
    checkedLengthText,
    withTabOptions,
    type ConvertRequest,
    type TabOptions,
  } from '../convertFlow';
  import {
    canStart,
    defaultSelection,
    isLocked,
    isMainRow,
    kindHint,
    shortReason,
    startLabel,
    toggle,
    type InventoryRow,
  } from '../partsSelection';

  type Snap = {
    state: string;
    title: string;
    inventory: InventoryRow[] | null;
    lead_rhythm: { ok: boolean; reason: string | null } | null;
  };

  let {
    analysisId,
    request,
    options = $bindable(),
    onstart,
    onback,
    onexpired,
    onfullsong,
  }: {
    analysisId: string;
    request: ConvertRequest;
    options: TabOptions;
    onstart: (jobId: string) => void;
    onback: () => void;
    onexpired: (message: string) => void;
    /** Check the whole song instead of its first part (runs the check again). */
    onfullsong: () => Promise<void>;
  } = $props();

  let inventory = $state<InventoryRow[]>([]);
  let songTitle = $state('');
  let splitNote = $state<string | null>(null);
  let selected = $state<string[]>([]);
  let loading = $state(true);
  let starting = $state(false);
  let rechecking = $state(false);
  let error = $state<string | null>(null);
  let settingsOpen = $state(false);

  let main = $derived(inventory.filter(isMainRow));
  let notFound = $derived(inventory.filter((r) => !isMainRow(r)));
  let foundCount = $derived(inventory.filter((r) => r.detected).length);
  let lengthText = $derived(checkedLengthText(request));

  onMount(async () => {
    try {
      const snap = await apiFetch<Snap>(`/api/analyses/${encodeURIComponent(analysisId)}`);
      inventory = snap.inventory ?? [];
      songTitle = snap.title;
      if (snap.lead_rhythm && !snap.lead_rhythm.ok && snap.lead_rhythm.reason) {
        splitNote = snap.lead_rhythm.reason;
      }
      selected = defaultSelection(inventory);
    } catch (err) {
      onexpired(err instanceof Error ? err.message : 'The instrument check is no longer available.');
    } finally {
      loading = false;
    }
  });

  async function start() {
    if (!canStart(selected) || starting) return;
    starting = true;
    error = null;
    try {
      const body = { ...withTabOptions(request, options), analysis_id: analysisId, parts: selected };
      const res = await apiFetch<{ job_id: string }>('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      onstart(res.job_id);
    } catch (err) {
      if (
        err instanceof ApiError &&
        (err.code === 'analysis_missing' || err.code === 'analysis_mismatch')
      ) {
        onexpired(err.message);
        return;
      }
      error = err instanceof Error ? err.message : 'Could not start making the tabs.';
    } finally {
      starting = false;
    }
  }

  async function fullSong() {
    rechecking = true;
    error = null;
    try {
      await onfullsong();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Could not check the whole song.';
      rechecking = false;
    }
  }
</script>

{#snippet icon(id: string)}
  <svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true">
    {#if id === 'lead' || id === 'rhythm' || id === 'combined'}
      <!-- guitar body + neck -->
      <path
        d="M19.5 12.5 26 6m-2-2 4 4M14.6 13.2c-1.6-1.6-4.6-1.3-6.4.6-1.1 1.1-1.3 2.4-1 3.4-1.6.2-2.9.9-3.6 2-1.6 2.5-.6 6 2.2 7.8 2.4 1.5 5.3 1.1 6.7-.9.6-.9.9-2 .8-3.2 1 .3 2.3.1 3.4-1 1.9-1.8 2.2-4.8.6-6.4l-2.7-2.3Z"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linejoin="round"
      />
      <circle cx="11.5" cy="20.5" r="1.6" fill="currentColor" />
      {#if id === 'lead'}
        <path d="M25 17.5v4M23 19.5h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
      {:else if id === 'rhythm'}
        <path d="M23 18h5M23 21h5M23 24h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
      {:else}
        <path d="M23 19h5M25.5 16.5v5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity="0.6" />
      {/if}
    {:else if id === 'bass'}
      <path
        d="M17.5 14.5 28 4m-2-2 4 4M13.2 15.8c-1.5-1.5-4-1.4-5.6.3-.9.9-1.2 2-1 3-1.5.3-2.7 1-3.3 2.1-1.4 2.4-.4 5.6 2.2 7.1 2.2 1.3 4.9.9 6.1-.9.5-.8.8-1.8.7-2.8.9.2 2-.1 2.9-1 1.7-1.6 1.9-4.2.5-5.7l-2.5-2.1Z"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linejoin="round"
      />
      <path d="M8.5 24.5l4-4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
    {:else if id === 'vocals'}
      <rect x="11.5" y="3.5" width="9" height="15" rx="4.5" stroke="currentColor" stroke-width="1.6" />
      <path
        d="M7.5 14.5a8.5 8.5 0 0 0 17 0M16 23v5m-4.5 0h9"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
      />
    {:else if id === 'keys'}
      <rect x="3.5" y="7.5" width="25" height="17" rx="2" stroke="currentColor" stroke-width="1.6" />
      <path d="M9.75 7.5v17M16 7.5v17M22.25 7.5v17" stroke="currentColor" stroke-width="1.4" />
      <path
        d="M7.6 7.5h3.2v9H7.6zM14.4 7.5h3.2v9h-3.2zM20.6 7.5h3.2v9h-3.2z"
        fill="currentColor"
      />
    {:else if id === 'drums'}
      <ellipse cx="16" cy="13" rx="11" ry="4.5" stroke="currentColor" stroke-width="1.6" />
      <path
        d="M5 13v8c0 2.5 4.9 4.5 11 4.5s11-2 11-4.5v-8M9 3.5l5 8m9-8-5 8"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
      />
    {:else}
      <path
        d="M3.5 16h3l2.5-6 4 13 4-17 4 15 2.5-5h5"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    {/if}
  </svg>
{/snippet}

{#snippet tile(row: InventoryRow)}
  {@const on = selected.includes(row.id)}
  {@const locked = isLocked(row.id, selected)}
  {@const tileNote = locked ? 'Untick Lead and Rhythm to pick this.' : row.note}
  <li>
    <button
      type="button"
      class="tile"
      class:on
      class:quiet={!row.detected}
      role="checkbox"
      aria-checked={on}
      aria-describedby="tile-meta-{row.id}"
      disabled={!row.tabbable || locked}
      onclick={() => (selected = toggle(selected, row.id, inventory))}
    >
      <span class="tick" aria-hidden="true">
        {#if on}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="m5 12.5 4.5 4.5L19 7.5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        {/if}
      </span>
      <span class="art">{@render icon(row.id)}</span>
      <span class="name">{row.label}</span>
      <span class="meta" id="tile-meta-{row.id}">
        {shortReason(row)} · {kindHint(row)}
      </span>
      {#if tileNote}<span class="tile-note">{tileNote}</span>{/if}
    </button>
  </li>
{/snippet}

<section class="instruments rise-in" aria-busy={loading}>
  <h1>Instruments in this song</h1>
  {#if songTitle}<p class="subtitle">{songTitle}</p>{/if}

  {#if loading}
    <p class="loading" role="status"><span class="spinner is-on" aria-hidden="true"></span> Loading…</p>
  {:else}
    <p class="lead-in">
      {#if foundCount}
        We found {foundCount} {foundCount === 1 ? 'instrument' : 'instruments'}. Tap one to leave it
        out.
      {:else}
        We couldn't clearly hear any instrument. You can still pick one below.
      {/if}
    </p>

    {#if main.length}
      <ul class="grid">
        {#each main as row (row.id)}{@render tile(row)}{/each}
      </ul>
    {/if}

    {#if splitNote}<p class="info" role="status">{splitNote}</p>{/if}

    {#if notFound.length}
      <details class="more" open={!foundCount}>
        <summary>Not found in this song ({notFound.length})</summary>
        <p class="more-hint">These were barely audible and may give few notes.</p>
        <ul class="grid">
          {#each notFound as row (row.id)}{@render tile(row)}{/each}
        </ul>
      </details>
    {/if}

    {#if lengthText}
      <p class="length">
        We listened to {lengthText} of the song.
        <button type="button" class="linkish" disabled={rechecking} onclick={fullSong}>
          {#if rechecking}<span class="spinner is-on" aria-hidden="true"></span>{/if}
          Use the whole song
        </button>
      </p>
    {/if}

    <details class="settings" bind:open={settingsOpen}>
      <summary>Tab settings</summary>
      <div class="settings-grid">
        <label class="field">
          <span>Tuning</span>
          <select bind:value={options.tuning}>
            <option>Standard (EADGBE)</option>
            <option>Drop D</option>
            <option>Half-step down</option>
          </select>
        </label>
        <label class="field">
          <span>Capo</span>
          <input type="number" min="0" max="12" bind:value={options.capo} />
        </label>
        <label class="field">
          <span>Fingering</span>
          <select bind:value={options.fingering}>
            <option value="playable">Easiest to play</option>
            <option value="low_fret">Near the nut</option>
            <option value="position">Stay in one position</option>
          </select>
        </label>
        <label class="field">
          <span>Tempo (BPM, 0 = detect)</span>
          <input type="number" min="0" max="300" bind:value={options.tempoOverride} />
        </label>
        <label class="check">
          <input type="checkbox" bind:checked={options.vocalDebleed} />
          Remove singing that leaks into guitar
        </label>
      </div>
    </details>

    {#if error}<p class="banner danger" role="alert">{error}</p>{/if}

    <div class="footer">
      <button type="button" class="ghost" onclick={onback}>Choose another song</button>
      <div class="go">
        <p class="hint" role="status">
          {#if !canStart(selected)}
            Pick at least one instrument.
          {/if}
        </p>
        <button
          type="button"
          class="primary"
          disabled={!canStart(selected) || starting || rechecking}
          onclick={start}
        >
          <span class="spinner" class:is-on={starting} aria-hidden="true"></span>
          {startLabel(selected.length)}
        </button>
      </div>
    </div>
  {/if}
</section>

<style>
  .instruments {
    width: 100%;
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-8);
  }
  h1 {
    font-size: var(--fs-5);
    font-weight: var(--weight-semibold);
    letter-spacing: -0.02em;
    margin-bottom: var(--space-1);
  }
  .subtitle {
    color: var(--text-secondary);
  }
  .loading {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--muted);
    margin-top: var(--space-6);
  }
  .lead-in {
    margin-top: var(--space-6);
    margin-bottom: var(--space-4);
    color: var(--text-secondary);
  }
  .grid {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
    gap: var(--space-3);
  }
  .tile {
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 148px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-1);
    padding: var(--space-4);
    border: 1.5px solid color-mix(in srgb, var(--line) 22%, transparent);
    border-radius: var(--radius-3);
    background: var(--art);
    color: var(--text);
    text-align: left;
    cursor: pointer;
    transition:
      border-color var(--motion),
      background var(--motion),
      opacity var(--motion);
  }
  .tile:hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--accent) 60%, transparent);
  }
  .tile.on {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, var(--art));
  }
  .tile:not(.on) {
    opacity: 0.78;
  }
  .tile:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }
  .tick {
    position: absolute;
    top: var(--space-3);
    right: var(--space-3);
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 1.5px solid color-mix(in srgb, var(--line) 45%, transparent);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--accent-ink);
  }
  .tile.on .tick {
    background: var(--accent);
    border-color: var(--accent);
  }
  .art {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 52px;
    height: 52px;
    margin-bottom: var(--space-2);
    border-radius: var(--radius-2);
    background: color-mix(in srgb, var(--accent) 14%, var(--surface));
    color: var(--accent);
  }
  .tile.quiet .art {
    background: var(--surface);
    color: var(--muted);
  }
  .name {
    font-weight: var(--weight-semibold);
    font-size: var(--fs-4);
    line-height: var(--lh-4);
  }
  .meta,
  .tile-note {
    color: var(--muted);
    font-size: var(--fs-1);
    line-height: var(--lh-1);
  }
  .tile-note {
    color: var(--text-secondary);
  }
  .info {
    margin-top: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
    border-radius: var(--radius-2);
    color: var(--text-secondary);
    font-size: var(--fs-2);
  }
  .more,
  .settings {
    margin-top: var(--space-6);
  }
  .more summary,
  .settings summary {
    min-height: 44px;
    display: flex;
    align-items: center;
    cursor: pointer;
    color: var(--text-secondary);
    font-weight: var(--weight-medium);
  }
  .more-hint {
    color: var(--muted);
    font-size: var(--fs-2);
    margin-bottom: var(--space-3);
  }
  .length {
    margin-top: var(--space-6);
    color: var(--muted);
    font-size: var(--fs-2);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .linkish {
    min-height: 32px;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-weight: var(--weight-semibold);
    cursor: pointer;
    padding: 0;
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
  }
  .linkish:disabled {
    opacity: 0.6;
    cursor: wait;
  }
  .settings-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--space-4);
    padding: var(--space-4);
    background: var(--art);
    border-radius: var(--radius-2);
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
  .field input,
  .field select {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 1px solid color-mix(in srgb, var(--line) 28%, transparent);
    border-radius: var(--radius-1);
    background: var(--surface);
    color: var(--text);
  }
  label.check {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-height: 44px;
    color: var(--text-secondary);
    grid-column: 1 / -1;
  }
  label.check input {
    width: 18px;
    height: 18px;
    accent-color: var(--accent);
  }
  .footer {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    justify-content: space-between;
    gap: var(--space-4);
    margin-top: var(--space-8);
  }
  .go {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-4);
    margin-left: auto;
  }
  .hint {
    color: var(--muted);
    font-size: var(--fs-2);
    max-width: 40ch;
    text-align: right;
  }
  .hint:empty {
    display: none;
  }
  .primary {
    min-height: 52px;
    padding: 0 var(--space-8);
    border: 0;
    border-radius: var(--radius-2);
    background: var(--accent);
    color: var(--accent-ink);
    font-size: var(--fs-4);
    font-weight: var(--weight-semibold);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    transition: filter var(--motion);
  }
  .primary:hover:not(:disabled) {
    filter: brightness(1.06);
  }
  .primary:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .ghost {
    min-height: 44px;
    padding: 0 var(--space-4);
    border: 1px solid color-mix(in srgb, var(--line) 35%, transparent);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--text);
    font-size: var(--fs-3);
    cursor: pointer;
  }
  .ghost:hover {
    background: color-mix(in srgb, var(--surface-2) 60%, transparent);
  }
  .banner {
    border-radius: var(--radius-2);
    padding: var(--space-4);
    margin-top: var(--space-6);
    background: var(--surface);
  }
  .banner.danger {
    border: 1px solid color-mix(in srgb, var(--danger) 45%, transparent);
    color: #ffc9c6;
  }
</style>
