<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte';

  import {
    apiFetch,
    downloadExport,
    fetchAudioObjectUrl,
    type AudioKind,
  } from '../api';
  import { shouldApplyAudioResult } from '../audioLoad';
  import TabPlayer from '../components/TabPlayer.svelte';
  import TabViewer from '../components/TabViewer.svelte';
  import { Transport, type Source } from '../synth';
  import {
    audibleTracks,
    loopBounds,
    measureAt,
    stepSpeed,
    trackKind,
    type LoopRange,
    type TabData,
  } from '../tabModel';
  import {
    exportFormats,
    isGenericRun,
    isGuitarPart,
    otherViewNote,
    listenForPart,
    nextTab,
    parseScoreParts,
    partLabel,
    restoreView,
    showPartSwitcher,
    toggleShown,
    type SavedView,
    type ScorePart,
    type ViewMode,
  } from '../scoreParts';

  type Score = {
    view: string;
    svg: string;
    text: string;
    meta: {
      title: string;
      key: string;
      tempo_bpm: number;
      duration_sec: number;
      beats_per_measure?: number;
      tuning_name: string;
      capo: number;
      transpose: number;
      bars_per_line: number;
      lyrics_status?: string;
    };
    layout?: unknown;
    tab?: TabData | null;
    artifacts: Record<string, boolean>;
    part?: string;
    parts?: string[];
  };

  type RunMeta = {
    details?: {
      lead_rhythm_fallback?: boolean;
      lead_rhythm_fallback_reason?: string;
    } | null;
    view?: Partial<SavedView> | null;
  };

  let {
    runId,
    onnew,
  }: {
    runId: string;
    onnew: () => void;
  } = $props();

  let view = $state('staff');
  let tuning = $state('Standard (EADGBE)');
  let capo = $state(0);
  let transpose = $state(0);
  let bars = $state(4);
  let score = $state<Score | null>(null);
  let error = $state<string | null>(null);
  let part = $state<ScorePart>('lead');
  let parts = $state<ScorePart[]>(['combined']);
  let listen = $state<AudioKind>('original');
  let audioSrc = $state<string | null>(null);
  let audioPending = $state(false);
  let confirmNew = $state(false);
  let exportOpen = $state(false);
  let panelOpen = $state(false);
  let fallbackNotice = $state<string | null>(null);
  let didInitialListenSync = false;
  // Single part or several stacked together; saved per run in meta.json (survives reloads).
  let mode = $state<ViewMode>('single');
  let shown = $state<string[]>([]);
  let savedView: Partial<SavedView> | null = null;
  let viewRestored = false;

  let audioEl = $state<HTMLAudioElement | null>(null);
  let playing = $state(false);
  let counting = $state(false);
  // Practice player (speed, loop, metronome, count-in, recording vs synth, mute/solo).
  let speed = $state(1);
  let source = $state<Source>('recording');
  let metronome = $state(false);
  let countIn = $state(false);
  let loop = $state<LoopRange | null>(null);
  let loopOn = $state(false);
  let muted = $state<Record<string, boolean>>({});
  let solo = $state<Record<string, boolean>>({});
  let volumes = $state<Record<string, number>>({});
  let recordingVolume = $state(1);
  const transport = new Transport();
  transport.onchange = (state) => {
    playing = state === 'playing';
    counting = state === 'counting';
    playTime = transport.time;
  };
  transport.audible = () => audibleTracks(tab?.tracks ?? [], muted, solo);
  transport.volume = (id) => volumes[id] ?? 1;
  let playTime = $state(0);
  let audioDuration = $state(0);
  // Non-reactive generation counter so $effect does not re-subscribe on bumps.
  let audioLoadGen = 0;

  async function loadRunMeta() {
    try {
      const meta = await apiFetch<RunMeta>(`/api/runs/${encodeURIComponent(runId)}`);
      savedView = meta.view ?? null;
      if (meta.details?.lead_rhythm_fallback) {
        fallbackNotice =
          meta.details.lead_rhythm_fallback_reason ||
          'Lead/rhythm split was unavailable; showing a single guitar tab.';
      } else {
        fallbackNotice = null;
      }
    } catch {
      fallbackNotice = null;
    }
  }

  async function loadScore() {
    try {
      const q = new URLSearchParams({
        view,
        tuning,
        capo: String(capo),
        transpose: String(transpose),
        bars: String(bars),
        part,
      });
      const next = await apiFetch<Score>(`/api/runs/${encodeURIComponent(runId)}/score?${q}`);
      score = next;
      const parsed = parseScoreParts(next.parts);
      parts = parsed;
      const ids = next.tab?.tracks.map((t) => t.id) ?? parsed;
      if (!viewRestored) {
        const restored = restoreView(savedView, ids);
        mode = restored.mode;
        shown = restored.shown;
        part = next.tab ? restored.part : (next.part ?? restored.part);
        viewRestored = true;
      } else if (!ids.includes(part)) {
        part = next.part && ids.includes(next.part) ? next.part : ids[0];
      }
      if (!didInitialListenSync) {
        listen = listenForPart(part, next.artifacts);
        didInitialListenSync = true;
      }
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Could not load score.';
    }
  }

  function selectPart(next: ScorePart) {
    if (next === part) return;
    part = next;
    listen = listenForPart(next, score?.artifacts);
  }

  async function loadAudio(kind: AudioKind) {
    // untrack: reading/writing audioSrc must not re-subscribe the listen effect
    // (that loop nulls the blob forever and storms /audio with 200s).
    const prev = untrack(() => audioSrc);
    if (prev) URL.revokeObjectURL(prev);
    audioLoadGen += 1;
    const gen = audioLoadGen;
    untrack(() => {
      audioSrc = null;
      audioPending = true;
    });
    try {
      const url = await fetchAudioObjectUrl(runId, kind);
      if (!shouldApplyAudioResult(gen, audioLoadGen)) {
        URL.revokeObjectURL(url);
        return;
      }
      untrack(() => {
        audioSrc = url;
        audioPending = false;
      });
    } catch {
      if (!shouldApplyAudioResult(gen, audioLoadGen)) return;
      untrack(() => {
        audioSrc = null;
        audioPending = false;
        // No recording to play: the synthesized tab is still available.
        if (synthReady) source = 'synth';
      });
    }
  }

  onMount(async () => {
    // Meta first so the saved Single/Together view is known before parts are placed.
    await loadRunMeta();
    void loadScore();
  });

  onDestroy(() => {
    transport.dispose();
    audioLoadGen += 1;
    const prev = untrack(() => audioSrc);
    if (prev) URL.revokeObjectURL(prev);
  });

  $effect(() => {
    void view;
    void tuning;
    void capo;
    void transpose;
    void bars;
    // The tab view carries every track, so switching parts there needs no refetch.
    if (view !== 'staff') void part;
    untrack(() => void loadScore());
  });

  let tab = $derived(view === 'staff' ? (score?.tab ?? null) : null);
  let synthReady = $derived(Boolean(tab?.tracks.some((t) => t.events.length)));
  let trackId = $derived(
    tab?.tracks.find((t) => t.id === part)?.id ?? tab?.tracks[0]?.id ?? 'combined',
  );
  let trackOrder = $derived(tab?.tracks.map((t) => t.id) ?? []);
  let trackIds = $derived(
    mode === 'together' && tab ? shown.filter((id) => trackOrder.includes(id)) : [trackId],
  );
  let multiPart = $derived(trackOrder.length > 1);
  // Tracks seen in the Tab view, remembered so other views and exports know the parts.
  let knownTracks = $state<{ id: string; label: string; kind?: 'tab' | 'staff' | 'drums' }[]>([]);
  $effect(() => {
    if (tab) knownTracks = tab.tracks.map((t) => ({ id: t.id, label: t.label, kind: t.kind }));
  });
  let genericRun = $derived(isGenericRun(knownTracks));
  let focusedPart = $derived(tab ? trackId : part);
  let focusedTrack = $derived(knownTracks.find((t) => t.id === focusedPart));
  let focusedKind = $derived(focusedTrack ? trackKind(focusedTrack) : 'tab');
  let viewNote = $derived(
    genericRun ? otherViewNote(focusedPart, focusedTrack?.label ?? focusedPart, view) : null,
  );
  let switcherParts = $derived(genericRun ? parts.filter(isGuitarPart) : parts);

  // Remember the view for this run (debounced; meta.json, because the desktop
  // window does not keep browser storage between launches).
  $effect(() => {
    const body = JSON.stringify({ mode, part, shown });
    if (!viewRestored) return;
    const timer = setTimeout(() => {
      void apiFetch(`/api/runs/${encodeURIComponent(runId)}/view`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body,
      }).catch(() => undefined);
    }, 300);
    return () => clearTimeout(timer);
  });

  function setMode(next: ViewMode) {
    mode = next;
    if (next === 'together' && !shown.length) shown = [...trackOrder];
  }

  function onModeKey(ev: KeyboardEvent) {
    if (ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
    ev.preventDefault();
    setMode(mode === 'single' ? 'together' : 'single');
    (ev.currentTarget as HTMLElement)
      .querySelector<HTMLElement>(`[data-mode="${mode}"]`)
      ?.focus();
  }

  function onTabKey(ev: KeyboardEvent) {
    const next = nextTab(trackOrder, trackId, ev.key);
    if (!next) return;
    ev.preventDefault();
    selectPart(next);
    document.getElementById(`part-tab-${next}`)?.focus();
  }

  $effect(() => {
    transport.attach(audioEl);
  });
  $effect(() => {
    transport.setData(tab);
  });
  $effect(() => {
    transport.setRate(speed);
  });
  $effect(() => {
    transport.metronome = metronome;
    transport.countIn = countIn;
  });
  $effect(() => {
    transport.setSource(source);
  });
  // Synth needs the tab view; fall back to the recording elsewhere.
  $effect(() => {
    if (source === 'synth' && !synthReady && audioSrc) source = 'recording';
  });
  $effect(() => {
    if (audioEl) audioEl.volume = recordingVolume;
  });

  let listenOptions = $derived.by(() => {
    const a = score?.artifacts ?? {};
    const out: { value: AudioKind; label: string }[] = [{ value: 'original', label: 'Full mix' }];
    if (a.guitar_stem) out.push({ value: 'stem', label: 'Guitar stem' });
    if (a.lead_guitar) out.push({ value: 'lead', label: 'Lead guitar' });
    if (a.rhythm_guitar) out.push({ value: 'rhythm', label: 'Rhythm guitar' });
    return out;
  });
  $effect(() => {
    const measures = tab?.measures;
    transport.setLoop(loopOn && loop && measures?.length ? loopBounds(measures, loop) : null);
  });

  // Depends only on listen (+ runId from props). loadAudio uses untrack for audioSrc.
  $effect(() => {
    const kind = listen;
    void runId;
    untrack(() => transport.reset());
    playing = false;
    playTime = 0;
    audioDuration = 0;
    void loadAudio(kind);
  });

  function togglePlay() {
    if (source === 'recording' && !audioSrc) return;
    if (source === 'synth' && !synthReady) return;
    transport.toggle();
  }

  function seekTo(time: number) {
    transport.seek(time);
    playTime = transport.time;
  }

  function cursorMeasure(): number {
    return tab ? measureAt(tab.measures, transport.time) : -1;
  }

  function setLoopEnd(which: 'a' | 'b') {
    const m = cursorMeasure();
    if (m < 0) return;
    const other = loop ? (which === 'a' ? loop.b : loop.a) : m;
    loop = which === 'a' ? { a: m, b: Math.max(m, other) } : { a: Math.min(m, other), b: m };
    loopOn = true;
  }

  function selectLoop(range: LoopRange) {
    loop = range;
    loopOn = true;
  }

  function toggleLoop() {
    if (!loop) {
      const m = cursorMeasure();
      if (m < 0) return;
      loop = { a: m, b: m };
      loopOn = true;
      return;
    }
    loopOn = !loopOn;
  }

  function selectTrack(id: string) {
    selectPart(id);
  }

  $effect(() => {
    if (!playing && !counting) return;
    let raf = 0;
    const tick = () => {
      playTime = transport.time;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  });

  $effect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
      const target = ev.target as HTMLElement | null;
      if (target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return;
      if (exportOpen || confirmNew) return;
      if (ev.code === 'Space') {
        if (target && target.tagName === 'BUTTON') return;
        ev.preventDefault();
        togglePlay();
        return;
      }
      if (!tab) return;
      const actions: Record<string, () => void> = {
        BracketLeft: () => setLoopEnd('a'),
        BracketRight: () => setLoopEnd('b'),
        KeyL: toggleLoop,
        Escape: () => {
          loop = null;
          loopOn = false;
        },
        Minus: () => (speed = stepSpeed(speed, -1)),
        NumpadSubtract: () => (speed = stepSpeed(speed, -1)),
        Equal: () => (speed = stepSpeed(speed, 1)),
        NumpadAdd: () => (speed = stepSpeed(speed, 1)),
        KeyM: () => (metronome = !metronome),
        KeyC: () => (countIn = !countIn),
        KeyT: () => {
          if (multiPart) setMode(mode === 'single' ? 'together' : 'single');
        },
      };
      const action = actions[ev.code];
      if (!action) return;
      ev.preventDefault();
      action();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  async function sendFeedback(answer: 'yes' | 'no') {
    await apiFetch(`/api/runs/${encodeURIComponent(runId)}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer }),
    });
  }

  let exportError = $state<string | null>(null);

  async function doExport(format: string, allShown = false) {
    exportError = null;
    // Legacy runs export exactly as before (no part field); picker runs name the part.
    const target = genericRun || multiPart ? { part: focusedPart } : {};
    const together = allShown ? { all_shown: true, shown: trackIds } : {};
    try {
      await downloadExport(runId, { format, tuning, capo, transpose, bars, ...target, ...together });
      exportOpen = false;
    } catch (err) {
      exportError = err instanceof Error ? err.message : 'Export failed.';
    }
  }
</script>

<section class="result rise-in">
  {#if error}
    <p class="banner" role="alert">{error}</p>
  {/if}
  {#if fallbackNotice}
    <p class="banner warn" role="status">{fallbackNotice}</p>
  {/if}

  <header class="chrome">
    <div class="identity">
      <h1>{score?.meta.title || 'Result'}</h1>
      <span class="ai-badge" title="Transcribed automatically from the audio. Expect mistakes."
        >AI-generated</span
      >
      {#if score}
        <p class="meta">
          Key {score.meta.key} · {Math.round(score.meta.tempo_bpm)} BPM ·
          {Math.floor(score.meta.duration_sec / 60)}:{String(Math.floor(score.meta.duration_sec % 60)).padStart(2, '0')}
        </p>
      {/if}
    </div>
    <div class="views" role="tablist" aria-label="Score view">
      {#each [['staff', 'Tab'], ['chords', 'Chords'], ['piano', 'Piano roll'], ['text', 'Text']] as [id, label]}
        <button
          type="button"
          class:active={view === id}
          onclick={() => (view = id)}>{label}</button
        >
      {/each}
    </div>
  </header>

  {#if tab && multiPart}
    <div class="partbar">
      <div
        class="mode"
        role="radiogroup"
        aria-label="Show parts"
        tabindex="-1"
        onkeydown={onModeKey}
      >
        {#each [['single', 'One part'], ['together', 'Together']] as [id, label] (id)}
          <button
            type="button"
            role="radio"
            data-mode={id}
            aria-checked={mode === id}
            tabindex={mode === id ? 0 : -1}
            class:active={mode === id}
            onclick={() => setMode(id as ViewMode)}>{label}</button
          >
        {/each}
      </div>
      {#if mode === 'single'}
        <div class="tracks" role="tablist" aria-label="Parts">
          {#each tab.tracks as t (t.id)}
            <button
              type="button"
              role="tab"
              id="part-tab-{t.id}"
              class="track"
              class:active={trackId === t.id}
              class:silent={!audibleTracks(tab.tracks, muted, solo).includes(t.id)}
              aria-selected={trackId === t.id}
              aria-controls="score-sheet"
              tabindex={trackId === t.id ? 0 : -1}
              onkeydown={onTabKey}
              onclick={() => selectTrack(t.id)}>{t.label}</button
            >
          {/each}
        </div>
      {:else}
        <div class="tracks" role="group" aria-label="Parts shown together">
          {#each tab.tracks as t (t.id)}
            <button
              type="button"
              class="track"
              class:active={shown.includes(t.id)}
              aria-pressed={shown.includes(t.id)}
              aria-disabled={shown.length === 1 && shown.includes(t.id)}
              title={shown.length === 1 && shown.includes(t.id)
                ? 'At least one part stays on screen'
                : undefined}
              onclick={() => (shown = toggleShown(shown, t.id, trackOrder))}>{t.label}</button
            >
          {/each}
        </div>
      {/if}
    </div>
  {:else if tab}
    <div class="tracks" role="group" aria-label="Tracks">
      {#each tab.tracks as t (t.id)}
        <button
          type="button"
          class="track"
          class:active={trackId === t.id}
          class:silent={!audibleTracks(tab.tracks, muted, solo).includes(t.id)}
          aria-pressed={trackId === t.id}
          onclick={() => selectTrack(t.id)}>{t.label}</button
        >
      {/each}
    </div>
  {:else if showPartSwitcher(switcherParts) || (genericRun && switcherParts.length > 0 && viewNote)}
    <div class="parts" role="tablist" aria-label="Guitar part">
      {#each switcherParts as id}
        <button
          type="button"
          class:active={part === id}
          onclick={() => selectPart(id)}>{partLabel(id)}</button
        >
      {/each}
    </div>
  {/if}

  <div class="score-stage">
    <div
      class="score"
      id="score-sheet"
      role={multiPart && mode === 'single' ? 'tabpanel' : undefined}
      aria-labelledby={multiPart && mode === 'single' ? `part-tab-${trackId}` : undefined}
    >
      {#if tab}
        <TabViewer
          data={tab}
          {trackIds}
          time={playTime}
          follow={playing}
          {loop}
          {loopOn}
          onseek={seekTo}
          onloopselect={selectLoop}
        />
      {:else if viewNote}
        <p class="muted view-note" role="status">{viewNote}</p>
      {:else if score?.svg}
        {@html score.svg}
      {/if}
      {#if score?.text && !viewNote}
        <pre>{score.text}</pre>
      {/if}
      {#if !score}
        <p class="muted"><span class="spinner is-on"></span> Loading score…</p>
      {/if}
    </div>
  </div>

  <audio
    bind:this={audioEl}
    src={audioSrc}
    preload="metadata"
    class="sr-audio"
    onpause={() => {
      // Paused from outside the app (media keys, system): keep the player in step.
      if (transport.playing && source === 'recording') transport.pause();
    }}
    onended={() => transport.handleEnded()}
    onloadedmetadata={() => (audioDuration = audioEl?.duration ?? 0)}
  ></audio>

  {#snippet morePanel()}
  <div class="panel" id="result-controls">
    <div class="panel-actions">
      <div class="export">
        <button type="button" class="ghost" onclick={() => (exportOpen = !exportOpen)}
          >Export</button
        >
        {#if exportOpen}
          <div class="menu">
            {#if multiPart || genericRun}
              <p class="menu-title">{focusedTrack?.label ?? partLabel(focusedPart)}</p>
              {#each exportFormats(focusedPart, focusedKind) as opt (opt.format)}
                <button
                  type="button"
                  disabled={opt.reason !== null}
                  aria-describedby={opt.reason ? `export-why-${opt.format}` : undefined}
                  onclick={() => doExport(opt.format)}>{opt.label}</button
                >
                {#if opt.reason}<small id="export-why-{opt.format}">{opt.reason}</small>{/if}
              {/each}
              {#if mode === 'together' && trackIds.length > 1}
                <button type="button" onclick={() => doExport('midi', true)}
                  >All shown parts (MIDI)</button
                >
                <button type="button" onclick={() => doExport('musicxml', true)}
                  >All shown parts (MusicXML)</button
                >
              {/if}
            {:else}
              {#each ['pdf', 'midi', 'tab', 'gp5'] as fmt}
                {#if !score || score.artifacts[fmt] !== false}
                  <button type="button" onclick={() => doExport(fmt)}>{fmt.toUpperCase()}</button>
                {/if}
              {/each}
            {/if}
            {#if exportError}<p class="menu-error" role="alert">{exportError}</p>{/if}
            {#if score?.artifacts.guitar_stem}
              <button type="button" onclick={() => doExport('guitar_stem')}>Guitar stem</button>
            {/if}
            {#if score?.artifacts.musicxml && !multiPart}
              <button type="button" onclick={() => doExport('musicxml')}>MusicXML</button>
            {/if}
          </div>
        {/if}
      </div>
      {#if confirmNew}
        <span class="confirm">Start over?</span>
        <button type="button" class="ghost" onclick={() => (confirmNew = false)}>Keep</button>
        <button type="button" class="danger" onclick={onnew}>Discard</button>
      {:else}
        <button type="button" class="ghost" onclick={() => (confirmNew = true)}>New song</button>
      {/if}
    </div>

    <h2>Inspector</h2>
    <label class="field"
      ><span>Tuning</span>
      <select bind:value={tuning}>
        <option>Standard (EADGBE)</option>
        <option>Drop D</option>
        <option>Half-step down</option>
      </select></label
    >
    <label class="field"
      ><span>Capo</span>
      <input type="number" min="0" max="12" bind:value={capo} /></label
    >
    <label class="field"
      ><span>Transpose</span>
      <input type="number" min="-12" max="12" bind:value={transpose} /></label
    >
    <label class="field"
      ><span>Bars per line</span>
      <input type="number" min="1" max="8" bind:value={bars} /></label
    >

    <div class="feedback">
      <span>Does this sound right?</span>
      <button type="button" class="ghost" onclick={() => sendFeedback('yes')}>Yes</button>
      <button type="button" class="ghost" onclick={() => sendFeedback('no')}>Not quite</button>
    </div>
  </div>
  {/snippet}

  <TabPlayer
    available={audioSrc !== null || synthReady}
    pending={audioPending}
    {playing}
    {counting}
    currentTime={playTime}
    duration={source === 'synth' ? (tab?.duration_sec ?? 0) : audioDuration}
    ontoggle={togglePlay}
    onseek={seekTo}
    practice={Boolean(tab)}
    {speed}
    onspeed={(s) => (speed = s)}
    {source}
    recordingAvailable={audioSrc !== null}
    onsource={(s) => (source = s)}
    {loopOn}
    hasLoop={loop !== null}
    onloop={toggleLoop}
    onsetA={() => setLoopEnd('a')}
    onsetB={() => setLoopEnd('b')}
    {metronome}
    onmetronome={() => (metronome = !metronome)}
    {countIn}
    oncountin={() => (countIn = !countIn)}
    tracks={tab?.tracks ?? []}
    {trackId}
    onselecttrack={selectTrack}
    {muted}
    {solo}
    {volumes}
    onmute={(id) => (muted = { ...muted, [id]: !muted[id] })}
    onsolo={(id) => (solo = { ...solo, [id]: !solo[id] })}
    onvolume={(id, v) => (volumes = { ...volumes, [id]: v })}
    {listenOptions}
    {listen}
    onlisten={(v) => (listen = v as AudioKind)}
    {recordingVolume}
    onrecordingvolume={(v) => (recordingVolume = v)}
    moreOpen={panelOpen}
    onmore={(open) => {
      panelOpen = open;
      if (!open) exportOpen = false;
    }}
    more={morePanel}
  />
</section>

<style>
  .result {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-height: calc(100vh - 120px);
    /* Room for the floating player dock. */
    padding-bottom: 168px;
  }
  @media (max-width: 560px) {
    .result {
      padding-bottom: 280px;
    }
  }
  .chrome {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    flex-shrink: 0;
  }
  .identity {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-3) var(--space-4);
  }
  h1 {
    font-family: var(--font-display);
    font-size: var(--fs-5);
    font-weight: var(--weight-medium);
  }
  .meta {
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: var(--fs-2);
  }
  .ai-badge {
    padding: 0 var(--space-2);
    border: 1px solid color-mix(in srgb, var(--accent) 55%, transparent);
    border-radius: var(--radius-1);
    color: var(--accent);
    font-size: var(--fs-1);
    line-height: var(--lh-1);
    font-weight: var(--weight-semibold);
  }
  .tracks {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .track {
    min-height: 40px;
    padding: 0 var(--space-3);
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .track.active {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 22%, transparent);
    color: var(--text);
    font-weight: var(--weight-semibold);
  }
  .track.silent {
    text-decoration: line-through;
    text-decoration-color: var(--muted);
  }
  .views {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .views button {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 0;
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .views button.active {
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
  }
  .partbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
  }
  .mode {
    display: inline-flex;
    padding: 2px;
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-1);
  }
  .mode button {
    min-height: 40px;
    padding: 0 var(--space-3);
    border: 0;
    border-radius: 3px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .mode button.active {
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
  }
  .track[aria-disabled='true'] {
    cursor: not-allowed;
  }
  .menu-title {
    padding: var(--space-1) var(--space-3);
    color: var(--muted);
    font-size: var(--fs-1);
  }
  .menu small {
    display: block;
    padding: 0 var(--space-3) var(--space-2);
    color: var(--muted);
    font-size: var(--fs-1);
    max-width: 32ch;
  }
  .menu-error {
    padding: var(--space-2) var(--space-3);
    color: #ffc9c6;
    font-size: var(--fs-2);
  }
  .parts {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .parts button {
    min-height: 40px;
    padding: 0 var(--space-3);
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .parts button.active {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 22%, transparent);
    color: var(--text);
    font-weight: var(--weight-semibold);
  }
  .score-stage {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .score {
    position: relative;
    flex: 1 1 auto;
    background: color-mix(in srgb, var(--art) 72%, var(--surface));
    border: 1px solid color-mix(in srgb, var(--line) 14%, transparent);
    border-radius: var(--radius-2);
    padding: var(--space-3);
    overflow-x: hidden;
    overflow-y: auto;
    min-height: calc(100vh - 280px);
  }
  .score :global(svg) {
    display: block;
    width: 100%;
    max-width: 100%;
    height: auto;
  }
  pre {
    white-space: pre;
    font-family: var(--font-mono);
    font-size: var(--fs-3);
    line-height: 1.45;
  }
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .panel h2 {
    font-size: var(--fs-4);
    font-weight: var(--weight-medium);
  }
  .panel-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
  }
  .export {
    position: relative;
  }
  .menu {
    margin-top: var(--space-2);
    background: var(--bg);
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-2);
    display: flex;
    flex-direction: column;
    min-width: 140px;
    z-index: 7;
  }
  .menu button {
    min-height: 44px;
    border: 0;
    background: transparent;
    color: var(--text);
    text-align: left;
    padding: 0 var(--space-4);
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
  }
  input,
  select {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 1px solid rgba(168, 184, 204, 0.4);
    border-radius: var(--radius-1);
    background: var(--bg);
    color: var(--text);
  }
  .feedback {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    color: var(--muted);
    padding-top: var(--space-2);
    border-top: 1px solid color-mix(in srgb, var(--line) 12%, transparent);
  }
  .confirm {
    color: var(--muted);
    font-size: var(--fs-2);
  }
  .sr-audio {
    display: none;
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
  .banner {
    background: var(--surface-2);
    border-radius: var(--radius-2);
    padding: var(--space-4);
  }
  .banner.warn {
    border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
    color: var(--text);
  }
  .muted {
    color: var(--muted);
  }
</style>
