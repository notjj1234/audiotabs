# Tab PDF — Designed Desktop Front End: Implementation Plan

> **For Kimi Code (agentic worker):** this file is the brief and the plan. Read
> §0 and §1 before touching anything. Work one task at a time, in order. Each
> task ends with a runnable check and a commit. Do not skip a milestone gate.

**Goal:** Replace the Streamlit front end with a designed FastAPI + Svelte
desktop UI on the existing Python engine, so the tab leads the result screen,
every control is labelled and sized for a human, and the app looks like one
product instead of Streamlit wearing custom CSS.

**Architecture:** FastAPI serves a built Svelte 5 SPA inside the existing
pywebview window. A single worker thread runs `run_pipeline` and streams
progress over SSE; runs stay as folders under `DATA_DIR`. The Python notation
and player renderers remain the source of truth for tab geometry and playback.

**Tech stack:** Python 3.10–3.12, FastAPI, uvicorn, python-multipart, Svelte 5,
Vite, TypeScript, plain CSS tokens. Node is build-time only. pywebview is
already installed via the `desktop` extra.

**Spec:** `docs/superpowers/specs/2026-11-18-ui-redesign-design.md`
**Audit:** `docs/ui-audit/2026-11-18-ui-ux-audit.md`
**Screenshots:** `.superpowers/ui-audit/`
**Plan date:** 2026-11-19

## Kickoff (paste this into Kimi Code)

```text
Read docs/superpowers/plans/2026-11-19-ui-redesign-kimi.md in full, then read
the spec and audit it links to. Start at Task 1. Follow section 0 exactly:
scope lock, forbidden actions, stop-and-ask conditions, one commit per task,
explicit paths only. Do not start Task 2 until Task 1's tests pass and you have
reported the checkpoint. Stop at the M0 gate and wait for review.
```

---

## Global Constraints

- Python `>=3.10,<3.13`. Do not use 3.12-only syntax in `app/server`.
- New runtime dependencies: **only** `fastapi`, `uvicorn`, `python-multipart`.
  Node packages are dev/build-time only. Ask before adding anything else.
- Runtime is local-only. Bind `127.0.0.1`. No telemetry, accounts, or cloud.
- Window default 1280×860, minimum 960×640. Content max width 1180 px, 32 px
  gutters. No phone breakpoints.
- One accent: brass `#e8a317`. One UI family: Instrument Sans. Display:
  Instrument Serif. Mono: JetBrains Mono.
- Type sizes: 12 / 13 / 15 / 18 / 24 / 34. Weights: 450 / 620. Spacing:
  4 / 8 / 12 / 16 / 24 / 32 / 48 / 64. Radii: 6 / 10 / 14.
- Every interactive target is at least 44×44 px.
- One `h1` per screen. No hidden labels, ever.
- Motion 120 ms `cubic-bezier(.2,0,0,1)`; 200 ms for card→waiting;
  `prefers-reduced-motion` sets durations to 0.
- Fonts are vendored `.woff2` files with OFL licences in the repo. No CDN.
- Do not mutate a completed run folder when exporting. Exports go to
  `DATA_DIR/exports/<run_id>/<signature>/`.
- `bars_per_line` remains authoritative for row breaks, on screen and in PDF.
- Frozen/packaged builds are **out of scope**. `make desktop` from source is
  the exit check. Keep asset paths `_MEIPASS`-safe anyway.
- Preserve the repo's pre-existing uncommitted changes. Never run
  `git checkout -- .`, `git reset --hard`, `git stash`, or `git clean`.
- Never `git add -A` or `git add .`. Stage explicit paths only.
- Do not touch `graphify-out/`, `.impeccable/`, `.superpowers/`, or the stray
  `--full-page` file.

---

## Review Focus

These are the conditions most likely to break the new UI. Each one has a test
in the task that owns the code.

1. **A run with zero usable notes / empty transcription** must show a cause and
   one action, not a blank score panel or a spinner that never ends.
2. **A 34+ measure tab** must keep the first row and the playhead's row visible,
   grow downward, and scroll the page behind a pinned transport — never scale
   the SVG up to fill the panel.
3. **Cancel during stem separation** must end `cancelled`, remove the partial
   run folder, restore the entry state intact, and leave no worker running.
4. **Export while the inspector is changing a score** must not rewrite the run
   folder or race another window; exports rebuild from a signature-keyed cache.
5. **A legacy run** with no stored config/source or a missing stem must still
   open its score and hide depth actions it cannot honour.

---

## 0. Execution contract

### 0.1 Starting state

- The app is Streamlit 1.67: `ui/app.py`, `ui/tab_pdf.py` (~1,700 lines),
  `ui/studio_theme.py` (1,101 lines of CSS), `ui/studio_shell.py`,
  `ui/common.py`.
- `run_pipeline()` in `src/audio_to_tab/pipeline.py:222` is synchronous and
  reports progress through `on_progress(stage, message, fraction)`.
- Runs persist under `DATA_DIR` with `meta.json` (`_META_FILENAME`) and
  artifacts (`midi`, `tab`, `pdf`, `result`, `playback.wav`, sometimes `gp5`,
  `tab_midi`, `guitar_stem.wav`).
- `packaging/launcher.py` starts Streamlit on a free port and opens pywebview.
- The repo already has uncommitted work in `ui/`, `src/`, `tests/`,
  `packaging/launcher.py`, plus untracked files. Leave all of it in place.

### 0.2 Target state

- `make desktop` opens a pywebview window served by FastAPI; no Streamlit
  process exists.
- The entry screen has a promise line, three labelled source tiles (File,
  YouTube, Media URL), a labelled quick setup, a summary line, Convert, and a
  real Recent list.
- Waiting has four stages, a weighted bar, one tip, and a working Cancel.
- The result screen shows the tab first at natural scale with bar lines and
  measure numbers above the staff, a pinned transport, and a settings
  inspector. Exports are real files.
- Library lists completed runs with Open / Reveal / Delete.
- Streamlit is gone from `pyproject.toml`, the launcher, and the repo.

### 0.3 Scope lock

Work only in:

- `app/` (new server and web app)
- `packaging/launcher.py`
- `src/audio_to_tab/notation_view.py` (score geometry only)
- `src/audio_to_tab/tab_bundle.py` (export regeneration helpers, if needed)
- `tests/test_api_*.py`, `tests/test_notation_view.py`,
  `tests/test_ui_*.py`, `tests/test_launcher_web.py`
- `pyproject.toml`, `Makefile`, `.gitignore`, `README.md`
- `PRODUCT.md`, `DESIGN.md`
- `ui/` and `.streamlit/` **only in Task 22 (deletion)**
- `tests/test_studio_ui.py`, `tests/test_result_studio.py` **only in Task 22**

### 0.4 Forbidden actions

