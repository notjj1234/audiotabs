<script lang="ts">
  import { apiFetch, getToken } from './lib/api';
  import AppBar from './lib/components/AppBar.svelte';
  import {
    analysisFingerprint,
    buildRequest,
    newDraft,
    NO_SEPARATOR_NOTICE,
    routeForConvert,
    tabOptionsFrom,
    type ConvertCaps,
    type ConvertRequest,
    type TabOptions,
  } from './lib/convertFlow';
  import Entry from './lib/screens/Entry.svelte';
  import Instruments from './lib/screens/Instruments.svelte';
  import Library from './lib/screens/Library.svelte';
  import Result from './lib/screens/Result.svelte';
  import Waiting from './lib/screens/Waiting.svelte';

  type Screen = 'entry' | 'analyzing' | 'instruments' | 'waiting' | 'result' | 'library';
  type Analysis = { id: string; fingerprint: string; request: ConvertRequest; done: boolean };

  let screen = $state<Screen>('entry');
  let jobId = $state<string | null>(null);
  let runId = $state<string | null>(null);
  let entryError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  // Entry's fields live here so Back from the picker keeps the upload and settings.
  let draft = $state(newDraft());
  let analysis = $state<Analysis | null>(null);
  // Tab settings chosen on the instruments page (kept when going back).
  let tabOptions = $state<TabOptions>(tabOptionsFrom(newDraft()));
  let lastCaps: ConvertCaps | null = null;

  // Consume the launch token from the URL fragment on boot.
  getToken();

  function goEntry() {
    screen = 'entry';
    jobId = null;
    entryError = null;
    notice = null;
  }

  function failJob(message: string) {
    // Do not call goEntry() — it clears entryError.
    jobId = null;
    screen = 'entry';
    entryError = message;
  }

  function startJob(id: string) {
    Object.assign(draft, tabOptions);
    jobId = id;
    entryError = null;
    screen = 'waiting';
  }

  function openRun(id: string) {
    runId = id;
    // A finished run consumed the analysis on the server.
    analysis = null;
    screen = 'result';
  }

  function dropAnalysis() {
    const stale = analysis;
    analysis = null;
    if (stale) {
      void apiFetch(`/api/analyses/${encodeURIComponent(stale.id)}`, { method: 'DELETE' }).catch(
        () => undefined,
      );
    }
  }

  async function convert(request: ConvertRequest, caps: ConvertCaps | null) {
    lastCaps = caps;
    const route = routeForConvert(
      { preset: request.preset, separateStems: Boolean(request.config.separate_stems) },
      caps,
    );
    if (route === 'picker') {
      const fingerprint = analysisFingerprint(request);
      if (analysis && analysis.fingerprint === fingerprint && analysis.done) {
        // Same audio and separation settings: reuse the instruments we already found.
        analysis = { ...analysis, request };
        entryError = null;
        screen = 'instruments';
        return;
      }
      dropAnalysis();
      const res = await apiFetch<{ analysis_id: string }>('/api/analyses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      analysis = { id: res.analysis_id, fingerprint, request, done: false };
      entryError = null;
      notice = null;
      screen = 'analyzing';
      return;
    }
    notice = route === 'direct_with_notice' ? NO_SEPARATOR_NOTICE : null;
    // No separator installed: tab the whole recording, as the notice says, instead
    // of asking the pipeline for a separation it can't do.
    const body =
      route === 'direct_with_notice'
        ? {
            ...request,
            config: { ...request.config, separate_stems: false, mix_aware_filtering: false },
          }
        : request;
    const res = await apiFetch<{ job_id: string }>('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    startJob(res.job_id);
  }

  /** Run the instrument check again on the whole song instead of its first part. */
  async function checkWholeSong() {
    draft.saferLength = false;
    draft.fullTrackConfirm = true;
    const request = buildRequest(draft);
    if ('error' in request) throw new Error(request.error);
    await convert(request, lastCaps);
  }

  /** Start a failed instrument check again from the same song. */
  async function retryAnalysis() {
    const previous = analysis;
    if (!previous) return;
    analysis = null;
    await convert(previous.request, lastCaps);
  }

  function analysisFailed(message: string) {
    analysis = null;
    failJob(message);
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
  {:else if screen === 'analyzing' && analysis}
    {#key analysis.id}
      <Waiting
        kind="analysis"
        jobId={analysis.id}
        ondone={() => {
          if (analysis) analysis = { ...analysis, done: true };
          screen = 'instruments';
        }}
        onfail={analysisFailed}
        onretry={retryAnalysis}
        oncancel={() => {
          analysis = null;
          goEntry();
        }}
      />
    {/key}
  {:else if screen === 'instruments' && analysis}
    <Instruments
      analysisId={analysis.id}
      request={analysis.request}
      bind:options={tabOptions}
      onstart={startJob}
      onback={goEntry}
      onexpired={(message) => analysisFailed(message)}
      onfullsong={checkWholeSong}
    />
  {:else if screen === 'waiting' && jobId}
    <Waiting
      kind="job"
      {jobId}
      {notice}
      ondone={(id) => openRun(id)}
      onfail={failJob}
      oncancel={goEntry}
    />
  {:else if screen === 'result' && runId}
    <Result {runId} onnew={goEntry} />
  {:else}
    <Entry bind:draft onconvert={convert} />
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
