<script lang="ts">
  let {
    available,
    pending = false,
    playing,
    currentTime,
    duration,
    ontoggle,
    onseek,
  }: {
    available: boolean;
    pending?: boolean;
    playing: boolean;
    currentTime: number;
    duration: number;
    ontoggle: () => void;
    onseek: (time: number) => void;
  } = $props();

  function fmt(sec: number): string {
    if (!Number.isFinite(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }
</script>

{#if available}
  <div class="player">
    <button
      type="button"
      class="play"
      aria-label={playing ? 'Pause' : 'Play'}
      onclick={ontoggle}
    >
      {#if playing}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <rect x="6" y="5" width="4.5" height="14" rx="1" />
          <rect x="13.5" y="5" width="4.5" height="14" rx="1" />
        </svg>
      {:else}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M8 5.5v13a1 1 0 0 0 1.52.86l11-6.5a1 1 0 0 0 0-1.72l-11-6.5A1 1 0 0 0 8 5.5Z" />
        </svg>
      {/if}
    </button>
    <input
      class="seek"
      type="range"
      min="0"
      max={duration || 0}
      step="0.01"
      value={currentTime}
      aria-label="Seek"
      oninput={(e) => onseek(Number((e.currentTarget as HTMLInputElement).value))}
    />
    <span class="time">{fmt(currentTime)} / {fmt(duration)}</span>
  </div>
{:else if pending}
  <p class="muted"><span class="spinner is-on" aria-hidden="true"></span> Loading audio…</p>
{:else}
  <p class="muted">Audio not available for this source.</p>
{/if}

<style>
  .player {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex: 1 1 320px;
    min-width: 0;
  }
  .play {
    flex: 0 0 auto;
    width: 44px;
    height: 44px;
    border: 0;
    border-radius: 50%;
    background: var(--accent);
    color: var(--accent-ink);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
  }
  .seek {
    flex: 1 1 auto;
    min-width: 0;
    accent-color: var(--accent);
    cursor: pointer;
  }
  .time {
    flex: 0 0 auto;
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: var(--fs-2);
    white-space: nowrap;
  }
  .muted {
    color: var(--muted);
  }
</style>
