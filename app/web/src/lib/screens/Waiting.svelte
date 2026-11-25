<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { apiFetch, ApiError } from '../api';

  type JobSnap = {
    id: string;
    state: string;
    title: string;
    rows: { id: string; label: string; state: string; detail: string }[];
    message: string;
    fraction: number;
    updated_at?: number;
    run_id: string | null;
    error: { code: string; message: string; hint?: string } | null;
  };

  let {
    jobId,
    kind = 'job',
    notice = null,
    ondone,
    onfail,
    oncancel,
    onretry,
  }: {
    jobId: string;
    kind?: 'job' | 'analysis';
    notice?: string | null;
    ondone: (runId: string) => void;
    onfail: (message: string) => void;
    oncancel?: () => void;
    /** Analysis only: start the instrument check again from the same source. */
    onretry?: () => Promise<void>;
  } = $props();

  // svelte-ignore state_referenced_locally
  const base = kind === 'analysis' ? '/api/analyses' : '/api/jobs';
  // svelte-ignore state_referenced_locally
  const isAnalysis = kind === 'analysis';
  let cancelling = $state(false);

  // Consecutive poll errors tolerated before saying the connection is lost (~5 s).
  const MAX_POLL_ERRORS = 10;
  // No progress update for this long shows a "still working" notice instead of silence.
  const STALL_MS = 3 * 60 * 1000;

  // svelte-ignore state_referenced_locally
  let currentJob = $state(jobId);
  let snap = $state<JobSnap | null>(null);
  let started = $state(Date.now());
  let elapsed = $state(0);
  let failure = $state<{ message: string; hint?: string; canRetry: boolean } | null>(null);
  let retrying = $state(false);
  let lastChange = $state(Date.now());
  let lastUpdatedAt = 0;
  let pollErrors = 0;
  let finished = false;
  let timer: ReturnType<typeof setInterval> | undefined;
  let poller: ReturnType<typeof setInterval> | undefined;

  let stalled = $derived(!failure && elapsed > 0 && Date.now() - lastChange > STALL_MS);

  function stopPolling() {
    finished = true;
    if (timer) clearInterval(timer);
    if (poller) clearInterval(poller);
    timer = undefined;
    poller = undefined;
  }

  function startPolling() {
    finished = false;
    pollErrors = 0;
    lastUpdatedAt = 0;
    started = Date.now();
    lastChange = Date.now();
    elapsed = 0;
    timer = setInterval(() => {
      elapsed = Math.floor((Date.now() - started) / 1000);
    }, 500);
    void poll();
    poller = setInterval(() => void poll(), 500);
  }

  function fail(message: string, hint: string | undefined, canRetry: boolean) {
    stopPolling();
    failure = { message, hint, canRetry };
  }

  async function poll() {
    if (finished) return;
    try {
      const next = await apiFetch<JobSnap>(`${base}/${encodeURIComponent(currentJob)}`);
      if (finished) return;
      pollErrors = 0;
      snap = next;
      if (next.updated_at && next.updated_at !== lastUpdatedAt) {
        lastUpdatedAt = next.updated_at;
        lastChange = Date.now();
      }
      if (next.state === 'done' && (isAnalysis || next.run_id)) {
        stopPolling();
        ondone(next.run_id ?? currentJob);
        return;
      }
      if (next.state === 'cancelled') {
        stopPolling();
        (oncancel ?? (() => onfail('Cancelled.')))();
        return;
      }
      if (next.state === 'failed') {
        fail(
          next.error?.message || next.message || 'Tab generation failed.',
          next.error?.hint || undefined,
          !isAnalysis || Boolean(onretry),
        );
      }
    } catch (err) {
      if (err instanceof ApiError && (err.code === 'job_missing' || err.code === 'analysis_missing')) {
        fail(err.message, 'The app may have restarted. Go back and generate the tab again.', false);
        return;
      }
      pollErrors += 1;
      if (pollErrors >= MAX_POLL_ERRORS) {
        fail(
          err instanceof Error ? err.message : 'Lost connection to the job.',
          'The local server stopped answering.',
          false,
        );
      }
    }
  }

  async function retry() {
    retrying = true;
    if (isAnalysis && onretry) {
      try {
        await onretry();
      } catch (err) {
        failure = {
          message: err instanceof Error ? err.message : 'Could not start again.',
          hint: failure?.hint,
          canRetry: false,
        };
      } finally {
        retrying = false;
      }
      return;
    }
    try {
      const res = await apiFetch<{ job_id: string }>(
        `/api/jobs/${encodeURIComponent(currentJob)}/retry`,
        { method: 'POST' },
      );
      currentJob = res.job_id;
      snap = null;
      failure = null;
      startPolling();
    } catch (err) {
      failure = {
        message: err instanceof Error ? err.message : 'Could not start again.',
        hint: failure?.hint,
        canRetry: false,
      };
    } finally {
      retrying = false;
    }
  }

  function back() {
    stopPolling();
    onfail(failure?.message || 'Tab generation was cancelled.');
  }

  /** Stop the server-side work, then leave at once; cleanup finishes in the background. */
  function cancel() {
    if (cancelling) return;
    cancelling = true;
    stopPolling();
    void apiFetch(`${base}/${encodeURIComponent(currentJob)}/cancel`, { method: 'POST' }).catch(
      () => undefined,
    );
    (oncancel ?? (() => onfail('Cancelled.')))();
  }

  onMount(() => {
    startPolling();
  });

  onDestroy(() => {
    stopPolling();
  });
