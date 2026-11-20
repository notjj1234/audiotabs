<script lang="ts">
  import { onMount } from 'svelte';

  import { apiFetch } from '../api';

  type Run = {
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

  let { ontranscribe }: { ontranscribe: () => void } = $props();

  let runs = $state<Run[] | null>(null);
  let loadError = $state<string | null>(null);

  onMount(async () => {
    try {
      runs = await apiFetch<Run[]>('/api/runs');
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Could not load your runs.';
    }
  });

  function formatDate(epochSeconds: number): string {
    return new Date(epochSeconds * 1000).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }
</script>

<section aria-labelledby="library-heading">
  <h1 id="library-heading">Library</h1>

  {#if loadError}
    <p class="banner" role="alert">{loadError}</p>
  {:else if runs === null}
    <p class="muted">Loading…</p>
  {:else if runs.length === 0}
    <div class="empty">
      <p>Nothing transcribed yet.</p>
      <button type="button" class="primary" onclick={ontranscribe}>Transcribe something</button>
    </div>
  {:else}
    <ul class="rows">
      {#each runs as run (run.id)}
        <li class="row">
          <span class="title">{run.title || 'Untitled run'}</span>
          {#if run.config?.model === 'lead_rhythm_split'}
            <span class="chip">Lead/Rhythm split</span>
          {/if}
          {#if Array.isArray(run.diagnostics?.warnings) && (run.diagnostics?.warnings?.length ?? 0) > 0}
            <span class="chip warn" title="Split quality warnings">⚠ {run.diagnostics?.warnings?.length}</span>
          {/if}
          <span class="date">{formatDate(run.created_at)}</span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  h1 {
    font-family: var(--font-display);
    font-size: var(--fs-5);
    line-height: var(--lh-5);
    letter-spacing: -0.01em;
    font-weight: 400;
    margin-bottom: var(--space-6);
  }

  .muted {
    color: var(--muted);
  }

  .banner {
    color: var(--text);
    background: var(--surface-2);
    border: 1px solid var(--line);
    border-radius: var(--radius-2);
    padding: var(--space-4);
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
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
    border: 1px solid var(--line);
    border-radius: var(--radius-2);
    background: var(--surface);
    overflow: hidden;
  }

  .row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4);
    border-bottom: 1px solid var(--line);
  }

  .row:last-child {
    border-bottom: 0;
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
    font-size: var(--fs-1);
    font-family: var(--font-mono);
    color: var(--muted);
    border: 1px solid var(--line);
    border-radius: var(--radius-1);
    padding: 0 var(--space-2);
    white-space: nowrap;
  }

  .chip.warn {
    color: var(--text);
  }
</style>
