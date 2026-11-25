<script lang="ts">
  type Screen = 'entry' | 'analyzing' | 'instruments' | 'waiting' | 'result' | 'library';

  let {
    screen,
    onnav,
  }: {
    screen: Screen;
    onnav: (next: 'entry' | 'library') => void;
  } = $props();
</script>

<header class="app-bar">
  <div class="inner">
    <div class="brand-wrap">
      <img class="logo" src="/app-icon.png" width="28" height="28" alt="" />
      <span class="brand">Tab PDF</span>
    </div>
    <nav class="nav" aria-label="Main">
      <button
        type="button"
        class="nav-button"
        aria-current={screen !== 'library' ? 'page' : undefined}
        onclick={() => onnav('entry')}
      >
        Transcribe
      </button>
      <button
        type="button"
        class="nav-button"
        aria-current={screen === 'library' ? 'page' : undefined}
        onclick={() => onnav('library')}
      >
        Library
      </button>
    </nav>
  </div>
</header>

<style>
  .app-bar {
    border-bottom: 1px solid color-mix(in srgb, var(--line) 10%, transparent);
    background: var(--bg);
  }

  .inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-6);
    max-width: var(--content-max);
    margin: 0 auto;
    padding: var(--space-2) var(--gutter);
  }

  .brand-wrap {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .logo {
    width: 24px;
    height: 24px;
    border-radius: var(--radius-1);
    display: block;
    object-fit: cover;
    flex-shrink: 0;
  }

  .brand {
    font-size: var(--fs-3);
    font-weight: var(--weight-semibold);
    letter-spacing: -0.02em;
    color: var(--text);
    white-space: nowrap;
  }

  .nav {
    display: flex;
    gap: var(--space-1);
  }

  .nav-button {
    position: relative;
    min-height: 36px;
    padding: 0 var(--space-3);
    border: 0;
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    font-size: var(--fs-2);
    font-weight: var(--weight-medium);
    cursor: pointer;
    transition:
      color var(--motion),
      background var(--motion);
  }

  .nav-button:hover {
    color: var(--text);
    background: var(--surface-2);
  }

  .nav-button[aria-current='page'] {
    color: var(--accent);
  }

  .nav-button[aria-current='page']::after {
    content: '';
    position: absolute;
    left: var(--space-4);
    right: var(--space-4);
    bottom: 6px;
    height: 2px;
    border-radius: 1px;
    background: var(--accent);
  }
</style>