- Do not change transcription, separation, beat detection, tuning, or export
  formats. The only engine edits are the score-geometry changes in §3.6.
- Do not expose `PipelineConfig` fields that have no UI today (§3.8).
- Do not add a light theme, theme switch, routing library, state library, or
  component library.
- Do not add authentication beyond the local launch token.
- Do not rewrite `run_pipeline` or move it into a process pool.
- Do not copy competitor copy, logos, or palettes.
- Do not polish Streamlit. It is being deleted.
- Do not fabricate completion. Every claim needs a command output or a
  screenshot path.

### 0.5 Stop and ask

Pause and report before:

- fetching fonts fails (do not substitute a system font),
- adding any dependency outside the allowed three,
- deleting `ui/` or `.streamlit/` before Task 22,
- changing a public engine signature or `PipelineConfig`,
- choosing a different screen structure than §3.1,
- any destructive git command,
- the same test failing twice for an unexplained reason,
- a task would take more than ~2× its planned size.

### 0.6 Checkpoints

After each task, report in this shape:

```
✅ Task N — <name>
Changed: <files>
Checks: <commands + result>
Evidence: <screenshot path or API output>
Open: <none | question>
```

At each milestone gate, stop and produce the full acceptance table. Do not
start the next milestone until it passes.

### 0.7 Commit rules

- One commit per task, conventional subject.
- Stage only files touched by that task.
- Never commit `dist/`, `node_modules/`, screenshots, or export caches.
- If a task modifies a file that already had uncommitted work, `git diff` it
  first and keep those changes.

---

## 1. Findings that drive the work

### 1.1 Verdict

The engine and practice surface are good; the interface around them is not.
Audit score: **22/40 (Acceptable, 55%)**. No P0s — the core path completes.
This is under-designed, not broken. The ceiling is Streamlit itself.

**Success is measurable on the same rubric:** ≥32/40, tab above the fold, zero
hidden labels, zero interactive targets under 44 px, one UI font family, one
accent. Design-specificity verdict: **partially authored, 5.5/10** — one real
palette, a genuine source-tile component, and a bespoke player, behind generic
Streamlit chrome.

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of status | 3 | Strong progress; result says "Playing the original audio" with no player; demo runs unmarked |
| 2 | Match real world | 2 | Right vocabulary; no bar lines; stray measure number below the staff |
| 3 | User control | 2 | No cancel; no undo/reset except "Use defaults"; no note correction |
| 4 | Consistency | 2 | Two visual worlds (640 px card vs 1180 px studio); labels hidden on entry only |
| 5 | Error prevention | 3 | Good guardrails; "Try stem separation" silently changes the next run |
| 6 | Recognition | 2 | Advanced has no visible labels; sliders show bare `90` and `0.00` |
| 7 | Flexibility | 2 | Excellent player; zero shortcuts; no batch; no edit |
| 8 | Minimalist design | 2 | Entry ~55% empty; ~700 px of chrome before the tab; duplicated actions |
| 9 | Error recovery | 2 | Empty/failed states are dead ends |
| 10 | Help and docs | 2 | Good tooltips; internals leak; nothing explains the product |
| **Total** | | **22/40** | **Acceptable — significant improvement needed** |

### 1.2 Measured facts

| Fact | Value |
|---|---|
| Computed UI font | `"Source Sans", sans-serif` (Streamlit default) |
| Font files in repo | none |
| Type sizes / weights / radii in CSS | 15 / 8 / 5; no scale |
| CSS size | 1,101 lines, keyed to Streamlit `data-testid` and `.st-key-*` |
| Buttons | 32 px tall; 10/11 entry and 22/23 result controls under 44 px in one dimension |
| Headings | zero `h1`, one `h2` on the result screen |
| Contrast | passes: muted `#9aa3b2` = 6.84:1 on panel, 7.43:1 on background |
| Overflow | none at 1280 px or 390 px |
| Detector | CLI `[]` (HTML emitted from Python); live scan finds `nested-cards` on the file dropzone |
| Score position | begins ~820–900 px down the result screen |
| Score scale | 228 px viewBox stretched to ~790 px (≈3.4×) |
| Bar lines | none |
| Measure number | `top + 78`, same ink as frets, below the staff |
| Streamlit warning | `widget with key "tab_result_transpose" was created with a default value but also had its value set via the Session State API` |

### 1.3 P1 issues

1. **Every label inside the entry card is hidden** by
   `.st-key-tab_source_entry [data-testid="stWidgetLabel"]` at
   `ui/studio_theme.py:119`. Quick setup reads `sample-song / Standard / None`;
   Advanced shows a bare `90`, a bare `0.00`, and unnamed toggles.
2. **The tab is buried, then rendered wrong.** Order is header → caveats →
   `Accurate?` → Go deeper → buttons → Playback → Tab settings → Score view →
   score below the fold. The score is stretched, has no bar lines, and prints
   its measure number below the staff.
3. **Three depth actions lie.** `Try stem separation` sets a flag and tells the
   user to start over; `Export Guitar Pro` points at the Downloads menu; the
   banner repeats the same actions as bullets and buttons.

### 1.4 P2 issues

- Entry never says what the app makes. "Tab PDF" is a file extension; the
  sample action floats outside the centred card.
- Machine output is shown as copy: `4537.1 KB Duration about 4:50.`,
  `Playing the original audio. ran without stem separation…`,
  `Onset threshold —, frame threshold —.`
- Targets/headings/state: 32 px buttons, no `h1`, score is `<img alt="Guitar
  tab">`, mouse-only score seeking, invisible Streamlit heading anchor,
  duplicate file name, `4.6 MB` vs `4537.1 KB`.

### 1.5 Cognitive load

7 of 8 checks fail: single focus, chunking, grouping, visual hierarchy, one
thing at a time, minimal choices, working memory. Progressive disclosure
passes only because Advanced is collapsed — and its labels are hidden.

**Persona red flags.** Alex (power user): no shortcuts, `Use defaults` sits
above `Convert` so a double-click resets then converts, no batch, no note
editing, no cancel. Jordan (first-timer): "Tab PDF" means nothing, unlabelled
fields, "Solo/fingerstyle vs Full mix" assumes stem knowledge, "Accurate?"
before the tab, "start over" reads as losing the upload. Sam (accessibility):
no `h1`, tab is an image, mouse-only seeking, fixed tiles clip at 200% zoom,
11.5 px uppercase labels.

### 1.6 Minor observations (all confirmed)

- `--studio-border` is used at `studio_theme.py:629` but never defined.
- `.st-key-tab_source_entry` declared at 36 rem then 40 rem; second wins.
- Full-width segmented-control CSS no longer matches Streamlit 1.67; it renders
  ~270 px inside a 640 px card.
