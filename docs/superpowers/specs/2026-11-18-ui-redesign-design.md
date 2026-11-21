# Tab PDF — designed desktop front end

**Status:** draft for partner approval (2026-11-18)
**Supersedes:** the Streamlit portions of `2026-11-10-studio-ui-design.md`
**Evidence:** `docs/ui-audit/2026-11-18-ui-ux-audit.md`, `.superpowers/ui-audit/`

---

## 1. Intent

Tab PDF's engine is good and its practice player is the differentiator. The
interface around them is the weakest part of the product: Streamlit's default
font, its stock widgets, a 1,101-line CSS override file, a tab that starts below
the fold, and labels hidden by a single rule.

Replace the Streamlit front end with a designed desktop interface on the same
Python engine. One shell, one type system, one visual language, and an order
that puts the tab where the user looks first.

**Why now:** the audit scored the surface 22/40 (Acceptable). Every remaining
point is capped by Streamlit itself — typography, widget chrome, layout order,
and the rerun-loop state model. Restyling harder does not raise the ceiling.

---

## 2. What exists today (grounding)

- `ui/app.py` is the Streamlit entrypoint; `ui/tab_pdf.py` renders entry
  (lines ~941–1700) and result (~587–940); `ui/studio_theme.py` holds 1,101
  lines of CSS keyed to Streamlit internals.
- `run_pipeline()` (`src/audio_to_tab/pipeline.py:222`) is synchronous, takes a
  `PipelineConfig`, and reports progress through an `on_progress` callback. The
  UI blocks the Streamlit script for the whole run; there is no cancel.
- Runs persist as folders under `DATA_DIR` with `_META_FILENAME` metadata
  (`ui/common.py:167–236`), so completed work already survives a restart.
- `src/audio_to_tab/player_bar.py` builds a custom waveform/transport in HTML +
  JS. `src/audio_to_tab/notation_view.py` builds staff, roll, and chord SVGs in
  Python.
- `packaging/launcher.py` opens a pywebview window (1280×860 default,
  960×640 minimum) pointed at a local Streamlit server.
- The entry accepts **four** sources: uploaded file, YouTube, a direct **Media
  URL** (`download_direct_media`), and the demo pack. "Trim start" is a
  pre-pipeline ffmpeg trim, not a `PipelineConfig` field.
- The Advanced drawer exposes engine selection, guitar-ft weights, and an
  Expert section (mix-aware, tempo override, onset/frame thresholds, low-end
  restore, de-bleed, bleed gate, adaptive fold gain, ensemble).
- No font file exists in the repo; the computed stack is
  `"Source Sans", sans-serif`.

---

## 3. Goals

1. A designed interface with real typography, a token system, and one visual
   world across entry, waiting, result, and library.
2. The tab is the first thing on the result screen and is rendered at natural
   scale with bar lines and measure numbers above the staff.
3. Every control has a visible label, ≥44 px target, and a name a first-timer
   understands.
4. The result screen leads with tab + transport; settings sit in an inspector;
   feedback comes after the score.
5. Real async jobs: progress streamed to the client, cancel that works, and a
   seam for re-runs (stem separation) without "start over".
6. Depth actions do what they say: re-run with separation, direct GP5 download.
7. No Streamlit at runtime, and no CSS keyed to another product's DOM.
8. **Parity means today's controls, not every dataclass field.** Every input
   reachable in the current UI survives. Fields with no UI today
   (`demucs_device`, `demucs_segment`, `demucs_jobs`, `fold_other_mode`,
   `minimum_note_length_ms`, `min_velocity`, `min_duration_sec`,
   `quantize_sec`, `max_notes_per_onset`, `beats_per_measure`, `beat_model`,
   `auto_meter`, `export_gp5`) are **not** newly exposed; that would be engine
   surgery, which §4 rules out.

**Success is measurable on the audit's own rubric:** Design Health Score ≥ 32/40,
tab fully visible above the fold at 1280×860, zero hidden labels, 0 interactive
targets under 44 px, one font family for UI text, one accent colour.

---

## 4. Non-goals

