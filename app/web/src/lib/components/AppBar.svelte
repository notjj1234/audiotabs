<script lang="ts">
  type Screen = 'entry' | 'waiting' | 'result' | 'library';

  let {
    screen,
    onnav,
  }: {
    screen: Screen;
    onnav: (next: Screen) => void;
  } = $props();
</script>

<header class="app-bar">
  <span class="brand">Tab PDF</span>
  <nav class="nav" aria-label="Main">
    <button
      type="button"
      class="nav-button"
      aria-current={screen === 'entry' ? 'page' : undefined}
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
</header>

<style>
  .app-bar {
    display: flex;
    align-items: center;
    gap: var(--space-6);
    max-width: 1180px;
    margin: 0 auto;
    padding: var(--space-3) var(--space-8);
    background: var(--surface);
    border-bottom: 1px solid var(--line);
  }

  .brand {
    font-size: var(--fs-3);
    font-weight: var(--weight-semibold);
  }

  .nav {
    display: flex;
    gap: var(--space-2);
  }

  .nav-button {
    min-height: 44px;
    padding: 0 var(--space-3);
    border: 0;
    border-radius: var(--radius-1);
    background: transparent;
    color: var(--muted);
    font-size: var(--fs-3);
    cursor: pointer;
    transition: color var(--motion), background var(--motion);
  }

  .nav-button:hover {
    color: var(--text);
    background: var(--surface-2);
  }

  .nav-button[aria-current='page'] {
    color: var(--accent);
  }
</style>
