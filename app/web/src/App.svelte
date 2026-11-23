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

  function failJob(message: string) {
    // Do not call goEntry() — it clears entryError.
    jobId = null;
    screen = 'entry';
    entryError = message;
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
<main class="content" class:result-tight={screen === 'result'}>
  {#if entryError && screen === 'entry'}
    <p class="banner" role="alert">{entryError}</p>
  {/if}

  {#if screen === 'library'}
    <Library ontranscribe={goEntry} onopen={openRun} />
  {:else if screen === 'waiting' && jobId}
    <Waiting
      {jobId}
      ondone={(id) => openRun(id)}
      onfail={failJob}
    />
  {:else if screen === 'result' && runId}
    <Result {runId} onnew={goEntry} />
  {:else}
    <Entry onjob={startJob} />
  {/if}
</main>

<style>
  .content {
    width: 100%;
    max-width: var(--content-max);
    margin-left: auto;
    margin-right: auto;
    padding: var(--space-16) var(--gutter) var(--space-16);
    display: flex;
    flex-direction: column;
    align-items: stretch;
    box-sizing: border-box;
  }
  .content.result-tight {
    max-width: none;
    padding-top: var(--space-6);
    padding-bottom: var(--space-6);
    padding-left: var(--space-6);
    padding-right: var(--space-6);
    flex: 1;
    min-height: calc(100vh - 56px);
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