- Changing transcription, separation, beat, or export behaviour beyond the
  score-rendering fixes in §13.
- New engines, cloud processing, accounts, telemetry, or sync.
- Light theme, theme switcher, or user-selectable fonts.
- Mobile layout. The window minimum is 960×640; 200% zoom must still work.
- Rewriting the PDF/GP5/MIDI builders. They stay server-side and unchanged.
- Reworking the progress checklist's stage weights or tips.
- Polishing the Streamlit UI in parallel. It is replaced, not improved.

## 5. Anti-goals

- Fake depth actions, or a banner that repeats its own buttons as bullets.
- Machine output shown as user copy (`4537.1 KB Duration about 4:50.`).
- Hiding labels to make a control "look clean".
- A second accent, glow, gradient text, or glass panels.
- Decorative cards, dashboards of stat tiles, or empty hero space.
- Shipping a "shell" that loses Advanced controls, YouTube, or the sample pack.

---

## 6. Constraints

- Python `>=3.10,<3.13`, local-only processing, no network at runtime.
- Keep `run_pipeline`, `PipelineConfig`, `write_run_metadata`, `DATA_DIR`, and
  the existing artifact names. Server code adapts to them; it does not fork
  them.
- Keep the pywebview shell. It still owns the window, icon, and shutdown.
- New runtime deps limited to `fastapi`, `uvicorn`, `python-multipart`.
  Node/npm are build-time only and never required by an installed app.
- Fonts must be vendored `.woff2` files (SIL OFL) inside the repo. No CDN.
- The window is a desktop app: content max width 1180 px, 32 px gutters, no
  responsive breakpoints below 960 px.
- **Frozen builds are out of scope.** This work ends at `make desktop` from
  source with a built `app/web/dist`. Asset paths must resolve through an
  `_MEIPASS`-safe helper so an external packaging step only has to copy the
  `dist/` folder; no PyInstaller spec is added here.

---

## 7. Decisions the partner made (2026-11-18)

1. **Exit route: B** — custom front end on the same Python engine, inside the
   existing pywebview shell.
2. **Result leads with the tab and the player**, not with settings.
3. **Keep the brass-on-charcoal identity** (`#0f1115` / `#171a21` / `#e8a317`)
   and give it real typography instead of replacing the palette.
4. **First pass fixes labels and order** before broad visual polish.

Decision 4 is honoured by sequencing, not by double work: M1 delivers the
corrected labels and order **in the new shell**. Streamlit is not polished a
second time.

---

## 8. Approaches considered

| # | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | Restyle Streamlit in place | 2–4 days; fixes nothing structural. Stock widgets, rerun loop, and injected font stack remain; CSS breaks on upgrades | Rejected: cannot reach a designed surface |
| B | **FastAPI job API + custom web UI in pywebview** | ~3–4 weeks of focused work; adds a build step and one new runtime package group. Full control of type, layout, state, cancel | **Chosen** |
| C | Python-native desktop UI (PySide6 or NiceGUI) | No JS build; PySide6 needs a full widget theme and loses the web player; NiceGUI's defaults are another framework to fight | Rejected: either heavier or the same theming problem |

B is the only route where the thing the audit scored lowest — typography,
hierarchy, order, and widget chrome — becomes fully authorable, and where the
existing custom player and SVG renderers carry over intact.

---

## 9. Architecture

### 9.1 Processes

```
pywebview window
  └─ http://127.0.0.1:<port>/
       └─ FastAPI (app/server)
            ├─ static: built front end (app/web/dist)
            ├─ api: uploads, jobs, runs, score, export, youtube
            └─ JobManager
                 ├─ ThreadPoolExecutor(max_workers=1)  ← one conversion at a time
                 │    └─ run_pipeline(..., on_progress=emit)
                 └─ in-memory job registry + per-job event ring buffer
```

`packaging/launcher.py` starts uvicorn instead of Streamlit and opens the same
window. A launch token is generated per run and required on `/api/*`.

### 9.2 Repository layout (call)