- Dropzone is left-aligned with a 22 px left / 63 px right gap.
- Result header uses `st.columns([6, 1])`, so Download ignores the 1180 px column.
- `Accurate?` label sits ~8 px above its Yes/No buttons.
- Playback claims to play audio while `_render_player` returns early when no
  playback file exists.
- Recent rows are not clickable; three affordances for 1–3 items.
- Progress is 640 px wide, result 1180 px — three widths in one flow.
- A refresh mid-flow loses in-progress state; only completed runs persist.

### 1.7 What already works — keep it

1. The weighted progress checklist: real stage weights, named stages, elapsed
   time, teaching tips, `role="progressbar"` with `aria-valuenow`.
2. The 88 px source tiles with matching icon discs and focus states.
3. The practice player: drag-to-loop waveform, 0.25–1× speeds, metronome from
   detected BPM, keyboard seek, and the hand-drawn staff/roll/chords with a
   synced playhead.

### 1.8 Why Streamlit is removed

1,101 lines of CSS keyed to internals; labels hidden globally to make one
control look right; stock uploader/audio/select/toast chrome; a rerun loop with
no cancel or async state; and a font stack the app cannot fully own. You can
get a better Streamlit app, not a designed one.

---

## 2. Decisions locked

### 2.1 Partner decisions (2026-11-18)

1. Exit route **B**: custom front end on the same Python engine.
2. Result leads with **tab + player**, not settings.
3. **Keep brass-on-charcoal** and add real typography.
4. **Fix labels and order first**, before broad visual polish — delivered in
   the new shell, never by polishing Streamlit twice.

**Alternatives rejected:** A, restyle Streamlit in place (2–4 days, capped by
stock widgets and the rerun loop); C, Python-native desktop UI with PySide6 or
NiceGUI (either heavier or the same theming fight).

### 2.2 Builder-check resolutions

| Gap | Resolution |
|---|---|
| "Every config field reachable" | Parity means **today's controls**, not all 34 dataclass fields. No new engine knobs. |
| `bars_per_line` vs target width | `bars_per_line` wins; width only sizes measures, clamped 148–220 px. |
| Export source | Regenerate from current inspector settings into a separate cache; never mutate the run. |
| Trim start / Solo–Full-mix preset / Media URL | Kept; the job request separates `source`, `trim_start_sec`, `preset`, `config`. |
| Frozen build | Out of scope. `make desktop` from source; `dist/` copied by an external build. |
| Accuracy feedback | Store yes/no per run; no free-text note (none exists today). |
| "Above the fold" | First score row plus the playhead's row visible at 1280×860; page scrolls under a pinned transport. |
| Missing endpoints | Add `/peaks`, `/capabilities`, `/config/schema`, `/feedback`; the endpoint list is a floor. |

### 2.3 Implementation calls

- **Svelte 5 + Vite + TypeScript.** No router; screens are app state.
- **SSE over `fetch` + `ReadableStream`,** not `EventSource`, because
  `EventSource` cannot send `X-Tab-Token`. Poll `/api/jobs/{id}` every 500 ms
  as fallback.
- **One worker thread**, one conversion at a time; second job is `queued`.
- **Cancel at stage boundaries.** torch/Demucs cannot be interrupted mid-forward.
- **Token in the URL fragment**, stored in memory, sent as `X-Tab-Token`.
- **No run-folder mutation after completion.**

---

## 3. Target design

### 3.1 Screens

**Entry — Transcribe**
App bar (brand, Transcribe / Library) → promise `h1` (Instrument Serif 34) +
one subline → card with three tiles (File / YouTube / Media URL), labelled
dropzone with "Try a sample tab" link, Quick setup (Title, Tuning, Capo),
summary line "First 90 s · no stem separation — Change", primary Convert
(44 px, full width) → Recent list with `Open` + `⋯` (Reveal, Delete).

**Waiting**
Replaces the card on the same screen. Four stages: Prepare, Separate,
Transcribe, Build tab. Weighted bar, elapsed, one tip, secondary Cancel. No form
remnants. Copy says whether separation is on before it starts.

**Result — song**
App bar: back, serif title, mono meta "Key G · 92 BPM · 1:24", Export menu,
New. Main column: view switch (Tab / Chords / Piano roll / Text) → score panel
→ feedback prompt. Right inspector (280 px): Tuning, Capo, Transpose, Bars per
line, Reset, "Go deeper" (Re-run with stem separation, adds ~2 min). Transport
pinned to the bottom at 88 px: play, time, waveform (seek + drag loop), speed,
loop, metronome, Original/Stem.

**Library**
Rows: title, key/tempo, duration, date; `Open`; `⋯` with Reveal and Delete
(confirm). Empty state: one sentence + "Transcribe something". No multi-select.

### 3.2 Tokens (`app/web/src/app.css`)

```
--bg #0f1115   --surface #171a21   --surface-2 #1d2129
--line #2a2f3a --text #e8eaef      --muted #9aa3b2
--accent #e8a317  --accent-ink #1a1305
--danger #e5534b  --ok #4ea36a
--fs-1 12/16  --fs-2 13/18  --fs-3 15/22
--fs-4 18/26  --fs-5 24/32  --fs-6 34/40
--space 4 8 12 16 24 32 48 64
--radius 6 10 14
--motion 120ms cubic-bezier(.2,0,0,1)
```
Two weights only: 450 and 620. Display sizes `-0.01em` tracking. Body ≤68 ch.
Focus ring 2 px accent at 2 px offset. One shadow, on the transport only.

### 3.3 Components

`AppBar`, `Promise`, `SourceTiles`, `Dropzone`, `QuickSetup`, `SummaryLine`,
`AdvancedDrawer`, `ConvertButton`, `StageList`, `SongHeader`, `ViewSwitch`,
`ScorePanel`, `FeedbackPrompt`, `Inspector`, `Transport`, `ExportMenu`,
`RecentList`, `LibraryList`, `ConfirmDialog`, `Toast`.

### 3.4 Copy deck

| Where | Copy |
|---|---|
| Promise | Turn a recording into guitar tab. |
| Subline | Drop an audio file or paste a YouTube link. You get tab, chords, and a practice player in about 90 seconds. |
| Tiles | File · YouTube · Media URL |
| Sample | Try a sample tab |
| Summary | First 90 s · no stem separation — Change |
| Convert | Convert (disabled: Install ffmpeg to convert.) |
| Waiting | Preparing audio · Separating the guitar · Finding the notes · Building your tab |
| Waiting caption | Runs on your machine. You can cancel between stages. |
| Result meta | Key G · 92 BPM · 1:24 |
| Feedback | Does this sound right? · Yes / Not quite |
| Depth | Re-run with stem separation · Adds about 2 minutes |
| Export | Download PDF · Download Guitar Pro · Download MIDI · Download tab text |
| Empty library | Nothing transcribed yet. · Transcribe something |
| Failure | Cause sentence + one action, never a raw exception |

