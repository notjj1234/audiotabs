<script lang="ts">
  import { getToken } from './lib/api';
  import AppBar from './lib/components/AppBar.svelte';
  import Library from './lib/screens/Library.svelte';

  type Screen = 'entry' | 'waiting' | 'result' | 'library';

  let screen = $state<Screen>('entry');

  // Consume the launch token from the URL fragment on boot.
  getToken();
</script>

<AppBar {screen} onnav={(next) => (screen = next)} />
<main class="content">
  {#if screen === 'library'}
    <Library ontranscribe={() => (screen = 'entry')} />
  {:else}
    <section class="promise">
      <h1>Turn a recording into guitar tab.</h1>
      <p>
        Drop an audio file or paste a YouTube link. You get tab, chords, and a practice player in
        about 90 seconds.
      </p>
    </section>
  {/if}
</main>

<style>
  .content {
    max-width: 1180px;
    margin: 0 auto;
    padding: var(--space-8);
  }

  .promise {
    max-width: 68ch;
  }

  .promise h1 {
    font-family: var(--font-display);
    font-size: var(--fs-6);
    line-height: var(--lh-6);
    letter-spacing: -0.01em;
    font-weight: 400;
    margin-bottom: var(--space-4);
  }

  .promise p {
    color: var(--muted);
    font-size: var(--fs-4);
    line-height: var(--lh-4);
  }
</style>