</script>

<section class="waiting rise-in" aria-live="polite">
  {#if failure}
    <h1>{isAnalysis ? "Couldn't check the instruments" : "Couldn't generate the tab"}</h1>
    <p class="error" role="alert">{failure.message}</p>
    {#if failure.hint}
      <details class="details">
        <summary>Technical details</summary>
        <p class="hint">{failure.hint}</p>
      </details>
    {/if}
    <div class="actions">
      {#if failure.canRetry}
        <button type="button" class="primary" disabled={retrying} onclick={retry}>
          <span class="spinner" class:is-on={retrying} aria-hidden="true"></span>
          Try again
        </button>
      {/if}
      <button type="button" class="ghost" onclick={back}>Back</button>
    </div>
  {:else}
    <h1>{isAnalysis ? 'Finding the instruments' : snap?.title || 'Generating tab…'}</h1>
    {#if isAnalysis && snap?.title}<p class="subtitle">{snap.title}</p>{/if}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
    <p class="elapsed">{elapsed}s · {snap?.message || 'Starting'}</p>
    <div class="indeterminate-bar" aria-hidden="true"><div class="fill"></div></div>
    {#if stalled}
      <div class="stall" role="status">
        <p>
          No progress for a few minutes. Stem separation can be slow on long songs, so it may
          still be working.
        </p>
        <button type="button" class="ghost" onclick={back}>Back</button>
      </div>
    {/if}
  {/if}
  {#if !failure}
    <div class="actions">
      <button type="button" class="ghost" disabled={cancelling} onclick={cancel}>
        {cancelling ? 'Cancelling…' : 'Cancel'}
      </button>
    </div>
  {/if}
  <ul class="stages">
    {#each snap?.rows ?? [] as row (row.id)}
      <li class="stage" data-state={failure && row.state === 'active' ? 'failed' : row.state}>
        <span class="mark"></span>
        <span>
          <strong>{row.label}</strong>
          {#if row.detail}<small>{row.detail}</small>{/if}
        </span>
      </li>
    {/each}
  </ul>
</section>

<style>
  .waiting {
    width: 100%;
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-8);
    text-align: left;
  }
  h1 {
    font-size: var(--fs-5);
    font-weight: var(--weight-semibold);
    letter-spacing: -0.02em;
    margin-bottom: var(--space-3);
  }
  .subtitle {
    color: var(--text);
    margin-bottom: var(--space-3);
  }
  .notice {
    color: var(--muted);
    font-size: var(--fs-2);
    max-width: 68ch;
    margin-bottom: var(--space-4);
  }
  .elapsed {
    color: var(--muted);
    margin-bottom: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--fs-2);
  }
  .indeterminate-bar {
    height: 4px;
    border-radius: 2px;
    background: var(--art);
    overflow: hidden;
  }
  .indeterminate-bar .fill {
    width: 40%;
    height: 100%;
    border-radius: 2px;
    background: var(--accent);
    animation: home-bar-slide 1.2s var(--ease-out) infinite;
  }
  .stages {
    list-style: none;
    padding: 0;
    margin-top: var(--space-6);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    text-align: left;
    max-width: 480px;
  }
  .stage {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
    color: var(--muted);
  }
  .stage[data-state='active'] {
    color: var(--text);
  }
  .stage[data-state='done'] {
    color: var(--text-secondary);
  }
  .stage strong {
    display: block;
    font-weight: var(--weight-medium);
  }
  .stage small {
    display: block;
    color: var(--muted);
  }
  .mark {
    width: 10px;
    height: 10px;
    margin-top: 6px;
    border-radius: 50%;
    background: rgba(202, 224, 250, 0.25);
    flex-shrink: 0;
  }
  .stage[data-state='active'] .mark {
    background: var(--accent);
  }
  .stage[data-state='done'] .mark {
    background: var(--ok);
  }
  .stage[data-state='failed'] {
    color: var(--text);
  }
  .stage[data-state='failed'] .mark {
    background: var(--danger);
  }
  .error {
    color: var(--text);
    margin-bottom: var(--space-2);
  }
  .details {
    margin-top: var(--space-2);
    color: var(--muted);
    font-size: var(--fs-2);
  }
  .details summary {
    cursor: pointer;
    min-height: 32px;
    display: inline-flex;
    align-items: center;
  }
  .details .hint {
    margin-top: var(--space-1);
    overflow-wrap: anywhere;
    font-family: var(--font-mono);
  }
  .hint,
  .stall p {
    color: var(--muted);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }
  .stall {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
    border-radius: var(--radius-2);
  }
  .stall p {
    flex: 1 1 240px;
  }
  .primary,
  .ghost {
    min-height: 44px;
    padding: 0 var(--space-4);
    border-radius: var(--radius-1);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }
  .primary {
    border: 0;
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
  }
  .primary:disabled {
    opacity: 0.6;
    cursor: default;
  }
  .ghost {
    border: 1px solid rgba(168, 184, 204, 0.4);
    background: transparent;
    color: var(--text);
  }
</style>