```
app/
  server/
    main.py          # FastAPI app, static mount, token gate, health
    jobs.py          # JobManager, JobRecord, cancel, SSE buffer
    routes_jobs.py   # POST /api/jobs, GET events, POST cancel
    routes_runs.py   # list/get/delete/score/audio/export/rerun
    routes_sources.py# uploads, youtube search, samples
    errors.py        # maps user_errors -> {code, message, hint, action}
  web/
    index.html
    src/             # Svelte 5 + TypeScript
      app.css        # tokens only
      lib/…          # components (§11)
    static/fonts/    # Instrument Sans, Instrument Serif, JetBrains Mono
    dist/            # build output, git-ignored
```

`ui/` and `tests/test_studio_ui.py`, `tests/test_result_studio.py` are removed
at M4. New tests live in `tests/test_api_*.py`.

### 9.3 Front-end stack (call)

**Svelte 5 + Vite + TypeScript.** It compiles to a small bundle, styles with
plain CSS (so the token file is the source of truth), has built-in transitions
for the 120 ms state changes, and avoids a virtual-DOM runtime for a
single-window app. Node is used only by `make ui-build`; the packaged app ships
`dist/`.

Dev flow: `make dev-api` (FastAPI on 8533) + `make dev-web` (Vite on 5173,
proxying `/api`). Production flow: `make ui-build` then the launcher.

**Streaming (call):** the client consumes SSE with `fetch` and a
`ReadableStream`, not `EventSource`, because `EventSource` cannot send the
`X-Tab-Token` header. If streaming fails, it falls back to
`GET /api/jobs/{id}` every 500 ms. Same state shape, no second design.

### 9.4 Token gate (call)

Launcher generates a 32-byte token, passes it in the initial URL fragment,
and the client keeps it in memory and sends `X-Tab-Token`. `/api/*` rejects
anything else. Server binds `127.0.0.1` only and sends no CORS headers. Static
assets stay readable; they contain no data.

---

## 10. Information architecture

### 10.1 Entry — "Transcribe"

```
┌ app bar ──────────────────────────────────────────────┐
│ Tab PDF            Transcribe   Library               │
├───────────────────────────────────────────────────────┤
│  Turn a recording into guitar tab.        (serif 34)  │
│  Drop an audio file or paste a YouTube link. You get  │
│  tab, chords, and a practice player in about 90 s.    │
│                                                       │
│  ┌ card ──────────────────────────────────────────┐   │
│  │ [File]  [YouTube]  [Media URL]   (3 tiles)     │   │
│  │                                                │   │
│  │ Drop an audio file here          (dropzone)    │   │
│  │ MP3, WAV, M4A, FLAC · up to 200 MB             │   │
│  │ Try a sample tab                               │   │
│  │                                                │   │
│  │ Quick setup                                    │   │
│  │  Title        [ Song title                ]    │   │
│  │  Tuning       [ Standard (EADGBE)      ▾ ]     │   │
│  │  Capo         [ − ] 0 [ + ]                    │   │
│  │                                                │   │
│  │  First 90 s · no stem separation        Change │   │
│  │                                                │   │
│  │            [        Convert        ]  (44 px)  │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  Recent                                               │
│  Am I Wrong — key G · 92 BPM · 2 days ago      Open   │
└───────────────────────────────────────────────────────┘
```

Order fixes: the promise line replaces the bare wordmark, the sample action
moves inside the card as a quiet link, every field is labelled,
Length/Separation collapse into one summary line with a `Change` disclosure,
and Recent becomes a compact list with one row action (`Open`) plus a context
menu (`Reveal`, `Delete`). Media URL stays as a first-class source because it
ships today; it is a text field in the chosen source panel, not a fourth
screen.

### 10.2 Waiting — replaces the card, same screen

Four stages: **Prepare · Separate · Transcribe · Build tab**. Weighted bar,
elapsed time, one short tip, `Cancel` as a secondary button. No form remnants,
no caveat paragraphs. If separation is on, the copy says so before it starts.

### 10.3 Result — "song"