File sizes use one formatter (`4.6 MB`, never `4537.1 KB`). Technical internals
stay inside Advanced. No "Soon" inside an action menu.

### 3.5 Score rendering rules

In `src/audio_to_tab/notation_view.py`:

- `tab_playhead_layout(doc, bars_per_line=4, measure_width=TAB_MEASURE_WIDTH)`
  accepts a clamped measure width; `width = 48 + measure_width * max(1, bars)`.
- `tab_staff_svg(..., measure_width=...)` draws a vertical bar line at every
  measure boundary (`class="bar-line"`, `--line` ink, full staff height).
- Measure numbers move above the staff: mono 10 px, muted, centred, `y` above
  `TAB_ORIGIN_Y`.
- SVG root uses `width="{width}" height="{height}"`, not `width="100%"`; the
  client caps display at 1× and scrolls horizontally.
- Per-measure width: `clamp(target_width_px / bars_per_line, 148, 220)`.
- PDF row breaks stay driven by `bars_per_line`; do not change the PDF builder.

### 3.6 Accessibility

One `h1` per screen; real `h2` sections. Score SVG `role="img"` + description
and a Text-view link. Score seeking is keyboard-operable. Roving focus in tiles
and view switch. 44 px targets. 200% zoom at 960 px must not clip labels.
Muted text ≥6.8:1. Polite live region for stages, export, errors.

### 3.7 API contract

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | launcher probe; no token |
| POST | `/api/uploads` | multipart → `{upload_id, name, bytes, duration_sec}`; 200 MB |
| POST | `/api/jobs` | `{source, trim_start_sec, preset, config}` → `202 {job_id}` |
| GET | `/api/jobs/{id}` | snapshot (poll fallback) |
| GET | `/api/jobs/{id}/events` | SSE: `snapshot`, `progress`, `done`, `error`; 15 s heartbeat |
| POST | `/api/jobs/{id}/cancel` | `{state: "cancelling"}` |
| GET | `/api/runs` | completed runs, newest first |
| GET | `/api/runs/{id}` | metadata + artifact availability |
| DELETE | `/api/runs/{id}` | path-guarded delete |
| GET | `/api/runs/{id}/score` | `view`, `tuning`, `capo`, `transpose`, `bars` → `{svg, meta}` + ETag |
| GET | `/api/runs/{id}/audio` | `kind=original\|stem`, Range supported |
| GET | `/api/runs/{id}/peaks` | cached waveform peaks |
| POST | `/api/runs/{id}/export` | `{format, tuning, capo, transpose, bars}` → file |
| POST | `/api/runs/{id}/feedback` | `{answer: "yes"\|"no"}` persisted |
| POST | `/api/runs/{id}/jobs` | re-run seeded from stored source/config |
| GET | `/api/capabilities` | ffmpeg, Demucs, RoFormer, guitar-ft, GPU, max upload |
| GET | `/api/config/schema` | fields, types, ranges, enums, defaults |

Job states: `queued → running → done | failed | cancelling → cancelled`.
`progress` carries `{stage, message, fraction, rows}` using
`progress_checklist.apply_progress`.

Job request:

```json
{
  "source": {"kind": "upload|youtube|media_url", "upload_id": "…",
             "youtube_url": "…", "media_url": "…"},
  "trim_start_sec": 0,
  "preset": "solo|full_mix",
  "config": {"tuning_name": "Standard (EADGBE)", "capo": 0}
}
```

`preset` expands to `separate_stems` + `mix_aware_filtering`; explicit `config`
wins. Unknown config fields → 422 naming the field.

Errors: `{code, message, hint, action}` from `user_errors`. Every banner shows
a cause and one working action.

### 3.8 Parity list — must remain reachable

Title, tuning, capo, fingering preference, separate-stem toggle, Solo/Full-mix
preset, Safer length, max duration, full-track confirmation, trim start, guitar
engine selection, guitar-ft weights, low-end restore, subtractive bass debleed,
spectral bleed gate, adaptive fold gain, cross-model ensemble, mix-aware
filtering, tempo override, onset threshold, frame threshold, result tuning,
capo, transpose, bars per line, PDF/GP5/MIDI/TXT downloads, recent runs,
YouTube search, Media URL, demo pack.

**Do not add:** `demucs_device`, `demucs_segment`, `demucs_jobs`,
`fold_other_mode`, `minimum_note_length_ms`, `min_velocity`, `min_duration_sec`,
`quantize_sec`, `max_notes_per_onset`, `beats_per_measure`, `beat_model`,
`auto_meter`, or a user-facing `export_gp5` choice.

---

## 4. File structure

```
app/
  __init__.py
  server/
    __init__.py
    __main__.py          # python -m app.server --port --data-dir
    main.py              # create_app(), static mount, token gate, health
    auth.py              # require_token dependency
    paths.py             # web_dist_dir() with _MEIPASS handling
    store.py             # RunRecord, read/list/delete runs, write metadata
    jobs.py              # JobManager, JobRecord, SSE ring buffer, cancel
    schemas.py           # JobRequest, SourceIn, ExportRequest, FeedbackRequest
    config_schema.py     # PipelineConfig -> JSON schema + UI field list
    routes_jobs.py
    routes_runs.py
    routes_sources.py
    exports.py           # signature-keyed regeneration cache
    score.py             # run -> SVG for each view, ETag cache
    errors.py            # user_errors -> {code,message,hint,action}
  web/
    package.json
    vite.config.ts
    tsconfig.json
    svelte.config.js
    index.html
    src/
      main.ts
      App.svelte
      app.css
      lib/
        api.ts
        stores.svelte.ts
        format.ts
        format.test.ts
        components/…
        screens/Entry.svelte, Waiting.svelte, Result.svelte, Library.svelte
    static/fonts/        # Instrument Sans/Serif, JetBrains Mono + OFL
    static/icons/        # app icon if needed
    dist/                # build output, git-ignored
tests/
  test_api_app.py
  test_api_runs.py
  test_api_jobs.py
  test_api_score.py
  test_api_exports.py
  test_config_schema.py
  test_notation_view.py
  test_ui_format.py      # optional: asserts format parity via node? see Task 3
  test_launcher_web.py
```

---

## 5. Tasks

### Milestone M0 — Foundations

**Gate:** app opens from source with FastAPI, lists real past runs, no
Streamlit process. No product screen is redesigned yet.

#### Task 1 — FastAPI skeleton, token, health, static path

**Files:**
- Create: `app/__init__.py`, `app/server/__init__.py`, `app/server/main.py`,
  `app/server/auth.py`, `app/server/paths.py`, `app/server/__main__.py`
- Test: `tests/test_api_app.py`

**Interfaces:**
- `create_app(*, data_dir: Path | None = None, token: str | None = None) -> FastAPI`
- `require_token(request: Request) -> None` reads `X-Tab-Token`; raises 401.
- `web_dist_dir() -> Path` checks `sys._MEIPASS/app/web/dist`, then
  `Path(__file__).parents[1] / "web" / "dist"`.
