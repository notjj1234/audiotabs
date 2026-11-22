<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { apiFetch } from '../api';

  type JobSnap = {
    id: string;
    state: string;
    title: string;
    rows: { id: string; label: string; state: string; detail: string }[];
    message: string;
    fraction: number;
    run_id: string | null;
    error: { code: string; message: string; hint?: string } | null;
  };

  let {
    jobId,
    ondone,
    onfail,
  }: {
    jobId: string;
    ondone: (runId: string) => void;
    onfail: (message: string) => void;
  } = $props();

  let snap = $state<JobSnap | null>(null);
  let started = $state(Date.now());
  let elapsed = $state(0);
  let timer: ReturnType<typeof setInterval> | undefined;
  let poller: ReturnType<typeof setInterval> | undefined;

  async function poll() {
    try {
      const next = await apiFetch<JobSnap>(`/api/jobs/${encodeURIComponent(jobId)}`);
      snap = next;
      if (next.state === 'done' && next.run_id) {
        ondone(next.run_id);
        return;
      }
      if (next.state === 'failed') {
        onfail(next.error?.message || next.message || 'Conversion failed.');
      }
    } catch (err) {
      onfail(err instanceof Error ? err.message : 'Lost connection to the job.');
    }
  }

  onMount(() => {
    started = Date.now();
    timer = setInterval(() => {
      elapsed = Math.floor((Date.now() - started) / 1000);
    }, 500);
    void poll();
    poller = setInterval(() => void poll(), 500);
  });

  onDestroy(() => {
    if (timer) clearInterval(timer);
    if (poller) clearInterval(poller);
  });
</script>

<section class="waiting rise-in" aria-live="polite">
  <h1>{snap?.title || 'Converting…'}</h1>
  <p class="elapsed">{elapsed}s · {snap?.message || 'Starting'}</p>
  <div class="indeterminate-bar" aria-hidden="true"><div class="fill"></div></div>
  <ul class="stages">
    {#each snap?.rows ?? [] as row (row.id)}
      <li class="stage" data-state={row.state}>
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
</style>
