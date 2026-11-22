<script lang="ts">
  import { getToken } from './lib/api';
  import AppBar from './lib/components/AppBar.svelte';
  import Entry from './lib/screens/Entry.svelte';
  import Library from './lib/screens/Library.svelte';
  import Result from './lib/screens/Result.svelte';
  import Waiting from './lib/screens/Waiting.svelte';

  type Screen = 'entry' | 'waiting' | 'result' | 'library';

  let screen = $state<Screen>('entry');
  let jobId = $state<string | null>(null);
  let runId = $state<string | null>(null);
  let entryError = $state<string | null>(null);

  // Consume the launch token from the URL fragment on boot.
  getToken();

  function goEntry() {
    screen = 'entry';
    jobId = null;
    entryError = null;
  }

  function startJob(id: string) {
    jobId = id;
    entryError = null;
    screen = 'waiting';
  }

  function openRun(id: string) {
    runId = id;
    screen = 'result';
  }
</script>

<AppBar
  {screen}
  onnav={(next) => {
    if (next === 'entry') goEntry();
    else screen = next;
  }}
/>
<main class="content">
  {#if entryError && screen === 'entry'}
    <p class="banner" role="alert">{entryError}</p>
  {/if}

  {#if screen === 'library'}
    <Library ontranscribe={goEntry} onopen={openRun} />
  {:else if screen === 'waiting' && jobId}
    <Waiting
      {jobId}
      ondone={(id) => openRun(id)}
      onfail={(message) => {
        entryError = message;
        goEntry();
      }}
    />
  {:else if screen === 'result' && runId}
    <Result {runId} onnew={goEntry} />
  {:else}
    <Entry onjob={startJob} />
  {/if}
</main>

<style>
  .content {
    max-width: var(--content-max);
    margin: 0 auto;
    padding: var(--space-12) var(--space-8) var(--space-16);
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }

  .banner {
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--danger) 45%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-4);
    margin-bottom: var(--space-6);
    color: #ffc9c6;
    text-align: center;
  }
</style>