- Token from `TABPDF_TOKEN`; if unset, `secrets.token_urlsafe(32)`.

- [ ] **Step 1: Write failing tests**

Fixture: `TestClient(create_app(data_dir=tmp_path, token="t"))`.

```python
def test_health_needs_no_token(client):
    assert client.get("/api/health").status_code == 200

def test_api_requires_token(client):
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/runs", headers={"X-Tab-Token": "t"}).status_code == 200

def test_web_dist_dir_is_meipass_safe(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert web_dist_dir() == tmp_path / "app" / "web" / "dist"
```

- [ ] **Step 2: Run and confirm failure**

`PYTHONPATH=src:. python -m pytest tests/test_api_app.py -q`

- [ ] **Step 3: Implement `create_app`**

Mount API routers; mount `StaticFiles(dist, html=True)` at `/` only if `dist`
exists; otherwise serve a one-line HTML "Run make ui-build". `/api/health`
returns `{"ok": true, "version": "0.1.6"}`.

- [ ] **Step 4: Pass, add `__main__`**

`python -m app.server --port 8533` runs uvicorn bound to `127.0.0.1`.

- [ ] **Step 5: Commit**

`git add app/__init__.py app/server tests/test_api_app.py`

#### Task 2 — Run store and read API

**Files:**
- Create: `app/server/store.py`, `app/server/routes_runs.py` (read/delete only)
- Modify: `app/server/main.py`
- Modify: `ui/common.py` to re-export store helpers (temporary, deleted in Task 22)
- Test: `tests/test_api_runs.py`

**Interfaces:**
- `RunRecord(id, dir: Path, title, created_at, artifacts: dict[str, Path], details: dict, feedback: dict | None, source: dict | None, config: dict | None)`
- `list_runs(data_dir: Path) -> list[RunRecord]`
- `get_run(data_dir: Path, run_id: str) -> RunRecord | None`
- `delete_run(data_dir: Path, run_id: str) -> bool` (path-guarded)
- `write_run_metadata(run_dir, *, page, title, artifacts, details=None, source=None, config=None, feedback=None)`
  writes atomically (temp file + `replace`) and preserves unknown keys.

- [ ] **Step 1: Tests**

`test_list_runs_newest_first`, `test_get_run_rejects_path_traversal`,
`test_delete_run_removes_folder`, `test_metadata_roundtrip_includes_source_and_config`,
`test_legacy_meta_without_source_still_reads`.

- [ ] **Step 2: Implement, run, pass.**

- [ ] **Step 3: Commit.** `app/server/store.py app/server/routes_runs.py ui/common.py tests/test_api_runs.py`

#### Task 3 — Front-end scaffold, tokens, fonts, shell, library

**Files:**
- Create: `app/web/package.json`, `vite.config.ts`, `tsconfig.json`,
  `svelte.config.js`, `index.html`, `src/main.ts`, `src/App.svelte`,
  `src/app.css`, `src/lib/api.ts`, `src/lib/format.ts`, `src/lib/format.test.ts`,
  `src/lib/components/AppBar.svelte`, `src/lib/screens/Library.svelte`
- Create: `app/web/static/fonts/*.woff2` + `OFL.txt`
- Modify: `.gitignore`, `Makefile`

**Interfaces:**
- `apiFetch<T>(path, init?)` adds `X-Tab-Token` from memory; throws
  `ApiError {code, message, hint, action}`.
- `getToken()` reads `#token=…` once, stores in memory, clears the fragment.
- `formatBytes(4537.1 * 1024) === "4.4 MB"`,
  `formatDuration(284) === "4:44"`, `joinSentence("a.", "b")`.
- App state: `screen: "entry" | "waiting" | "result" | "library"`.

- [ ] **Step 1: Scaffold** with Svelte 5 runes, TypeScript, Vitest. Add scripts
  `dev`, `build`, `check`, `test`. Vite proxy `/api` → `http://127.0.0.1:8533`.
  Commit `package-lock.json`; `npm ci` must work from a clean checkout.
- [ ] **Step 2: Vendor fonts** (Instrument Sans variable, Instrument Serif 400,
  JetBrains Mono 400/500) as `.woff2` + OFL. If download fails, stop and ask.
- [ ] **Step 3: Write `app.css`** with the §3.2 tokens, resets, focus ring,
  reduced-motion rule, and `@font-face` declarations. No component CSS here.
- [ ] **Step 4: Write `format.test.ts`** for the three formatters; run
  `npm test` → pass.
- [ ] **Step 5: Build AppBar + Library** reading `/api/runs`; empty state per
  copy deck. Confirm `npm run build` produces `dist/`.
- [ ] **Step 6: Add Makefile targets**

```
ui-build: cd app/web && npm ci && npm run build
dev-api:  PYTHONPATH=src:. python -m app.server --port 8533
dev-web:  cd app/web && npm run dev
```

- [ ] **Step 7: Commit** explicit paths.

#### Task 4 — Launcher serves the web UI

**Files:**
- Modify: `packaging/launcher.py`
- Test: `tests/test_launcher_web.py`

**Interfaces:**
- `build_web_url(port: int, token: str) -> str` → `http://127.0.0.1:<port>/#token=<token>`
- `start_web_server(port: int, token: str) -> Popen` runs
  `python -m app.server --port <port>` with `TABPDF_TOKEN`.
- `--ui web|streamlit`, default `streamlit` in M0–M1, switch to `web` at M2.

- [ ] **Step 1: Tests** for URL shape and env propagation.
- [ ] **Step 2: Implement; keep the Streamlit path intact behind the flag.**
- [ ] **Step 3: Manual check** `PYTHONPATH=src:. python packaging/launcher.py --ui web`
  → window opens, Library lists runs, no Streamlit process
  (`pgrep -fl streamlit` empty).
- [ ] **Step 4: Commit.**

#### Task 5 — Product and design docs

**Files:** create `PRODUCT.md`, `DESIGN.md`.

- [ ] **Step 1:** `PRODUCT.md` — what the app is, who it serves, the promise,
  success metrics from §1.1, anti-goals.
- [ ] **Step 2:** `DESIGN.md` — tokens, type scale, component rules, copy
  voice, accessibility rules, and the screens in §3.1. Link the spec.
- [ ] **Step 3: Commit.**

**M0 gate report:** health/401 checks, runs list, screenshot of the shell,
`pgrep -fl streamlit` empty when `--ui web`.

---

### Milestone M1 — Entry, waiting, cancel

**Gate:** zero hidden labels, promise line, sample inside the card, Advanced
fully labelled and grouped, cancel works between stages, Recent actions work.

#### Task 6 — Sources, capabilities, config schema