```
┌ app bar ────────────────────────────────────────────────────────┐
│ ←   Am I Wrong        Key G · 92 BPM · 1:24      [Export ▾] New │
├──────────────────────────────────────────────┬──────────────────┤
│  [ Tab ] Chords  Piano roll  Text            │  Tuning          │
│                                              │  [Standard ▾]    │
│  ┌ score panel ────────────────────────────┐ │  Capo            │
│  │  1        2        3        4           │ │  [−] 0 [+]       │
│  │  ═══════════════════════════════════    │ │  Transpose       │
│  │  ───────────────────────────────────    │ │  [−] 0 [+]       │
│  │  ───────────────────────────────────    │ │  Bars per line   │
│  │  0   3   5    …                         │ │  [−] 4 [+]       │
│  └─────────────────────────────────────────┘ │  Reset           │
│                                              │                  │
│  Does this sound right?  Yes   Not quite     │  Go deeper       │
│                                              │  Re-run with     │
│                                              │  stem separation │
│                                              │  (adds ~2 min)   │
├──────────────────────────────────────────────┴──────────────────┤
│ ▶  0:00 / 1:24  ▁▂▅▇▅▂▁ waveform ▂▅▇  ⏱  0.5×  ↻  ♩  Original │
└─────────────────────────────────────────────────────────────────┘
```

- **Score first.** It sits directly under the app bar, inside the main column,
  at natural scale. If a tab is wider than the column it scrolls horizontally;
  it is never scaled up past 1×. "Above the fold" means the first score row and
  the row containing the playhead are visible at 1280×860 without scrolling;
  the panel grows downward and the page scrolls under the pinned transport.
- **View switch** above the score, right-aligned; remembered per song.
- **Transport** pinned to the bottom of the window at 88 px, full width, so it
  never leaves the screen.
- **Inspector** (280 px) holds Tuning, Capo, Transpose, Bars per line, Reset,
  and the single depth action. Changes rerender the score after a 150 ms
  debounce and update the export signature.
- **Feedback** asks once, after the score: `Yes` / `Not quite`. The answer is
  stored with the run, so it is never asked twice. `Not quite` also reveals one
  hint — "Try a cleaner, solo-guitar section" — with no free-text field.
- **Export** is a real menu: PDF, GP5, MIDI, Tab text. GP5 downloads directly
  when available and says why when it is not. No "in the Downloads menu".
- **Go deeper** is one action that starts a real job seeded from the original
  source and config, with the added time stated.

### 10.4 Library

Rows: title, key/tempo, duration, created date, `Open` primary, `⋯` menu with
`Reveal in Finder` and `Delete` (confirm). Empty state: one sentence and one
`Transcribe something` action. No checkbox multi-select until a batch action
exists.

---

## 11. Visual system

### 11.1 Colour (kept from the current identity)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0f1115` | window ground |
| `--surface` | `#171a21` | cards, score panel, app bar |
| `--surface-2` | `#1d2129` | inputs, hover rows |
| `--line` | `#2a2f3a` | 1 px hairlines, staff ink |
| `--text` | `#e8eaef` | primary text |
| `--muted` | `#9aa3b2` | secondary text (≥6.8:1 on surface) |
| `--accent` | `#e8a317` | primary action, active view, playhead |
| `--accent-ink` | `#1a1305` | text on accent |
| `--danger` | `#e5534b` | destructive only |
| `--ok` | `#4ea36a` | confirmation only |

One accent. Brass is for the primary button, the active segment, the playhead,
and focus. Nothing else.

### 11.2 Type

- **Instrument Sans** (variable, 450/620) — UI, labels, body.
- **Instrument Serif** (400) — the entry promise and the song title only.
- **JetBrains Mono** (400/500) — tab glyphs, timecodes, bar numbers, key/BPM.

Six sizes, no more:

| Token | Size / line | Use |
|---|---|---|
| `--fs-1` | 12 / 16 | captions, bar numbers, unit labels |
| `--fs-2` | 13 / 18 | meta, helper text, table cells |
| `--fs-3` | 15 / 22 | body, inputs, buttons |
| `--fs-4` | 18 / 26 | section headings, inspector labels |
| `--fs-5` | 24 / 32 | song title, screen titles |
| `--fs-6` | 34 / 40 | entry promise only |

