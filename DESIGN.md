# Tab PDF — Design

The design contract for the desktop front end. The spec is the authority; this
file is the working reference for reviews. Tokens live in
[app/web/src/app.css](app/web/src/app.css) — that file is the source of truth
at build time.

**Spec:** [docs/superpowers/specs/2026-11-18-ui-redesign-design.md](docs/superpowers/specs/2026-11-18-ui-redesign-design.md)
**Audit:** [docs/ui-audit/2026-11-18-ui-ux-audit.md](docs/ui-audit/2026-11-18-ui-ux-audit.md)

## Principles

1. The tab leads. The result screen puts the score first at natural scale;
   settings live in an inspector; feedback comes after the score.
2. Every control is labelled, sized for a human (≥ 44 px), and named in the
   user's vocabulary.
3. One product, one visual world: entry, waiting, result, library.
4. Empty and error states always show a cause and one action.
5. Correctness over filling the panel: `bars_per_line` drives row breaks on
   screen and in the PDF; a short clip reads as one measure, not a fragment.

## Colour

Shared with Audio Tools desktop `HOME_*` tokens (navy / amber). Product
layout stays Tab-PDF-unique.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#192542` | window ground |
| `--surface` | `#2A4467` | cards, score panel, app bar |
| `--surface-2` | `#35557C` | inputs, hover rows |
| `--line` | `#A8B8CC` | 1 px hairlines |
| `--text` | `#F4F7FB` | primary text |
| `--muted` | `#B7C3D4` | secondary text |
| `--accent` | `#F6AD49` | primary action, active view, playhead, focus |
| `--accent-ink` | `#1a1305` | text on accent |
| `--danger` | `#e5534b` | destructive only |
| `--ok` | `#4ea36a` | confirmation only |

One accent. Amber is for the primary button, the active segment, the playhead,
and focus. Nothing else.

## Type

Satoshi (400/500/700) for UI and display (shared with Audio Tools). JetBrains
Mono (400/500) for tab glyphs, timecodes, bar numbers, and key/BPM meta.
Vendored as `.woff2` under `app/web/static/fonts/` (Satoshi under
`fonts/satoshi/`). No CDN at runtime.

| Token | Size / line | Use |
|---|---|---|
| `--fs-1` | 12 / 16 | captions, bar numbers, unit labels |
| `--fs-2` | 13 / 18 | meta, helper text, table cells |
| `--fs-3` | 15 / 22 | body, inputs, buttons |
| `--fs-4` | 18 / 26 | section headings, inspector labels |
| `--fs-5` | 24 / 32 | song title, screen titles |
| `--fs-6` | 34 / 40 | entry promise only |

Body measure ≤ 68 ch. No uppercase-tracked labels. No rendered text below
12 px; no more than six sizes in use.

## Space, shape, motion

Spacing: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 — no arbitrary values. Radii: 4
(inputs, buttons), 8 (cards, score panel), 14 (modals only) — matching Audio
Tools. One shadow, on the pinned transport only. Content max width 1180 px,
32 px gutters, window 1280×860 default / 960×640 minimum; no breakpoints
below 960 px.

Motion (Audio Tools): `--duration-fast` 150 ms, `--duration-base` 220 ms,
`--ease-out` `cubic-bezier(0.22, 1, 0.36, 1)`. Loading uses `home-bar-slide`
indeterminate bar and `.spinner` / `spin`. `prefers-reduced-motion` collapses
durations. Focus: 2 px accent ring at 2 px offset, never removed.

## Component rules

- Every interactive control ≥ 44×44 px; icon buttons get a 44 px hit area even
  when drawn smaller.
- Labels are always visible. No collapsed-label equivalent, ever.
- Numbers carry units: `90 s`, `0.05 s`. No bare sliders.
- Inline icon buttons are the exception only when a visible text label sits
  beside them.
- Score SVG renders inline at intrinsic width (`overflow-x: auto`), never
  `width: 100%`; bar lines at every measure boundary; measure numbers above
  the staff in muted mono 10 px.
- Exports rebuild from the inspector settings into `DATA_DIR/exports/…`; a
  completed run folder is never mutated.

## Copy voice

The copy deck (spec §15) is binding: the promise line, subline, source tiles,
waiting stages and caption, feedback question, depth action, export items, and
empty states are written there. Rules:

- File sizes use one formatter (`4.6 MB`, never `4537.1 KB`).
- Sentences are joined properly (`joinSentence` in `app/web/src/lib/format.ts`).
- Technical internals stay inside the Advanced drawer; no Demucs/threshold
  jargon in default copy.
- No "Soon" inside an action menu. No raw exceptions in banners — a cause
  sentence plus one working action.

## Accessibility

One `h1` per screen; sections are real `h2`/`h3`. The score SVG gets
`role="img"`, a text description, and a link to the Text view; score seeking is
keyboard-operable like the waveform. Roving focus in the source tiles and view
switch. Muted text ≥ 6.8:1. 200% zoom at 960 px must not clip labels. Status
changes are announced through a polite live region (stages, export complete,
errors).

## Screens

Entry (**Transcribe**): app bar → Satoshi promise + one subline → card with
File / YouTube / Media URL tiles, labelled dropzone, Quick setup (Title,
Tuning, Capo), summary line (`First 90 s · no stem separation — Change`),
full-width Convert, then a compact Recent list.

**Waiting**: replaces the card on the same screen — four stages (Prepare,
Separate, Transcribe, Build tab), weighted bar, elapsed time, one tip, and a
working Cancel. Copy says whether separation is on before it starts.

**Result**: app bar with back, display title, mono meta (`Key G · 92 BPM · 1:24`),
Export menu, New. Main column: view switch (Tab / Chords / Piano roll / Text),
score panel, feedback prompt (`Does this sound right? · Yes / Not quite`).
Right inspector (280 px): Tuning, Capo, Transpose, Bars per line, Reset, and
one depth action (`Re-run with stem separation · Adds about 2 minutes`).
Transport pinned to the bottom at 88 px: play, time, waveform with seek +
drag-to-loop, speed, loop, metronome, Original/Stem.

**Library**: rows with title, key/tempo, duration, date; `Open`; `⋯` with
Reveal and Delete (confirm). Empty state: one sentence + one
`Transcribe something` action. No multi-select.