**Files:**
- Create: `app/server/routes_sources.py`, `app/server/config_schema.py`,
  `app/server/schemas.py`, `app/server/errors.py`
- Modify: `app/server/main.py`
- Test: `tests/test_config_schema.py`, `tests/test_api_app.py`

**Interfaces:**
- `GET /api/capabilities` → `{ffmpeg, demucs, roformer, guitar_ft, gpu, max_upload_mb}`
- `GET /api/config/schema` → `{fields: [{name, type, default, min?, max?, enum?, group}]}`
- `POST /api/uploads` → 200 MB cap, saved under `DATA_DIR/uploads/<uuid>/<name>`.

- [ ] **Step 1: Tests** — schema includes every `PipelineConfig` field exactly
  once; capabilities shape; upload stores and returns duration; oversize 413.
- [ ] **Step 2: Implement.** Use `dataclasses.fields(PipelineConfig)`; derive
  enums from `TUNING_PRESETS`, quality, beat model, fingering.
- [ ] **Step 3: Pass + commit.**

#### Task 7 — Job manager, SSE, cancel

**Files:**
- Create: `app/server/jobs.py`, `app/server/routes_jobs.py`
- Modify: `app/server/main.py`, `app/server/store.py`
- Test: `tests/test_api_jobs.py`

**Interfaces:**
- `JobRecord` fields from §3.7 plus `cancel_event: threading.Event`.
- `JobManager(data_dir, runner=run_pipeline, max_workers=1)`
  - `submit(req: JobRequest) -> str`
  - `get(job_id) -> dict`
  - `cancel(job_id) -> str`
  - `stream(job_id, last_id=0) -> Iterator[dict]`
- Worker builds `PipelineConfig` from `config` + `preset`, applies
  `trim_start_sec` with `audio_to_tab.isolate._trim_audio(path, length,
  start_sec=…)`, downloads a `media_url` source with
  `download_direct_media(url, dest_dir)`, calls
  `runner(..., on_progress=emit)`, then `write_run_metadata` with `source` and
  `config`.
- `JobCancelled` checked before each stage and in `emit`; partial run dir
  removed; job ends `cancelled`.
- Ring buffer: last 200 events, monotonic `id`.

- [ ] **Step 1: Tests** with a fake runner: done path, ordered progress,
  queued second job, cancel between stages, partial-dir removal, error mapping,
  unknown field 422, SSE replay from `Last-Event-ID`.
- [ ] **Step 2: Implement minimal. Run. Pass.**
- [ ] **Step 3: Commit.**

#### Task 8 — Entry screen

**Files:**
- Create: `src/lib/screens/Entry.svelte`, `src/lib/components/SourceTiles.svelte`,
  `Dropzone.svelte`, `QuickSetup.svelte`, `SummaryLine.svelte`,
  `AdvancedDrawer.svelte`, `ConvertButton.svelte`
- Modify: `App.svelte`, `api.ts`, `stores.svelte.ts`

**Interfaces:**
- `SourceTiles` emits `change(kind)`; keyboard roving focus.
- `QuickSetup` reads `/api/config/schema` for tuning/fingering; fields always
  labelled above the control.
- `AdvancedDrawer` groups: Length, Separation, Detection; uses a native
  `<details>` or a button + region; every field labelled with units.
- Convert disabled state renders the ffmpeg reason inline.

- [ ] **Step 1: Build the screen with static fixtures; no API mutation yet.**
- [ ] **Step 2: Wire uploads + YouTube search + media URL; Convert posts a job
  and switches to Waiting.**
- [ ] **Step 3: Manual checks at 1280×860 and 960×640:** every label visible;
  all targets ≥44 px; no horizontal overflow; sample link inside the card.
- [ ] **Step 4: Commit.**

#### Task 9 — Waiting screen and cancel

**Files:**
- Create: `src/lib/screens/Waiting.svelte`, `src/lib/components/StageList.svelte`
- Modify: `stores.svelte.ts`, `App.svelte`

- [ ] **Step 1: Map 7 pipeline stages onto 4 rows** (Prepare = ingest;
  Separate = separate; Transcribe = transcribe; Build tab = tab/pdf/export).
  Show elapsed time and one tip from `progress_tips.progress_tip_for`.
- [ ] **Step 2: Consume SSE via fetch stream; fallback to 500 ms polling.**
- [ ] **Step 3: Cancel button** → `POST /cancel`; while a stage runs show
  "Cancelling after this stage…"; on `cancelled`, restore the entry form with
  the previous source/config intact.
- [ ] **Step 4: Manual:** cancel a stem run; confirm no partial folder remains
  and no worker keeps writing.
- [ ] **Step 5: Commit.**

#### Task 10 — Recent list actions

**Files:**
- Modify: `src/lib/screens/Entry.svelte`, `Library.svelte`
- Create: `src/lib/components/RecentList.svelte`

- [ ] **Step 1:** Row click or `Open` loads the run; `⋯` offers Reveal and
  Delete; Delete uses `ConfirmDialog`.
- [ ] **Step 2: Add `POST /api/runs/{id}/reveal`** (server calls
  `open -R`/`explorer /select,`).
- [ ] **Step 3: Manual:** open, reveal, delete; confirm list refresh.
- [ ] **Step 4: Commit.**

**M1 gate report:** screenshots entry (empty + file chosen + Advanced open) and
waiting; label audit; cancel evidence; `pytest tests/test_api_jobs.py -q`.

---

### Milestone M2 — Result core

**Gate:** tab fully visible above the fold at 1280×860; no upscaling; bar lines
and measure numbers correct; every export downloads a real file; feedback after
the score.

#### Task 11 — Score geometry in `notation_view`

**Files:**
- Modify: `src/audio_to_tab/notation_view.py`
- Test: `tests/test_notation_view.py`

**Interfaces:**
- `tab_playhead_layout(doc, *, bars_per_line=4, measure_width=TAB_MEASURE_WIDTH)`
- `tab_staff_svg(doc, *, bars_per_line=4, measure_width=TAB_MEASURE_WIDTH, ink, line)`
- `measure_width_for(target_width_px: int, bars_per_line: int) -> int` →
  `clamp(target_width // bars, 148, 220)`.

- [ ] **Step 1: Tests**
  `test_bar_lines_at_every_measure`, `test_measure_number_above_staff`,
  `test_measure_width_clamped`, `test_svg_not_percent_width`,
  `test_pdf_row_breaks_unchanged` (assert `write_tab_exports` still uses
  `bars_per_line`).
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement.** Keep existing note math; only add bar-line elements,
  move the number, accept width, replace `width="100%"`.
- [ ] **Step 4: Pass + commit.**

#### Task 12 — Score, audio, peaks endpoints

**Files:**
- Create: `app/server/score.py`, extend `app/server/routes_runs.py`
- Test: `tests/test_api_score.py`