Two weights (450 regular, 620 semibold). Display sizes get `-0.01em` tracking.
Body measure ≤ 68 ch. No uppercase-tracked labels.

### 11.3 Space, shape, motion

- Spacing: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64. No arbitrary values.
- Radii: 6 (inputs, buttons), 10 (cards, score panel), 14 (modals only).
- Borders: 1 px `--line`; no shadows except overlays and the pinned transport
  (one soft top shadow).
- Motion: 120 ms `cubic-bezier(.2,0,0,1)` for state changes; 200 ms for the
  card→waiting swap. `prefers-reduced-motion` sets all durations to 0.
- Focus: 2 px `--accent` ring at 2 px offset, never removed.

### 11.4 Component rules

- Every interactive control ≥44×44 px. Inline icon buttons get a 44 px hit area
  even when drawn at 32 px.
- Labels are always visible. No `label_visibility="collapsed"` equivalent, ever.
- Numbers carry units: `90 s`, `0.05 s`, `40` with a name. No bare sliders.
- Empty and error states always have a cause and one action.
- One `h1` per screen; sections are real `h2`/`h3`.

---

## 12. Component inventory

| Component | Notes |
|---|---|
| `AppBar` | brand, Transcribe/Library, per-screen right slot |
| `Promise` | serif h1 + one subline (entry only) |
| `SourceTiles` | File / YouTube / Media URL, 88 px, keyboard roving focus; "Try a sample tab" is a quiet link inside the card |
| `Dropzone` | labelled, drag + click, shows name/size once chosen |
| `QuickSetup` | Title, Tuning, Capo in one group; visible labels |
| `SummaryLine` | "First 90 s · no stem separation" + `Change` |
| `AdvancedDrawer` | all remaining config, grouped: Length, Separation, Detection, Export |
| `ConvertButton` | 44 px, accent, disabled state explains why |
| `StageList` | 4 stages, weighted bar, elapsed, tip, `Cancel` |
| `SongHeader` | back, serif title, mono meta line, Export, New |
| `ViewSwitch` | Tab / Chords / Piano roll / Text, arrow-key navigable |
| `ScorePanel` | server SVG, natural scale, horizontal scroll, bar lines |
| `FeedbackPrompt` | Yes / Not quite, after the score |
| `Inspector` | Tuning, Capo, Transpose, Bars, Reset, Go deeper |
| `Transport` | play, time, waveform (seek + drag loop), speed, loop, metronome, Original/Stem |
| `ExportMenu` | PDF / GP5 / MIDI / TXT, availability stated |
| `RecentList` / `LibraryList` | one primary row action, context menu |
| `ConfirmDialog` | delete, full-track warning, discard run |
| `Toast` | success only; errors use an inline banner with an action |

`Transport` and `ScorePanel` are ports of `player_bar.py` and
`notation_view.py` output into the new client; the Python renderers stay the
source of truth for notation geometry.

---

## 13. Score rendering changes (the only engine touchpoints)

1. **Natural scale.** `notation_view` accepts the available `target_width_px`
   and lays out `bars_per_line` measures per row at fixed glyph metrics (staff
   line 1 px, note text 11 px). `bars_per_line` stays authoritative because it
   also drives the PDF's `measures_per_row`, so the screen and the export keep
   the same row breaks. Per-measure width is
   `clamp(target_width_px / bars_per_line, 148, 220)`; the SVG is never scaled
   past 1× by CSS.
2. **Bar lines.** Vertical rules at every measure boundary, `--line` ink, full
   staff height.
3. **Measure numbers** move above the staff, mono 10 px, `--muted`, centred on
   the bar. Never in fret ink below the staff.
4. **Minimum measure width** 148 px so a one-measure clip reads as one measure,
   not a fragment.
5. Everything else — note placement, chord diagrams, roll, text view — is
   unchanged. The PDF and GP5 builders are untouched.

---

## 14. Job API

