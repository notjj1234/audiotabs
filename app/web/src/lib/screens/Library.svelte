<script lang="ts">
  import { onMount } from 'svelte';

  import { apiFetch } from '../api';

  export type Run = {
    id: string;
    title: string;
    created_at: number;
    artifacts: Record<string, boolean>;
    details: Record<string, unknown>;
    diagnostics?: Record<string, unknown> | null;
    feedback: Record<string, unknown> | null;
    source: Record<string, unknown> | null;
    config: Record<string, unknown> | null;
  };

  let {
    ontranscribe,
    onopen,
  }: {
    ontranscribe: () => void;
    onopen: (runId: string) => void;
  } = $props();

  let runs = $state<Run[] | null>(null);
  let loadError = $state<string | null>(null);
  let confirmId = $state<string | null>(null);
  let deleting = $state(false);

  async function load() {
    try {
      runs = await apiFetch<Run[]>('/api/runs');
      loadError = null;
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Could not load your runs.';
    }
  }

  onMount(() => {
    void load();
  });

  function formatDate(epochSeconds: number): string {
    return new Date(epochSeconds * 1000).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }

  async function confirmDelete(runId: string) {
    deleting = true;
    try {
      await apiFetch<{ deleted: boolean }>(`/api/runs/${encodeURIComponent(runId)}`, {
        method: 'DELETE',
      });
      confirmId = null;
      runs = (runs ?? []).filter((r) => r.id !== runId);
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Could not delete that run.';
    } finally {
      deleting = false;
    }
  }
</script>

<section class="rise-in" aria-labelledby="library-heading">
  <h1 id="library-heading">Library</h1>

  {#if loadError}
    <p class="banner" role="alert">{loadError}</p>
  {:else if runs === null}
    <p class="muted"><span class="spinner is-on" aria-hidden="true"></span> Loading…</p>
  {:else if runs.length === 0}
    <div class="empty">
      <p>Nothing transcribed yet.</p>
      <button type="button" class="primary" onclick={ontranscribe}>Transcribe something</button>
    </div>
  {:else}
    <ul class="rows">
      {#each runs as run (run.id)}
        <li class="row">
          <div class="meta">
            <span class="title">{run.title || 'Untitled run'}</span>
            {#if run.config?.model === 'lead_rhythm_split'}
              <span class="chip">Lead/Rhythm split</span>
            {/if}
            {#if Array.isArray(run.diagnostics?.warnings) && (run.diagnostics?.warnings?.length ?? 0) > 0}
              <span class="chip warn" title="Split quality warnings">
                <svg
                  class="warn-icon"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"
                    stroke="currentColor"
                    stroke-width="1.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                {run.diagnostics?.warnings?.length}
              </span>
            {/if}
            <span class="date">{formatDate(run.created_at)}</span>
          </div>
          <div class="actions">
            {#if confirmId === run.id}
              <span class="confirm-label">Delete this run?</span>
              <button type="button" class="ghost" disabled={deleting} onclick={() => (confirmId = null)}
                >Cancel</button
              >
              <button
                type="button"
                class="danger"
                disabled={deleting}
                onclick={() => confirmDelete(run.id)}>Delete</button
              >
            {:else}
              <button type="button" class="ghost" onclick={() => onopen(run.id)}>Open</button>
              <button type="button" class="ghost danger-text" onclick={() => (confirmId = run.id)}
                >Delete</button
              >
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  h1 {
    font-size: var(--fs-5);
    line-height: var(--lh-5);
    letter-spacing: -0.02em;
    font-weight: var(--weight-semibold);
    margin-bottom: var(--space-6);
    text-align: center;
  }

  .muted {
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
  }

  .banner {
    color: var(--text);
    background: var(--surface-2);
    border: 1px solid color-mix(in srgb, var(--line) 28%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-4);
    text-align: center;
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: var(--space-4);
    color: var(--muted);
  }

  .primary {
    min-height: 44px;
    padding: 0 var(--space-6);
    border: 0;
    border-radius: var(--radius-1);
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
    cursor: pointer;
  }

  .rows {
    list-style: none;
    padding: 0;
    border: 1px solid color-mix(in srgb, var(--line) 28%, transparent);
    border-radius: var(--radius-2);
    background: var(--surface);
    overflow: hidden;
  }

  .row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-5, var(--space-4));
    border-bottom: 1px solid color-mix(in srgb, var(--line) 20%, transparent);
    transition: background var(--motion);
  }

  .row:hover {
    background: color-mix(in srgb, var(--surface-2) 45%, transparent);
  }

  .row:last-child {
    border-bottom: 0;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
    min-width: 0;
  }

  .title {
    font-weight: var(--weight-semibold);
  }

  .date {
    color: var(--muted);
    font-size: var(--fs-2);
    font-family: var(--font-mono);
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--fs-1);
    font-family: var(--font-mono);
    color: var(--muted);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-1);
    padding: 0 var(--space-2);
    min-height: 24px;
    white-space: nowrap;
  }

  .chip.warn {
    color: var(--muted);
  }

  .warn-icon {
    flex-shrink: 0;
    color: var(--muted);
  }

  .actions {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    gap: var(--space-2);
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

  .danger-text {
    color: var(--danger);
  }

  .confirm-label {
    color: var(--muted);
    font-size: var(--fs-2);
  }
</style>