**Interfaces:**
- `GET /api/runs/{id}/score?view=tab|chords|roll|text&tuning&capo&transpose&bars`
  → `{view, svg?, text?, meta: {bars, key, warnings}, etag}`.
- Build `TabDocument` with `tab_document_for` from `tab_midi` (or `midi`),
  using `result.json` metadata.
- Chords: `bundle_chords` + `chord_diagram_svg`; Roll: `piano_roll_svg`;
  Text: `screen_tab_text`.
- ETag = SHA-256 of `(run mtime, view, tuning, capo, transpose, bars)`.
- `GET /audio?kind=original|stem` with Range; 404 with reason when missing.
- `GET /peaks?points=800` cached under `DATA_DIR/cache/peaks/<run>.json`.

- [ ] **Step 1: Tests** for each view, ETag stability/change, missing stem 404,
  missing/corrupt MIDI 409 with code `empty_transcription` and an action, peaks
  shape and cache reuse.
- [ ] **Step 2: Implement + pass + commit.**

#### Task 13 — Result shell: app bar, score, view switch

**Files:**
- Create: `src/lib/screens/Result.svelte`, `SongHeader.svelte`,
  `ScorePanel.svelte`, `ViewSwitch.svelte`
- Modify: `App.svelte`, `stores.svelte.ts`

- [ ] **Step 1:** SongHeader: back, title (serif 24), mono meta, Export slot,
  and `New` (returns to a cleared entry form after a confirm).
- [ ] **Step 2:** ScorePanel: server SVG rendered inline at intrinsic width,
  `overflow-x: auto`, `max-width: 100%`, never `width: 100%`; `role="img"` plus
  a description and a link to the Text view; empty/error state with cause +
  action (Review Focus 1).
- [ ] **Step 3:** ViewSwitch: Tab / Chords / Piano roll / Text, arrow-key
  navigable, remembered per run in memory.
- [ ] **Step 4: Measure:** at 1280×860, first score row top `< 600 px` and the
  playhead's row visible without scrolling; SVG display/intrinsic ratio
  `≤ 1.01`.
- [ ] **Step 5: Commit.**

#### Task 14 — Transport

**Files:**
- Create: `src/lib/components/Transport.svelte`, `src/lib/player.ts`
- Modify: `Result.svelte`, `api.ts`

- [ ] **Step 1:** Port `player_bar.py` behaviour: play/pause, timecode,
  waveform seek, drag-to-loop, speeds 0.25/0.5/0.75/1, loop toggle, metronome
  from BPM, Original/Stem switch, keyboard seek on the waveform.
- [ ] **Step 2:** Use `<audio>` with `/api/runs/{id}/audio`; peaks from
  `/peaks`; no base64 inlining.
- [ ] **Step 3:** Pinned bottom, 88 px, one top shadow; page content gets
  `padding-bottom: 88px`.
- [ ] **Step 4: Manual:** compare against `player_bar.py` at 1×, 0.5×, loop,
  metronome; playhead follows audio; reduced motion respected.
- [ ] **Step 5: Commit.**

#### Task 15 — Inspector, exports, feedback

**Files:**
- Create: `src/lib/components/Inspector.svelte`, `ExportMenu.svelte`,
  `FeedbackPrompt.svelte`, `app/server/exports.py`
- Modify: `Result.svelte`, `routes_runs.py`
- Test: `tests/test_api_exports.py`

**Interfaces:**
- `build_export(run, settings) -> Path` writes to
  `DATA_DIR/exports/<run_id>/<tuning>-<capo>-<transpose>-<bars>/`.
- `POST /export {format, tuning, capo, transpose, bars}` → `FileResponse`;
  formats `pdf|gp5|midi|txt`; unavailable GP5 → 409 with reason and action.
- `POST /feedback {answer}` writes `feedback` into `meta.json` atomically.
- Inspector rerenders the score after 150 ms debounce; Reset restores run
  defaults.

- [ ] **Step 1: Tests:** export does not modify run folder (compare mtimes and
  hashes), second call reuses cache, unknown format 422, GP5 missing 409,
  feedback persists and is returned by `GET /runs/{id}`.
- [ ] **Step 2: Implement + pass.**
- [ ] **Step 3: Manual:** tuning/capo/transpose/bars each update the score and
  the PDF row breaks; every menu item downloads a real file.
- [ ] **Step 4: Commit.**

**M2 gate report:** above-fold measurement, upscale ratio, bar-line count,
measure-number position, export hashes, screenshots at 1280×860 and 960×640,
`pytest tests/test_api_score.py tests/test_api_exports.py -q`.

---

### Milestone M3 — Depth, library, keyboard

**Gate:** re-run starts a real job; GP5 downloads directly; library actions
work; shortcuts documented.

#### Task 16 — Re-run with stem separation

**Files:**
- Modify: `app/server/routes_runs.py`, `app/server/jobs.py`,
  `src/lib/components/Inspector.svelte`
- Test: `tests/test_api_jobs.py`

- [ ] **Step 1: Test** `POST /api/runs/{id}/jobs {separate_stems: true}` creates
  a queued job from stored `source` + `config`; legacy run without source → 409
  with a cause; UI hides the action for legacy runs.
- [ ] **Step 2: Implement + pass.**
- [ ] **Step 3:** Inspector shows "Adds about 2 minutes"; on start, switches to
  Waiting with the original entry settings preserved.
- [ ] **Step 4: Manual:** run a solo clip, then re-run with separation; confirm
  new run folder, old one untouched.
- [ ] **Step 5: Commit.**

#### Task 17 — Library screen and reveal

**Files:** `src/lib/screens/Library.svelte`, `RecentList.svelte`,
`ConfirmDialog.svelte`.

- [ ] **Step 1:** Row: title, key/tempo, duration, date; Open; menu with Reveal
  and Delete; confirm dialog names the run and says it cannot be undone.
- [ ] **Step 2:** Empty state per copy deck.
- [ ] **Step 3: Manual:** delete a run, confirm folder gone, list refresh.
- [ ] **Step 4: Commit.**

#### Task 18 — Keyboard shortcuts and help

**Files:** `src/lib/shortcuts.ts`, `src/lib/components/HelpOverlay.svelte`,
`Result.svelte`.

- [ ] **Step 1:** `Space` play/pause, `←/→` seek 5 s, `1–4` views, `Esc` close
  overlay/dialog. Ignore when focus is in an input.
- [ ] **Step 2:** `?` opens a shortcut list; include it in the app bar menu.
- [ ] **Step 3: Manual:** verify all keys, focus rings, no scroll hijack.
- [ ] **Step 4: Commit.**

#### Task 19 — Empty, error, and legacy states

**Files:** screens/components as needed; `app/server/errors.py`.