### 14.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/uploads` | multipart file → `{upload_id, name, bytes, duration_sec}`; 200 MB cap |
| `POST` | `/api/jobs` | `{source, trim_start_sec, preset, config}` → `202 {job_id}` (§14.3) |
| `GET` | `/api/jobs/{id}` | current snapshot (poll fallback) |
| `GET` | `/api/jobs/{id}/events` | SSE: `snapshot`, `progress`, `done`, `error`, heartbeat 15 s |
| `POST` | `/api/jobs/{id}/cancel` | cooperative cancel → `{state: "cancelling"}` |
| `GET` | `/api/runs` | completed runs from `DATA_DIR`, newest first |
| `GET` | `/api/runs/{id}` | metadata + artifact availability |
| `DELETE` | `/api/runs/{id}` | delete run folder (path-guarded like `delete_run`) |
| `GET` | `/api/runs/{id}/score` | `view`, `tuning`, `capo`, `transpose`, `bars` → `{svg, meta}` with ETag |
| `GET` | `/api/runs/{id}/audio` | `kind=original\|stem`, Range supported |
| `GET` | `/api/runs/{id}/peaks` | waveform peaks from the stored WAV, cached in the run folder |
| `POST` | `/api/runs/{id}/export` | `{format, tuning, capo, transpose, bars}` → file stream with `Content-Disposition` |
| `POST` | `/api/runs/{id}/feedback` | `{answer: "yes"\|"no"}` persisted in run metadata |
| `POST` | `/api/runs/{id}/jobs` | re-run seeded from stored source/config (`separate_stems`) |
| `GET` | `/api/capabilities` | ffmpeg, Demucs, RoFormer, guitar-ft, GPU, max upload |
| `GET` | `/api/config/schema` | `PipelineConfig` fields, types, ranges, enums, defaults |
| `GET` | `/api/youtube/search` | existing search wrapper |
| `GET` | `/api/health` | port probe for the launcher |

This table is a floor, not a ceiling: read-only endpoints may be added where
the UI would otherwise duplicate server logic.

### 14.2 Job state machine

```
queued → running → done
              ├──→ failed
              └──→ cancelling → cancelled
```

- One worker thread. A second job sits `queued` with its position shown.
- `progress` events carry `{stage, message, fraction, rows}` where `rows` is the
  existing checklist state from `progress_checklist`.
- Cancel sets a `threading.Event`. It is checked before each stage and inside
  the progress callback. `run_pipeline`'s stage boundaries are the cancellation
  points, because Demucs/torch cannot be interrupted mid-forward.
- Copy: `Cancel` while queued or between stages; `Cancelling after this
  stage…` while a stage is executing. The job ends `cancelled`, the partial run
  folder is removed, and the entry state is restored intact.
- Errors map through `user_errors` to `{code, message, hint, action}`. Every
  error banner shows the cause and one working action.

### 14.3 Config mapping

`POST /api/jobs` separates the **source** from the **config**, because three
current inputs are not `PipelineConfig` fields:

```json
{
  "source": {
    "kind": "upload | youtube | media_url",
    "upload_id": "…",
    "youtube_url": "…",
    "media_url": "…"
  },
  "trim_start_sec": 0,
  "preset": "solo",
  "config": { "tuning_name": "Standard (EADGBE)", "capo": 0, "…": "…" }
}
```

- `trim_start_sec` is applied by the worker before `run_pipeline`, using the
  same ffmpeg path the current UI uses.
- `preset` expands to `separate_stems` + `mix_aware_filtering` exactly as the
  Solo/Full-mix control does today; an explicit `config` value wins.
- `config` accepts `PipelineConfig` field names, validates with the dataclass,
  and rejects unknown fields with a 422 that names the field.
