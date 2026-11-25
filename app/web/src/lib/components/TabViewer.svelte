<script lang="ts">
  import {
    accidental,
    drumStep,
    fitStep,
    grandStaffFor,
    ledgerLines,
    staffStep,
    tabLine,
    type Clef,
  } from '../notation';
  import {
    eventAt,
    fractionInMeasure,
    inLoop,
    measureAt,
    measureMinWidth,
    techniqueLabel,
    timeInMeasure,
    trackKind,
    type LoopRange,
    type TabData,
    type TabTrack,
    type Technique,
  } from '../tabModel';

  let {
    data,
    trackIds,
    time,
    follow,
    loop,
    loopOn,
    onseek,
    onloopselect,
  }: {
    data: TabData;
    /** One id = single part; several = stacked staves sharing bars, cursor and loop. */
    trackIds: string[];
    time: number;
    follow: boolean;
    loop: LoopRange | null;
    loopOn: boolean;
    onseek: (time: number) => void;
    onloopselect: (range: LoopRange) => void;
  } = $props();

  // Vertical geometry (px) shared by markup and styles.
  const BASE_STAFF_TOP = 32;
  const LINE_GAP = 12;
  const HALF = LINE_GAP / 2;
  const GRAND_GAP = 36;
  const STEM = 20;
  const LEAD_IN = 60; // room for tuning / clef + time signature in the first bar

  const LEGATO: Technique[] = ['hammer_on', 'pull_off', 'slide'];

  type Glyph =
    | { type: 'fret'; top: number; text: string }
    | {
        type: 'head';
        top: number;
        sharp: boolean;
        hollow: boolean;
        ledgers: number[];
        ottava?: string | null;
      }
    | { type: 'x'; top: number };
  type Placed = {
    idx: number;
    f: number;
    start: number;
    glyphs: Glyph[];
    rhythm?: { type: string; flags: number; dotted: boolean };
    beamed: boolean;
  };
  type Mark = { label: string; f: number; from?: number };
  type Beam = { left: number; right: number; flags: number };
  type StaveBar = { placed: Placed[]; beams: Beam[]; marks: Mark[] };
  type Bar = { index: number; start: number; end: number; width: number; staves: StaveBar[] };
  type Geometry = {
    kind: 'tab' | 'staff' | 'drums';
    lines: number[];
    linesTop: number;
    linesHeight: number;
    rhythmTop: number;
    height: number;
    names: string[];
    clefs: { label: string; top: number }[];
  };

  let tracks = $derived.by<TabTrack[]>(() => {
    const picked = trackIds
      .map((id) => data.tracks.find((t) => t.id === id))
      .filter((t): t is TabTrack => Boolean(t));
    return picked.length ? picked : data.tracks.slice(0, 1);
  });
  let stacked = $derived(tracks.length > 1);
  // Stacked staves get headroom for their part label above the top line.
  let staffTop = $derived(stacked ? BASE_STAFF_TOP + 12 : BASE_STAFF_TOP);

  function bottomOf(top: number): number {
    return top + 4 * LINE_GAP;
  }

  function geometry(track: TabTrack): Geometry {
    const kind = trackKind(track);
    if (kind === 'tab') {
      const names = track.strings?.length ? track.strings : data.tuning;
      const n = Math.max(1, names.length);
      const lines = Array.from({ length: n }, (_, i) => staffTop + i * LINE_GAP);
      const rhythmTop = staffTop + (n - 1) * LINE_GAP + 8;
      return {
        kind,
        lines,
        linesTop: staffTop,
        linesHeight: (n - 1) * LINE_GAP,
        rhythmTop,
        height: rhythmTop + STEM + 12,
        names: [...names].reverse(),
        clefs: [],
      };
    }
    const five = (top: number) => [0, 1, 2, 3, 4].map((i) => top + i * LINE_GAP);
    if (kind === 'staff' && track.clef === 'grand') {
      const bassTop = bottomOf(staffTop) + GRAND_GAP;
      const rhythmTop = bottomOf(bassTop) + 24;
      return {
        kind,
        lines: [...five(staffTop), ...five(bassTop)],
        linesTop: staffTop,
        linesHeight: bottomOf(bassTop) - staffTop,
        rhythmTop,
        height: rhythmTop + STEM + 12,
        names: [],
        clefs: [
          { label: 'Treble', top: staffTop },
          { label: 'Bass', top: bassTop },
        ],
      };
    }
    const rhythmTop = bottomOf(staffTop) + (kind === 'drums' ? 12 : 24);
    return {
      kind,
      lines: five(staffTop),
      linesTop: staffTop,
      linesHeight: 4 * LINE_GAP,
      rhythmTop,
      height: rhythmTop + STEM + 12,
      names: [],
      clefs: [{ label: kind === 'drums' ? 'Kit' : 'Treble', top: staffTop }],
    };
  }

  let geoms = $derived(tracks.map(geometry));

  function stepTop(staffTop: number, step: number): number {
    return bottomOf(staffTop) - step * HALF;
  }

  function glyphsFor(track: TabTrack, geom: Geometry, ev: TabTrack['events'][number]): Glyph[] {
    const hollow = ev.rhythm?.type === 'half' || ev.rhythm?.type === 'whole';
    if (geom.kind === 'tab') {
      const n = geom.lines.length;
      return ev.notes.map((note) => ({
        type: 'fret' as const,
        top: staffTop + tabLine(note.string, n) * LINE_GAP,
        text: String(note.fret),
      }));
    }
    if (geom.kind === 'drums') {
      return ev.notes
        .filter((note) => note.piece)
        .map((note) => {
          const top = stepTop(staffTop, drumStep(note.piece!));
          return note.piece === 'hihat'
            ? { type: 'x' as const, top }
            : { type: 'head' as const, top, sharp: false, hollow: false, ledgers: [] };
        });
    }
    return ev.notes.map((note) => {
      const clef: Clef = track.clef === 'grand' ? grandStaffFor(note.pitch) : 'treble';
      const noteStaff = clef === 'bass' ? bottomOf(staffTop) + GRAND_GAP : staffTop;
      // Fold notes far outside the staff by octaves (marked 8va/8vb) so they stay in their stave.
      const { step, ottava } = fitStep(staffStep(note.pitch, clef));
      return {
        type: 'head' as const,
        top: stepTop(noteStaff, step),
        sharp: accidental(note.pitch) !== null,
        hollow,
        ledgers: ledgerLines(step).map((s) => stepTop(noteStaff, s)),
        ottava,
      };
    });
  }

  let bars = $derived.by<Bar[]>(() => {
    const out: Bar[] = data.measures.map((m) => ({
      index: m.index,
      start: m.start,
      end: m.end,
      width: 0,
      staves: tracks.map(() => ({ placed: [], beams: [], marks: [] })),
    }));
    tracks.forEach((track, s) => {
      const events = track.events ?? [];
      const beamMembers = new Map<number, Placed[]>();
      events.forEach((ev, idx) => {
        const bar = out[ev.measure];
        if (!bar) return;
        const stave = bar.staves[s];
        const f = fractionInMeasure(bar, ev.start);
        const placed: Placed = {
          idx,
          f,
          start: ev.start,
          glyphs: glyphsFor(track, geoms[s], ev),
          rhythm: ev.rhythm,
          beamed: ev.beam !== undefined,
        };
        stave.placed.push(placed);
        if (ev.beam !== undefined) {
          const list = beamMembers.get(ev.beam) ?? [];
          list.push(placed);
          beamMembers.set(ev.beam, list);
        }
        for (const kind of ev.techniques ?? []) {
          if (LEGATO.includes(kind)) {
            const prev = events[idx - 1];
            const from =
              prev && prev.measure === ev.measure
                ? fractionInMeasure(bar, prev.start)
                : Math.max(0, f - 0.06);
            stave.marks.push({ label: techniqueLabel(kind), f, from });
          } else {
            stave.marks.push({ label: techniqueLabel(kind), f });
          }
        }
      });
      for (const members of beamMembers.values()) {
        if (members.length < 2) continue;
        const bar = out[events[members[0].idx].measure];
        bar.staves[s].beams.push({
          left: members[0].f,
          right: members[members.length - 1].f,
          flags: Math.max(1, Math.min(...members.map((p) => p.rhythm?.flags ?? 1))),
        });
      }
    });
    for (const bar of out) {
      const busiest = Math.max(0, ...bar.staves.map((st) => st.placed.length));
      bar.width = measureMinWidth(busiest) + (bar.index === 0 ? LEAD_IN : 0);
    }
    return out;
  });

  let measureHeight = $derived(geoms.reduce((sum, g) => sum + g.height, 0));
  let activeMeasure = $derived(measureAt(data.measures, time));
  let activeEvents = $derived(tracks.map((track) => eventAt(track.events, data.measures, time)));
  let cursorF = $derived(
    data.measures[activeMeasure] ? fractionInMeasure(data.measures[activeMeasure], time) : 0,
  );
  let loopA = $derived(loop ? Math.min(loop.a, loop.b) : -1);
  let loopB = $derived(loop ? Math.max(loop.a, loop.b) : -1);
  // Pointer: click seeks, drag across bars (or shift+click) selects an A/B loop range.
  let anchor: number | null = null;
  let dragged = false;

  function onPointerDown(ev: PointerEvent, index: number) {
    if (ev.button !== 0) return;
    // Let touch drags reach neighbouring bars.
    (ev.target as Element).releasePointerCapture?.(ev.pointerId);
    if (ev.shiftKey) {
      onloopselect({ a: loop?.a ?? activeMeasure, b: index });
      anchor = null;
      return;
    }
    anchor = index;
    dragged = false;
  }

  function onPointerEnter(index: number) {
    if (anchor === null || index === anchor) return;
    dragged = true;
    onloopselect({ a: anchor, b: index });
  }

  function onPointerUp(ev: PointerEvent, index: number) {
    if (anchor !== index || dragged) {
      anchor = null;
      return;
    }
    anchor = null;
    const target = (ev.target as HTMLElement).closest<HTMLElement>('[data-t]');
    if (target?.dataset.t) {
      onseek(Number(target.dataset.t));
      return;
    }
    const area = (ev.currentTarget as HTMLElement).querySelector<HTMLElement>('.notes');
    const bar = data.measures[index];
    if (!area || !bar) return;
    const rect = area.getBoundingClientRect();
    const f = rect.width > 0 ? (ev.clientX - rect.left) / rect.width : 0;
    onseek(timeInMeasure(bar, f));
  }

  function onKey(ev: KeyboardEvent, index: number) {
    if (ev.key !== 'Enter') return;
    ev.preventDefault();
    const bar = data.measures[index];
    if (bar) onseek(bar.start);
  }

  $effect(() => {
    const end = () => (anchor = null);
    window.addEventListener('pointerup', end);
    return () => window.removeEventListener('pointerup', end);
  });

  /** Nearest ancestor that actually scrolls (the score panel or the page). */
  function scrollParent(node: HTMLElement): HTMLElement {
    for (let el = node.parentElement; el; el = el.parentElement) {
      const style = getComputedStyle(el);
      if (/(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 1) return el;
    }
    return (document.scrollingElement as HTMLElement) ?? document.documentElement;
  }

  // Follow playback: when the cursor moves to a new line, bring that line near the top.
  let sheet = $state<HTMLDivElement | null>(null);
  let followedTop = -1;
  $effect(() => {
    const index = activeMeasure;
    if (!follow || !sheet) {
      followedTop = -1;
      return;
    }
    const el = sheet.querySelector<HTMLElement>(`[data-m="${index}"]`);
    if (!el) return;
    const scroller = scrollParent(sheet);
    const isPage = scroller === document.scrollingElement;
    const viewTop = isPage ? 0 : scroller.getBoundingClientRect().top;
    const viewHeight = isPage ? window.innerHeight : scroller.clientHeight;
    const top = el.getBoundingClientRect().top - viewTop + scroller.scrollTop;
    if (Math.abs(top - followedTop) < 4) return;
    followedTop = top;
    const reduce =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    scroller.scrollTo({
      top: Math.max(0, top - viewHeight * 0.2),
      behavior: reduce ? 'auto' : 'smooth',
    });
  });
</script>

<div
  class="sheet"
  bind:this={sheet}
  style:--staff-top="{staffTop}px"
  style:--line-gap="{LINE_GAP}px"
  style:--stem="{STEM}px"
  style:--lead-in="{LEAD_IN}px"
  style:--measure-h="{measureHeight}px"
>
  {#each bars as bar (bar.index)}
    <div
      class="measure"
      class:first={bar.index === 0}
      class:last={bar.index === bars.length - 1}
      class:active={bar.index === activeMeasure}
      class:looped={inLoop(loop, bar.index)}
      class:loop-on={loopOn && inLoop(loop, bar.index)}
      data-m={bar.index}
      style:flex="{bar.width} 1 {bar.width}px"
      role="button"
      tabindex="0"
      aria-label="Measure {bar.index + 1}"
      onpointerdown={(e) => onPointerDown(e, bar.index)}
      onpointerenter={() => onPointerEnter(bar.index)}
      onpointerup={(e) => onPointerUp(e, bar.index)}
      onkeydown={(e) => onKey(e, bar.index)}
    >
      <span class="num">{bar.index + 1}</span>
      {#if bar.index === loopA}<span class="ab a">A</span>{/if}
      {#if bar.index === loopB}<span class="ab b">B</span>{/if}

      {#each bar.staves as stave, s (tracks[s].id)}
        {@const geom = geoms[s]}
        <div
          class="stave"
          class:split={s > 0}
          class:first-stave={s === 0}
          data-kind={geom.kind}
          style:height="{geom.height}px"
          style:--lines-top="{geom.linesTop}px"
          style:--lines-h="{geom.linesHeight}px"
          style:--rhythm-top="{geom.rhythmTop}px"
        >
          {#if bar.index === 0}
            {#if s === 0}
              <span class="tempo">
                <span aria-hidden="true">♩</span> = {Math.round(data.tempo_bpm)}{#if data.capo}
                  · Capo {data.capo}{/if}
              </span>
            {/if}
            {#if stacked}<span class="part-label">{tracks[s].label}</span>{/if}
            <div
              class="lead-in"
              aria-label={geom.kind === 'tab'
                ? `${tracks[s].label}, tuning ${geom.names.slice().reverse().join(' ')}`
                : tracks[s].label}
            >
              {#each geom.names as name, line (line)}
                <span class="tune" style:top="{staffTop + line * LINE_GAP}px">{name}</span>
              {/each}
              {#each geom.clefs as clef (clef.top)}
                <span class="clef" style:top="{clef.top + 2 * LINE_GAP}px">{clef.label}</span>
              {/each}
              <span
                class="sig"
                style:top="{geom.linesTop + geom.linesHeight / 2 - LINE_GAP}px"
                aria-label="Time signature {data.beats_per_measure}/4"
              >
                <span>{data.beats_per_measure}</span><span>4</span>
              </span>
            </div>
            {#if tracks[s].empty_reason}
              <span class="empty" style:top="{geom.linesTop + geom.linesHeight / 2}px"
                >{tracks[s].empty_reason}</span
              >
            {/if}
          {/if}

          <div class="staff" aria-hidden="true">
            {#each geom.lines as top, line (line)}
              <span class="line" style:top="{top}px"></span>
            {/each}
          </div>

          <div class="notes">
            {#each stave.marks as mark, k (k)}
              {#if mark.from !== undefined}
                <span
                  class="arc"
                  style:left="{mark.from * 100}%"
                  style:width="{Math.max(0.02, mark.f - mark.from) * 100}%"
                ></span>
              {/if}
              <span
                class="mark"
                style:left="{(mark.from !== undefined ? (mark.from + mark.f) / 2 : mark.f) * 100}%"
                >{mark.label}</span
              >
            {/each}

            {#each stave.placed as p (p.idx)}
              {#each p.glyphs as glyph, k (k)}
                {#if glyph.type === 'fret'}
                  <span
                    class="fret"
                    class:on={p.idx === activeEvents[s]}
                    data-t={p.start}
                    style:left="{p.f * 100}%"
                    style:top="{glyph.top}px">{glyph.text}</span
                  >
                {:else}
                  {#if glyph.type === 'head'}
                    {#each glyph.ledgers as ledger (ledger)}
                      <span class="ledger" style:left="{p.f * 100}%" style:top="{ledger}px"
                      ></span>
                    {/each}
                  {/if}
                  <span
                    class={glyph.type === 'x' ? 'xhead' : 'head'}
                    class:hollow={glyph.type === 'head' && glyph.hollow}
                    class:on={p.idx === activeEvents[s]}
                    data-t={p.start}
                    style:left="{p.f * 100}%"
                    style:top="{glyph.top}px"
                  ></span>
                  {#if glyph.type === 'head' && glyph.ottava}
                    <span class="ottava" style:left="{p.f * 100}%" style:top="{glyph.top}px"
                      >{glyph.ottava}</span
                    >
                  {/if}
                  {#if glyph.type === 'head' && glyph.sharp}
                    <span class="sharp" style:left="{p.f * 100}%" style:top="{glyph.top}px"
                      >♯</span
                    >
                  {/if}
                {/if}
              {/each}
              {#if p.rhythm && p.rhythm.type !== 'whole'}
                <span
                  class="stem"
                  class:short={p.rhythm.type === 'half'}
                  style:left="{p.f * 100}%"
                ></span>
                {#if !p.beamed}
                  {#each Array(p.rhythm.flags) as _, layer (layer)}
                    <span class="flag" style:left="{p.f * 100}%" style:--layer={layer}></span>
                  {/each}
                {/if}
                {#if p.rhythm.dotted}
                  <span class="dot" style:left="{p.f * 100}%"></span>
                {/if}
              {/if}
            {/each}

            {#each stave.beams as beam, k (k)}
              {#each Array(beam.flags) as _, layer (layer)}
                <span
                  class="beam"
                  style:left="{beam.left * 100}%"
                  style:width="{(beam.right - beam.left) * 100}%"
                  style:--layer={layer}
                ></span>
              {/each}
            {/each}

            {#if bar.index === activeMeasure}
              <span class="cursor" style:left="{cursorF * 100}%" aria-hidden="true"></span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/each}
  <span class="filler" aria-hidden="true"></span>
</div>

<style>
  .sheet {
    --tab-bg: color-mix(in srgb, var(--art) 72%, var(--surface));
    --tab-line: color-mix(in srgb, var(--line) 50%, transparent);
    display: flex;
    flex-wrap: wrap;
    row-gap: var(--space-4);
    padding-bottom: var(--space-16);
    user-select: none;
    -webkit-user-select: none;
  }
  .filler {
    flex: 9999 1 0;
  }
  .measure {
    --m-bg: var(--tab-bg);
    position: relative;
    display: flex;
    flex-direction: column;
    background: var(--m-bg);
    cursor: pointer;
    min-width: 0;
    touch-action: pan-y;
    /* Long songs × several staves: skip layout/paint for bars far off screen. */
    content-visibility: auto;
    contain-intrinsic-size: auto var(--measure-h);
  }
  .stave {
    position: relative;
  }
  .stave.split {
    border-top: 1px dashed color-mix(in srgb, var(--line) 18%, transparent);
  }
  .part-label {
    position: absolute;
    left: var(--space-2);
    top: var(--space-1);
    font-size: var(--fs-1);
    line-height: var(--lh-1);
    color: var(--text-secondary);
    white-space: nowrap;
    z-index: 1;
  }
  .stave.first-stave .part-label {
    top: var(--space-4);
  }
  .clef {
    position: absolute;
    left: var(--space-2);
    transform: translateY(-50%);
    font-size: var(--fs-1);
    line-height: 1;
    color: var(--muted);
  }
  .empty {
    position: absolute;
    left: calc(var(--lead-in) + var(--space-4));
    transform: translateY(-50%);
    font-size: var(--fs-2);
    color: var(--text-secondary);
    white-space: nowrap;
    background: var(--m-bg);
    padding: 0 var(--space-1);
    z-index: 1;
  }
  .measure.looped {
    --m-bg: color-mix(in srgb, var(--accent) 10%, var(--tab-bg));
  }
  .measure.loop-on {
    --m-bg: color-mix(in srgb, var(--accent) 18%, var(--tab-bg));
  }
  .measure.active {
    --m-bg: color-mix(in srgb, var(--accent) 7%, var(--tab-bg));
  }
  .measure.active.looped {
    --m-bg: color-mix(in srgb, var(--accent) 22%, var(--tab-bg));
  }
  .measure:focus-visible {
    outline-offset: -2px;
  }
  .num {
    position: absolute;
    left: var(--space-1);
    top: 0;
    font-family: var(--font-mono);
    font-size: var(--fs-1);
    line-height: var(--lh-1);
    color: var(--muted);
  }
  .ab {
    position: absolute;
    top: 0;
    font-family: var(--font-mono);
    font-size: var(--fs-1);
    line-height: var(--lh-1);
    font-weight: var(--weight-semibold);
    color: var(--accent);
  }
  .ab.a {
    left: calc(var(--space-6) + var(--space-1));
  }
  .ab.b {
    right: var(--space-1);
  }
  .tempo {
    position: absolute;
    left: calc(var(--lead-in) - var(--space-2));
    top: 0;
    font-family: var(--font-mono);
    font-size: var(--fs-1);
    line-height: var(--lh-1);
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .lead-in {
    position: absolute;
    left: 0;
    top: 0;
    width: var(--lead-in);
    height: 100%;
  }
  .tune {
    position: absolute;
    left: var(--space-2);
    transform: translateY(-50%);
    font-family: var(--font-mono);
    font-size: var(--fs-1);
    line-height: 1;
    color: var(--muted);
  }
  .sig {
    position: absolute;
    left: calc(var(--space-6) + var(--space-2));
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: var(--font-display);
    font-size: var(--fs-5);
    line-height: calc(var(--line-gap) * 2);
    font-weight: var(--weight-medium);
    color: var(--text);
  }
  .staff {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
  .staff::before,
  .measure.last .staff::after {
    content: '';
    position: absolute;
    top: var(--lines-top);
    height: calc(var(--lines-h) + 1px);
    width: 1px;
    background: var(--tab-line);
  }
  .staff::before {
    left: 0;
  }
  .measure.last .staff::after {
    right: 0;
  }
  .line {
    position: absolute;
    left: 0;
    right: 0;
    height: 1px;
    background: var(--tab-line);
  }
  .notes {
    position: absolute;
    top: 0;
    bottom: 0;
    left: var(--space-4);
    right: var(--space-4);
  }
  .measure.first .notes {
    left: calc(var(--lead-in) + var(--space-2));
  }
  .fret {
    position: absolute;
    transform: translate(-50%, -50%);
    padding: 0 2px;
    background: var(--m-bg);
    font-family: var(--font-mono);
    font-size: var(--fs-3);
    line-height: var(--lh-1);
    font-weight: var(--weight-semibold);
    color: var(--text);
    transition: color var(--motion);
  }
  .fret.on {
    color: var(--accent);
  }
  .head,
  .xhead {
    position: absolute;
    width: 10px;
    height: 8px;
    transform: translate(-50%, -50%);
    transition:
      background-color var(--motion),
      border-color var(--motion);
  }
  .head {
    border-radius: 50%;
    background: var(--text);
    rotate: -20deg;
  }
  .head.hollow {
    background: var(--m-bg);
    border: 1.5px solid var(--text);
  }
  .head.on {
    background: var(--accent);
  }
  .head.hollow.on {
    background: var(--m-bg);
    border-color: var(--accent);
  }
  .xhead::before,
  .xhead::after {
    content: '';
    position: absolute;
    left: 50%;
    top: 50%;
    width: 11px;
    height: 1.5px;
    background: var(--text);
    translate: -50% -50%;
    rotate: 45deg;
  }
  .xhead::after {
    rotate: -45deg;
  }
  .xhead.on::before,
  .xhead.on::after {
    background: var(--accent);
  }
  .sharp {
    position: absolute;
    transform: translate(calc(-50% - 13px), -50%);
    font-size: var(--fs-3);
    line-height: 1;
    color: var(--text);
  }
  /* Notation staves name their clef in words; the time signature sits after it. */
  .stave:not([data-kind='tab']) .sig {
    left: calc(var(--lead-in) - var(--space-3));
  }
  .ottava {
    position: absolute;
    transform: translate(-50%, calc(-50% - 13px));
    font-family: var(--font-mono);
    font-size: var(--fs-1);
    line-height: 1;
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .ledger {
    position: absolute;
    width: 18px;
    height: 1px;
    transform: translateX(-50%);
    background: var(--tab-line);
  }
  .mark {
    position: absolute;
    top: calc(var(--staff-top) - 22px);
    transform: translateX(-50%);
    font-family: var(--font-mono);
    font-size: var(--fs-1);
    line-height: var(--lh-1);
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .arc {
    position: absolute;
    top: calc(var(--staff-top) - 8px);
    height: 6px;
    border: 1px solid var(--text-secondary);
    border-bottom: 0;
    border-radius: 6px 6px 0 0;
  }
  .stem,
  .flag,
  .beam,
  .dot {
    position: absolute;
    background: var(--text-secondary);
    pointer-events: none;
  }
  .stem {
    top: var(--rhythm-top);
    width: 1px;
    height: var(--stem);
  }
  .stem.short {
    height: calc(var(--stem) / 2);
  }
  .flag {
    top: calc(var(--rhythm-top) + var(--stem) - 6px - var(--layer) * 5px);
    width: 7px;
    height: 1.5px;
    transform-origin: left center;
    transform: rotate(-35deg);
  }
  .beam {
    top: calc(var(--rhythm-top) + var(--stem) - 3px - var(--layer) * 5px);
    height: 3px;
  }
  .dot {
    top: calc(var(--rhythm-top) + var(--stem) - 4px);
    width: 3px;
    height: 3px;
    margin-left: 4px;
    border-radius: 50%;
  }
  .cursor {
    position: absolute;
    top: calc(var(--lines-top) - 10px);
    height: calc(var(--lines-h) + 20px);
    width: 2px;
    margin-left: -1px;
    background: var(--accent);
    border-radius: 1px;
    box-shadow: 0 0 6px color-mix(in srgb, var(--accent) 65%, transparent);
    pointer-events: none;
  }
</style>