- [ ] **Step 1:** Cover: no notes, failed separation, missing stem, missing
  playback, corrupt/legacy metadata, invalid upload type, ffmpeg missing,
  network/YouTube failure. Each: cause + one action.
- [ ] **Step 2:** Add tests for the API error codes used by those states.
- [ ] **Step 3: Manual sweep** at 1280 and 960.
- [ ] **Step 4: Commit.**

**M3 gate report:** re-run evidence, GP5 file, library screenshots, shortcut
list, legacy-run evidence.

---

### Milestone M4 — Parity and removal

**Gate:** every control in §3.8 reachable; Streamlit gone; tests green;
`make desktop` opens the new UI.

#### Task 20 — Parity inventory

**Files:** create `app/server/ui_manifest.py`, `tests/test_ui_parity.py`;
modify entry/Advanced/Inspector.

- [ ] **Step 1:** Manifest lists every control ID in §3.8 with its config field
  or non-config input.
- [ ] **Step 2: Test** asserts every manifest entry exists in the schema or the
  source list and that the front-end field list covers it; fail on extras from
  the "do not add" list.
- [ ] **Step 3:** Wire anything missing (expected: fingering, full-track
  confirmation, ensemble, guitar-ft).
- [ ] **Step 4: Commit.**

#### Task 21 — Demo pack, YouTube, Media URL parity

**Files:** `app/server/routes_sources.py`, `Entry.svelte`.

- [ ] **Step 1:** Demo pack endpoint returns the packaged sample; sample link
  starts a job with the demo source.
- [ ] **Step 2:** YouTube search + pagination port; Media URL validation and
  error copy.
- [ ] **Step 3: Test** each source produces a valid `JobRequest`.
- [ ] **Step 4: Manual:** one run per source.
- [ ] **Step 5: Commit.**

#### Task 22 — Remove Streamlit

**Files:** delete `ui/`, `.streamlit/`, `tests/test_studio_ui.py`,
`tests/test_result_studio.py`; modify `pyproject.toml`, `Makefile`,
`packaging/launcher.py`, `README.md`.

- [ ] **Step 1:** Confirm Task 20 parity test green; stop if not.
- [ ] **Step 2:** Launcher default `web`; delete the Streamlit branch.
- [ ] **Step 3:** Drop `streamlit` from dependencies; keep the three new ones.
- [ ] **Step 4:** Delete `ui/` and `.streamlit/`; remove `make ui`; update
  README commands to `make ui-build` + `make desktop`.
- [ ] **Step 5:** Run the full suite; fix references. Do not delete engine tests.
- [ ] **Step 6: Commit** with the deletion and dependency change.

#### Task 23 — Full verification and handoff

- [ ] **Step 1:** `PYTHONPATH=src:. python -m pytest tests/ -q` → pass.
- [ ] **Step 2:** `cd app/web && npm ci && npm run check && npm run build` → pass.
- [ ] **Step 3:** `make desktop` → window opens; `pgrep -fl streamlit` empty;
  `pgrep -fl "app.server"` shows one process.
- [ ] **Step 4:** Manual acceptance table (§6) at 1280×860 and 960×640, 200%
  zoom at 960; save screenshots under `.superpowers/ui-audit/final/`.
- [ ] **Step 5:** Update `DESIGN.md` if implementation diverged; add a short
  "after" section to the audit doc with the new measured scores.
- [ ] **Step 6: Commit** docs and final fixes.

**M4 gate report:** parity checklist, full test output, build output, final
screenshots, `pgrep` evidence, and a one-page before/after summary.

---

## 6. Verification matrix

### Automated

| Command | Pass means |
|---|---|
| `PYTHONPATH=src:. python -m pytest tests/ -q` | all pass |
| `cd app/web && npm run check` | 0 errors |
| `cd app/web && npm test -- --run` | formatter/unit tests pass |
| `cd app/web && npm run build` | `dist/` produced, no warnings |
| `PYTHONPATH=src:. python packaging/launcher.py --ui web` | window opens, no Streamlit |
| `curl -s -o /dev/null -w "%{http_code}" 127.0.0.1:<port>/api/runs` | `401` |
| same with `-H "X-Tab-Token: $TABPDF_TOKEN"` | `200` |

### Manual, measured

At 1280×860 and 960×640 unless stated:

1. Exactly one `h1` per screen.
2. Computed UI font is Instrument Sans; mono is JetBrains Mono.
3. No rendered text below 12 px; no more than six distinct sizes in use.
4. Every `button`, `[role=button]`, input, and select has a bounding box
   ≥44×44 px.
5. No horizontal document overflow (`scrollWidth <= clientWidth`).
6. Result: first score row top `< 600 px`; playhead's row visible.
7. Score display width ÷ intrinsic width `≤ 1.01`.
8. Bar-line count equals measures − 1 per row; measure numbers sit above the
   staff in muted mono 10 px.
9. Score starts above the fold and the transport stays at the viewport bottom
   while the page scrolls.
10. Advanced open at 960 px: every label visible, nothing clipped at 200% zoom.
11. Cancel during separation: state ends `cancelled`, partial folder gone, entry
    restored, no process writing.
12. Export twice with different settings: run folder hashes unchanged; both
    files match the on-screen score.
13. Legacy run: score opens; depth action hidden; no console errors.
14. Empty run: cause + action, no blank panel.
15. Contrast: muted text ≥6.8:1; focus ring visible on every control.

---

## 7. Risks and responses

| Risk | Response |
|---|---|
| `EventSource` cannot send the token | fetch-stream SSE + poll fallback (§2.3) |
| Cancel not instant inside torch | stage-boundary cancel + honest copy |
| Parity drift | manifest test from §3.8; fail on extras |
| Packaging needs Node | `dist/` built before packaging; no npm at runtime |
| Short clip looks small | 148 px minimum measure + bar lines |
| Export races | signature cache, run folder immutable |
| Test suite tied to Streamlit | replaced at Task 22, not kept green in parallel |
| Player regression | side-by-side against `player_bar.py` at four speeds |
| Visual drift | tokens in one file; review against `DESIGN.md` |

---

## 8. Out of scope

- Frozen/packaged builds and installers.
- New transcription/separation models or knobs.
- Light theme, theme switcher, font picker.
- Mobile layout below 960 px.
- Accounts, sync, telemetry, cloud.
- Batch conversion, note editing, undo history.
- MusicXML/LilyPond/Synth additions.
- Rewriting the PDF/GP5/MIDI builders.

---

## 9. Handoff requirements

At the end, produce:

1. A file-by-file summary of what changed.
2. The full test and build output.
3. The measured acceptance table from §6 with actual numbers.
4. Screenshot paths for entry, waiting, result (Tab and Chords), library, and
   the empty/error states.
5. Any place the implementation diverged from the spec, with the reason.
6. Anything still open, ranked by user impact.

Claims without a command result or screenshot are not accepted.
