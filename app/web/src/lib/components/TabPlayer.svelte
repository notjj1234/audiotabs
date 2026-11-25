<script lang="ts">
  import type { Snippet } from 'svelte';

  import type { Source } from '../synth';
  import { SPEEDS, stepSpeed } from '../tabModel';

  type MixerTrack = { id: string; label: string };
  type ListenOption = { value: string; label: string };
  type Popover = 'mixer' | 'more' | 'help' | null;

  let {
    available,
    pending = false,
    playing,
    counting = false,
    currentTime,
    duration,
    ontoggle,
    onseek,
    practice = false,
    speed = 1,
    onspeed = () => {},
    source = 'recording',
    recordingAvailable = true,
    onsource = () => {},
    loopOn = false,
    hasLoop = false,
    onloop = () => {},
    onsetA = () => {},
    onsetB = () => {},
    metronome = false,
    onmetronome = () => {},
    countIn = false,
    oncountin = () => {},
    tracks = [],
    trackId = '',
    onselecttrack = () => {},
    muted = {},
    solo = {},
    volumes = {},
    onmute = () => {},
    onsolo = () => {},
    onvolume = () => {},
    listenOptions = [],
    listen = 'original',
    onlisten = () => {},
    recordingVolume = 1,
    onrecordingvolume = () => {},
    moreOpen = false,
    onmore = () => {},
    more,
  }: {
    available: boolean;
    pending?: boolean;
    playing: boolean;
    counting?: boolean;
    currentTime: number;
    duration: number;
    ontoggle: () => void;
    onseek: (time: number) => void;
    /** Tab-only tools (loop, metronome, count-in, synth). */
    practice?: boolean;
    speed?: number;
    onspeed?: (speed: number) => void;
    source?: Source;
    recordingAvailable?: boolean;
    onsource?: (source: Source) => void;
    loopOn?: boolean;
    hasLoop?: boolean;
    onloop?: () => void;
    onsetA?: () => void;
    onsetB?: () => void;
    metronome?: boolean;
    onmetronome?: () => void;
    countIn?: boolean;
    oncountin?: () => void;
    tracks?: MixerTrack[];
    trackId?: string;
    onselecttrack?: (id: string) => void;
    muted?: Record<string, boolean>;
    solo?: Record<string, boolean>;
    volumes?: Record<string, number>;
    onmute?: (id: string) => void;
    onsolo?: (id: string) => void;
    onvolume?: (id: string, volume: number) => void;
    listenOptions?: ListenOption[];
    listen?: string;
    onlisten?: (value: string) => void;
    recordingVolume?: number;
    onrecordingvolume?: (volume: number) => void;
    /** The "More" panel (export, inspector…) is owned by the screen. */
    moreOpen?: boolean;
    onmore?: (open: boolean) => void;
    more?: Snippet;
  } = $props();

  let popover = $state<Popover>(null);
  let collapsed = $state(false);
  let dock = $state<HTMLDivElement | null>(null);

  let shown = $derived<Popover>(moreOpen ? 'more' : popover);

  const SHORTCUTS: [string, string][] = [
    ['Space', 'Play / pause'],
    ['[', 'Loop start (A) at the cursor'],
    [']', 'Loop end (B) at the cursor'],
    ['L', 'Loop on / off'],
    ['Esc', 'Clear the loop'],
    ['− / =', 'Slower / faster'],
    ['M', 'Metronome'],
    ['C', 'Count-in'],
    ['T', 'One part / Together (multi-part runs)'],
  ];

  function open(next: Popover) {
    const target = shown === next ? null : next;
    popover = target === 'more' ? null : target;
    onmore(target === 'more');
  }

  function closeAll() {
    popover = null;
    if (moreOpen) onmore(false);
  }

  $effect(() => {
    if (!shown) return;
    const onDown = (ev: PointerEvent) => {
      if (dock && !dock.contains(ev.target as Node)) closeAll();
    };
    window.addEventListener('pointerdown', onDown);
    return () => window.removeEventListener('pointerdown', onDown);
  });

  /**
   * Mount the dock on <body> so it stays pinned to the window. The result screen's
   * entrance animation keeps a transform on the page, which would otherwise make the
   * fixed dock scroll away with the content.
   */
  function pinToWindow(node: HTMLElement) {
    document.body.appendChild(node);
    return {
      destroy() {
        node.remove();
      },
    };
  }

  function fmt(sec: number): string {
    if (!Number.isFinite(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  let progress = $derived(duration > 0 ? Math.min(100, (currentTime / duration) * 100) : 0);
</script>

{#snippet playButton(big: boolean)}
  <button
    type="button"
    class="play"
    class:big
    aria-label={playing || counting ? 'Pause' : 'Play'}
    disabled={!available}
    onclick={ontoggle}
  >
    {#if playing || counting}
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <rect x="6" y="5" width="4.5" height="14" rx="1" />
        <rect x="13.5" y="5" width="4.5" height="14" rx="1" />
      </svg>
    {:else}
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M8 5.5v13a1 1 0 0 0 1.52.86l11-6.5a1 1 0 0 0 0-1.72l-11-6.5A1 1 0 0 0 8 5.5Z" />
      </svg>
    {/if}
  </button>
{/snippet}

{#snippet seekStrip()}
  <div class="strip">
    <span class="time">{counting ? 'Count-in…' : fmt(currentTime)}</span>
    <input
      class="seek"
      type="range"
      min="0"
      max={duration || 0}
      step="0.01"
      value={currentTime}
      aria-label="Seek"
      disabled={!available}
      style:--progress="{progress}%"
      oninput={(e) => onseek(Number((e.currentTarget as HTMLInputElement).value))}
    />
    <span class="time">{fmt(duration)}</span>
    <button
      type="button"
      class="fold"
      aria-label={collapsed ? 'Show player controls' : 'Hide player controls'}
      aria-expanded={!collapsed}
      onclick={() => {
        collapsed = !collapsed;
        closeAll();
      }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d={collapsed ? 'M6 15l6-6 6 6' : 'M6 9l6 6 6-6'}
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  </div>
{/snippet}

<div
  class="dock"
  class:collapsed
  bind:this={dock}
  use:pinToWindow
  role="region"
  aria-label="Player"
>
  {#if shown === 'mixer'}
    <div class="pop left" role="dialog" aria-label="Mixer">
      {#if tracks.length}
        <h2>Tab tracks</h2>
        <ul class="mix">
          {#each tracks as t (t.id)}
            <li class:current={trackId === t.id}>
              <button
                type="button"
                class="mix-name"
                aria-pressed={trackId === t.id}
                title="Show this track's tab"
                onclick={() => onselecttrack(t.id)}>{t.label}</button
              >
              <button
                type="button"
                class="chip"
                class:on={muted[t.id]}
                aria-pressed={Boolean(muted[t.id])}
                aria-label="Mute {t.label}"
                onclick={() => onmute(t.id)}>M</button
              >
              <button
                type="button"
                class="chip"
                class:on={solo[t.id]}
                aria-pressed={Boolean(solo[t.id])}
                aria-label="Solo {t.label}"
                onclick={() => onsolo(t.id)}>S</button
              >
              <input
                class="vol"
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={volumes[t.id] ?? 1}
                aria-label="{t.label} volume"
                oninput={(e) => onvolume(t.id, Number((e.currentTarget as HTMLInputElement).value))}
              />
            </li>
          {/each}
        </ul>
        <p class="note">Mute, solo and volume shape the synth playback.</p>
      {/if}
      {#if listenOptions.length}
        <h2>Recording</h2>
        <div class="listen" role="radiogroup" aria-label="Recording plays">
          {#each listenOptions as opt (opt.value)}
            <button
              type="button"
              role="radio"
              aria-checked={listen === opt.value}
              class:on={listen === opt.value}
              onclick={() => onlisten(opt.value)}>{opt.label}</button
            >
          {/each}
        </div>
        <label class="rec-vol">
          <span>Volume</span>
          <input
            class="vol"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={recordingVolume}
            oninput={(e) => onrecordingvolume(Number((e.currentTarget as HTMLInputElement).value))}
          />
        </label>
        <p class="note">The recording is one mix; pick a separated part to hear just that guitar.</p>
      {/if}
    </div>
  {:else if shown === 'help'}
    <div class="pop right" role="dialog" aria-label="Keyboard shortcuts">
      <h2>Keyboard</h2>
      <dl>
        {#each SHORTCUTS as [key, what] (key)}
          <dt><kbd>{key}</kbd></dt>
          <dd>{what}</dd>
        {/each}
      </dl>
      <p class="note">Drag across bars, or shift-click a bar, to pick a loop range.</p>
    </div>
  {:else if shown === 'more' && more}
    <div class="pop right wide" role="dialog" aria-label="More controls">
      {@render more()}
    </div>
  {/if}

  {@render seekStrip()}

  {#if collapsed}
    <div class="mini">
      {@render playButton(false)}
      {#if pending}<span class="hint"><span class="spinner is-on"></span> Loading audio…</span>{/if}
    </div>
  {:else}
    <div class="tiles">
      <div class="group">
        <button
          type="button"
          class="tile"
          class:on={shown === 'mixer'}
          aria-expanded={shown === 'mixer'}
          onclick={() => open('mixer')}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M6 4v16M12 4v16M18 4v16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            <rect x="3.5" y="13" width="5" height="3" rx="1.2" fill="currentColor" />
            <rect x="9.5" y="7" width="5" height="3" rx="1.2" fill="currentColor" />
            <rect x="15.5" y="11" width="5" height="3" rx="1.2" fill="currentColor" />
          </svg>
          <span>Mixer</span>
        </button>

        <div class="tile speed" role="group" aria-label="Speed">
          <div class="stepper">
            <button
              type="button"
              aria-label="Slower"
              disabled={speed <= SPEEDS[0]}
              onclick={() => onspeed(stepSpeed(speed, -1))}>−</button
            >
            <strong>{Math.round(speed * 100)}%</strong>
            <button
              type="button"
              aria-label="Faster"
              disabled={speed >= SPEEDS[SPEEDS.length - 1]}
              onclick={() => onspeed(stepSpeed(speed, 1))}>+</button
            >
          </div>
          <span>Speed</span>
        </div>

        {#if practice}
          <div class="tile loop" class:on={loopOn} role="group" aria-label="A/B loop">
            <div class="stepper">
              <button type="button" title="Loop start at the cursor ([)" onclick={onsetA}>A</button>
              <button
                type="button"
                class="loop-toggle"
                aria-pressed={loopOn}
                aria-label="Loop"
                disabled={!hasLoop}
                title="Loop the selected bars (L)"
                onclick={onloop}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M7 7h9.5a3.5 3.5 0 0 1 0 7H15M17 17H7.5a3.5 3.5 0 0 1 0-7H9M14 11.5 16.5 14 14 16.5M10 12.5 7.5 10 10 7.5"
                    stroke="currentColor"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
              <button type="button" title="Loop end at the cursor (])" onclick={onsetB}>B</button>
            </div>
            <span>Loop</span>
          </div>
        {/if}
      </div>

      {@render playButton(true)}

      <div class="group">
        {#if practice}
          <div class="source" role="radiogroup" aria-label="Audio source">
            <button
              type="button"
              role="radio"
              aria-checked={source === 'recording'}
              class:on={source === 'recording'}
              disabled={!recordingAvailable}
              onclick={() => onsource('recording')}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M4 12h1M8 8v8M12 5v14M16 9v6M20 12h0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              </svg>
              Recording
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={source === 'synth'}
              class:on={source === 'synth'}
              onclick={() => onsource('synth')}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M9 17V6l10-2v11" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
                <circle cx="6.5" cy="17" r="2.5" stroke="currentColor" stroke-width="1.8" />
                <circle cx="16.5" cy="15" r="2.5" stroke="currentColor" stroke-width="1.8" />
              </svg>
              Synth
            </button>
          </div>

          <button
            type="button"
            class="tile"
            class:on={metronome}
            aria-pressed={metronome}
            title="Metronome (M)"
            onclick={onmetronome}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M9 3h6l3.5 18h-13L9 3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
              <path d="M12 16l5-9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
              <path d="M7 16h10" stroke="currentColor" stroke-width="1.6" />
            </svg>
            <span>Click</span>
          </button>

          <button
            type="button"
            class="tile"
            class:on={countIn}
            aria-pressed={countIn}
            title="Count-in (C)"
            onclick={oncountin}
          >
            <span class="count" aria-hidden="true">1·2·3</span>
            <span>Count-in</span>
          </button>
        {/if}

        {#if more}
          <button
            type="button"
            class="tile"
            class:on={shown === 'more'}
            aria-expanded={shown === 'more'}
            onclick={() => open('more')}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <circle cx="5" cy="12" r="1.8" />
              <circle cx="12" cy="12" r="1.8" />
              <circle cx="19" cy="12" r="1.8" />
            </svg>
            <span>More</span>
          </button>
        {/if}

        {#if practice}
          <button
            type="button"
            class="tile narrow"
            class:on={shown === 'help'}
            aria-expanded={shown === 'help'}
            aria-label="Keyboard shortcuts"
            onclick={() => open('help')}
          >
            <span class="count" aria-hidden="true">?</span>
            <span>Keys</span>
          </button>
        {/if}
      </div>
    </div>
    {#if pending}
      <p class="hint"><span class="spinner is-on" aria-hidden="true"></span> Loading audio…</p>
    {:else if !available}
      <p class="hint">Audio not available for this source.</p>
    {/if}
  {/if}
</div>

<style>
  .dock {
    position: fixed;
    left: 50%;
    bottom: var(--space-4);
    transform: translateX(-50%);
    z-index: 20;
    width: min(780px, calc(100vw - var(--space-8)));
    padding: var(--space-2) var(--space-3) var(--space-3);
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 18%, transparent);
    border-radius: var(--radius-3);
    box-shadow:
      var(--shadow-transport),
      0 12px 32px rgba(0, 0, 0, 0.35);
  }
  .dock.collapsed {
    width: min(460px, calc(100vw - var(--space-8)));
  }

  .strip {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  .time {
    flex: 0 0 auto;
    min-width: 36px;
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: var(--fs-1);
    text-align: center;
  }
  .seek {
    flex: 1 1 auto;
    min-width: 0;
    height: 24px;
    margin: 0;
    background: transparent;
    accent-color: var(--accent);
    cursor: pointer;
    -webkit-appearance: none;
    appearance: none;
  }
  .seek::-webkit-slider-runnable-track {
    height: 4px;
    border-radius: 2px;
    background: linear-gradient(
      to right,
      var(--accent) var(--progress),
      color-mix(in srgb, var(--line) 25%, transparent) var(--progress)
    );
  }
  .seek::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 12px;
    height: 12px;
    margin-top: -4px;
    border-radius: 50%;
    background: var(--accent);
  }
  .seek::-moz-range-track {
    height: 4px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--line) 25%, transparent);
  }
  .seek::-moz-range-progress {
    height: 4px;
    border-radius: 2px;
    background: var(--accent);
  }
  .seek::-moz-range-thumb {
    width: 12px;
    height: 12px;
    border: 0;
    border-radius: 50%;
    background: var(--accent);
  }
  .fold {
    flex: 0 0 auto;
    width: 32px;
    height: 32px;
    border: 0;
    border-radius: var(--radius-2);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .fold:hover {
    background: var(--surface-2);
    color: var(--text);
  }

  .mini {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-1);
  }
  .tiles {
    display: flex;
    align-items: stretch;
    justify-content: center;
    gap: var(--space-2);
    margin-top: var(--space-1);
    flex-wrap: wrap;
  }
  .group {
    display: flex;
    align-items: stretch;
    gap: var(--space-2);
    flex: 1 1 0;
    min-width: max-content;
  }
  .group:first-child {
    justify-content: flex-end;
  }
  .group:last-child {
    justify-content: flex-start;
  }

  .play {
    flex: 0 0 auto;
    width: 44px;
    height: 44px;
    border: 0;
    border-radius: var(--radius-2);
    background: var(--accent);
    color: var(--accent-ink);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
    transition: transform var(--motion);
  }
  .play.big {
    width: 72px;
    height: auto;
    min-height: 56px;
    border-radius: var(--radius-3);
  }
  .play:active {
    transform: scale(0.96);
  }
  .play:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .tile {
    min-width: 56px;
    min-height: 56px;
    padding: var(--space-1) var(--space-2);
    border: 0;
    border-radius: var(--radius-2);
    background: var(--bg);
    color: var(--text-secondary);
    cursor: pointer;
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    transition:
      background var(--motion),
      color var(--motion);
  }
  .tile > span:last-child {
    font-size: var(--fs-1);
    line-height: var(--lh-1);
    color: var(--muted);
  }
  button.tile:hover {
    background: var(--surface-2);
    color: var(--text);
  }
  .tile.on {
    background: color-mix(in srgb, var(--accent) 22%, var(--bg));
    color: var(--accent);
  }
  .tile.on > span:last-child {
    color: var(--text);
  }
  .tile.narrow {
    min-width: 44px;
  }
  .count {
    font-family: var(--font-mono);
    font-size: var(--fs-2);
    line-height: 20px;
    font-weight: var(--weight-semibold);
  }
  .stepper {
    display: flex;
    align-items: center;
    gap: 2px;
  }
  .stepper button {
    min-width: 26px;
    height: 26px;
    border: 0;
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--fs-3);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .stepper button:hover:not(:disabled) {
    background: var(--surface-2);
    color: var(--text);
  }
  .stepper button:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .stepper strong {
    min-width: 40px;
    text-align: center;
    font-family: var(--font-mono);
    font-size: var(--fs-2);
    font-weight: var(--weight-semibold);
    color: var(--text);
  }
  .loop.on .loop-toggle {
    color: var(--accent);
  }

  .source {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    padding: 3px;
    border-radius: var(--radius-2);
    background: var(--bg);
  }
  .source button {
    flex: 1 1 0;
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0 var(--space-2);
    border: 0;
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    font-size: var(--fs-1);
    cursor: pointer;
  }
  .source button.on {
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: var(--weight-semibold);
  }
  .source button:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .pop {
    position: absolute;
    bottom: calc(100% + var(--space-2));
    width: min(340px, calc(100vw - var(--space-8)));
    max-height: min(70vh, 560px);
    overflow-y: auto;
    padding: var(--space-4);
    background: var(--surface);
    border: 1px solid color-mix(in srgb, var(--line) 18%, transparent);
    border-radius: var(--radius-3);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .pop.left {
    left: 0;
  }
  .pop.right {
    right: 0;
  }
  .pop.wide {
    width: min(320px, calc(100vw - var(--space-8)));
  }
  .pop h2 {
    font-size: var(--fs-3);
    font-weight: var(--weight-medium);
    color: var(--text);
  }
  .note {
    color: var(--muted);
    font-size: var(--fs-1);
    line-height: var(--lh-1);
  }
  .mix {
    list-style: none;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .mix li {
    display: grid;
    grid-template-columns: 1fr auto auto minmax(72px, 96px);
    align-items: center;
    gap: var(--space-2);
  }
  .mix-name {
    min-height: 36px;
    padding: 0 var(--space-3);
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    text-align: left;
    cursor: pointer;
  }
  .mix li.current .mix-name {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 22%, transparent);
    color: var(--text);
    font-weight: var(--weight-semibold);
  }
  .chip {
    width: 32px;
    height: 32px;
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: var(--fs-2);
    cursor: pointer;
  }
  .chip.on {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 22%, transparent);
    color: var(--text);
  }
  .vol {
    width: 100%;
    accent-color: var(--accent);
    cursor: pointer;
  }
  .listen {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .listen button {
    min-height: 36px;
    padding: 0 var(--space-3);
    border: 1px solid rgba(168, 184, 204, 0.35);
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .listen button.on {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 22%, transparent);
    color: var(--text);
    font-weight: var(--weight-semibold);
  }
  .rec-vol {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: var(--space-3);
    color: var(--muted);
    font-size: var(--fs-2);
  }
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--space-1) var(--space-3);
    font-size: var(--fs-2);
    line-height: var(--lh-2);
  }
  dd {
    color: var(--text-secondary);
  }
  kbd {
    font-family: var(--font-mono);
    color: var(--text);
  }
  .hint {
    margin-top: var(--space-2);
    color: var(--muted);
    font-size: var(--fs-2);
    text-align: center;
  }
  .mini .hint {
    margin: 0;
  }

  @media (max-width: 560px) {
    .dock {
      bottom: var(--space-2);
      width: calc(100vw - var(--space-4));
      padding: var(--space-2);
    }
    .group {
      flex: 1 1 100%;
      justify-content: center !important;
      flex-wrap: wrap;
    }
    .play.big {
      order: -1;
      flex: 1 1 100%;
      min-height: 48px;
    }
  }
</style>