- `/api/config/schema` is generated from the dataclass, so the Inspector and
  Advanced drawer never hand-duplicate a range or enum. Whether a field is
  *shown* is a separate, explicit list (parity with today's UI).

### 14.4 Exports, regeneration, and feedback

- **Exports are regenerated on demand**, never by mutating the stored run.
  `POST /api/runs/{id}/export` rebuilds from the run's `tab_midi` with the
  current inspector settings and writes to
  `DATA_DIR/exports/<run_id>/<tuning>-<capo>-<transpose>-<bars>/`, keyed and
  ETagged by signature. The run folder keeps the artifacts it was created with,
  so every run stays reproducible and two windows cannot race.
- PDF, GP5, MIDI, and tab text share that path; the menu states availability
  rather than pointing at a Downloads folder.
- **Feedback** is stored once per run in `meta.json` (`feedback: {answer, at}`)
  so "Does this sound right?" does not ask twice. There is no free-text note —
  the current accuracy-feedback module is session-only and has no note field,
  so this document does not invent one.

---

## 15. Copy deck (core strings)

| Where | Copy |
|---|---|
| Promise | "Turn a recording into guitar tab." |
| Subline | "Drop an audio file or paste a YouTube link. You get tab, chords, and a practice player in about 90 seconds." |
| Source tiles | File · YouTube · Media URL |
| Sample link | "Try a sample tab" |
| Summary | "First 90 s · no stem separation — Change" |
| Convert | "Convert" (disabled: "Install ffmpeg to convert.") |
| Waiting | "Preparing audio" · "Separating the guitar" · "Finding the notes" · "Building your tab" |
| Waiting caption | "Runs on your machine. You can cancel between stages." |
| Result meta | "Key G · 92 BPM · 1:24" |
| Feedback | "Does this sound right?" · Yes / Not quite |
| Depth | "Re-run with stem separation" · "Adds about 2 minutes" |
| Export | "Download PDF" · "Download Guitar Pro" · "Download MIDI" · "Download tab text" |
| Empty library | "Nothing transcribed yet." · "Transcribe something" |
| Failed run | cause sentence + one action, no raw exception |

File sizes always use one formatter (`4.6 MB`, never `4537.1 KB`). Sentences
are joined properly, never lowercase after a dash. Technical internals are
hidden unless the Advanced drawer is open.

---

## 16. Accessibility

- One `h1` per screen, sections as `h2`.
- The score SVG gets `role="img"` plus a text description and a link to the
  Text view; score seeking is keyboard-operable like the waveform.
- Focus visible on every control; roving focus in the source tiles and view
  switch.
- 44 px minimum targets; 200% zoom at 960 px width must not clip labels.
- Contrast stays at or above the audit's measured values (muted ≥ 6.8:1).
- `prefers-reduced-motion` respected.
- Status changes are announced via a polite live region (conversion stages,
  export complete, errors).

---

## 17. Milestones

| # | Scope | Size | Acceptance |
|---|---|---|---|
| **M0** | FastAPI skeleton, token gate, static build, launcher flag `--ui web\|streamlit`, fonts vendored, `PRODUCT.md` + `DESIGN.md`, read-only `/api/runs` | S | App opens without Streamlit and lists real past runs |
| **M1** | Entry, waiting, cancel, recent list; labels and order corrected in the new shell | M | Zero hidden labels; promise line; sample action in-card; cancel works between stages; Advanced fully labelled and grouped |
| **M2** | Result core: app bar, score first at natural scale with bar lines, view switch, pinned transport, inspector, feedback, export menu | L | Tab fully visible above the fold at 1280×860; no upscaling; measures numbered above; every export downloads a real file |
| **M3** | Depth + library + keyboard: real re-run, direct GP5, library actions, shortcuts (`Space`, `←/→`, `1–4`, `Esc`) | M | Re-run starts a real job; GP5 downloads; row actions work; shortcuts documented in a `?` overlay |
| **M4** | Parity + removal: every control reachable today remains reachable, demo pack, YouTube, Media URL, delete `ui/` and Streamlit | M | Parity test enumerates today's controls and fails if any is missing; `make desktop` runs the new UI from source; Streamlit gone from deps and code. Frozen build explicitly not in scope |

Overall: a project, roughly 3–4 weeks of focused work. **M0 + M1 is the first
usable slice** and is the smallest thing worth showing.

---

## 18. Risks

| Risk | Handling |
|---|---|
| EventSource unsupported in a platform webview | 500 ms poll fallback on the same state shape (§9.3) |
| Cancel cannot interrupt a running model | Stage-boundary cancel plus honest copy; no fake instant-cancel |
| Config parity gaps | A test enumerates today's controls (not all 34 dataclass fields) and fails if any is missing from the UI schema |
| Natural scale makes short clips look small | Minimum measure width 148 px and bar lines; correctness over filling the panel |
| Export mutating a run while another window reads it | Exports rebuild into `DATA_DIR/exports/<run>/<signature>/`; the run folder is never rewritten |
| Packaging needs Node | `dist/` is a build artifact included at package time; installed apps never run npm |
| Tests written against Streamlit CSS/strings | Replaced by API contract tests at M4; no attempt to keep both suites green simultaneously |
| Regressing the player | `player_bar.py` remains the reference; the port is compared side by side at 1×, 0.5×, loop, and metronome |
| Visual drift during build | Tokens live in one CSS file; a review pass checks against `DESIGN.md` and the audit screenshots |

---

## 19. What is left to the builder

- Exact Svelte component boundaries and store shape (one store per job, one per
  run).
- SSE reconnect/`Last-Event-ID` details and the ring-buffer size.
- Waveform port mechanics (canvas vs SVG) while keeping drag-to-loop and
  keyboard seek.
- File layout inside `app/web/src/lib`.
- Test split between `pytest` API tests and a small set of pure-function
  front-end tests.
- The `PRODUCT.md` / `DESIGN.md` contents at M0, using this document as the
  source.
- The `_MEIPASS`-safe asset-path helper, so an external build only copies
  `app/web/dist`.

---

## 20. What this replaces

`ui/app.py`, `ui/tab_pdf.py`, `ui/studio_theme.py`, `ui/studio_shell.py`,
`ui/common.py` (Streamlit-only helpers), the Streamlit start path in
`packaging/launcher.py`, and the Streamlit dependency in `pyproject.toml`.
Engine modules, artifacts, run metadata, and the CLI stay.

---

## 21. Builder-check resolutions (2026-11-18)

A reviewer read this document against the code and raised eight gaps. Seven are
settled here; the eighth is a scope question for the partner.

| Gap | Resolution | Where |
|---|---|---|
| "Every `PipelineConfig` field reachable" would add ~15 engine-surgery controls | Parity means **today's controls**, per the partner's "no engine rework" rule. No new knobs. | §3.8, §17 M4 |
| `bars_per_line` vs `target_width_px` | `bars_per_line` stays authoritative (it also sets PDF row breaks). Width only sizes each measure, clamped 148–220 px. | §13.1 |
| Exports: stored artifact or regenerated? | Regenerated from current inspector settings into a separate exports cache. The run folder is never mutated or raced. | §14.4 |
| Non-config inputs: trim start, Solo/Full-mix preset, Media URL | Kept as parity. `/api/jobs` separates `source`, `trim_start_sec`, and `preset` from `config`. | §14.3 |
| Frozen/packaged build has no spec in the repo | Out of scope by partner decision: the work ends at `make desktop` from source. `dist/` is copied by whoever builds frozen; asset paths are `_MEIPASS`-safe. | §6, §17 M4 |
| Accuracy feedback has no note field or persistence | Persist yes/no in run metadata; no free-text note. Removes the invented field. | §10.3, §14.4 |
| "Tab above the fold" for a 34-measure tab | Means the first row and the playhead's row are visible; the panel grows down and the page scrolls under a pinned transport. | §10.3 |
| Endpoints the UI needs but §14.1 lacked | Added `/peaks`, `/capabilities`, `/config/schema`, `/feedback`; §14.1 is a floor, not a ceiling. | §14.1 |

**Packaging (answered 2026-11-18).** The partner chose to stop at the source
launcher. The repo contains `sys.frozen` / `_MEIPASS` handling but no PyInstaller
spec, and this work does not add one. M4's exit check is `make desktop` with a
built `app/web/dist`; the frozen build stays outside the repo and only needs to
copy that folder.
