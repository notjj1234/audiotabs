# Instrument parts — design

## Context

Today a conversion transcribes a single source: the guitar stem or the raw mix.
htdemucs_6s already produces six stems, but five of them are thrown away. The
user can't see what was detected, can't choose parts, and can only view one tab
at a time. Vocal energy that leaks into the guitar stem also turns into fake
guitar notes. This work adds four things:
- **G1:** an instrument-detection picker.
- **G2:** Lead and Rhythm guitar as first-class parts.
- **G3:** a multi-part result screen with a Single/Together toggle.
- **G4:** de-bleed that uses the vocals stem.

User decisions made during planning (2026-11-25):
- The Lead/Rhythm split **runs during analysis**, so the picker shows what actually happened.
- **Every detected instrument is tabbable, with guitar first.** Bass gets a 4-string tab. Vocals, keys and "other" get real staff notation, not fret numbers. Drums get a drum staff from **heuristic kit-hit detection**: kick, snare and hi-hat, labelled "rough". No new dependencies.
- Staff notation is a **custom SVG staff** built into our own viewer. No VexFlow or alphaTab.
- Git: create `feat/instrument-parts` and **do not commit or push**. The user tests the working tree first. Every "Commit" step below becomes "leave staged-ready, no commit".

Verified codebase facts that change the brief:
1. **There's no server-side cancel.** Waiting's Back button only stops polling (`Waiting.svelte:137`), and `JobManager` (`app/server/jobs.py`) has no cancel or TTL. The hooks already exist: `separate.run_demucs(should_abort=…)` (`separate.py:392`) and `subprocess_util.JobAborted`.
2. **The Lead/Rhythm path never writes `vocals.wav`** (`pipeline.py:271-302`), so G4 would have no input on today's default path. Keeping every stem from the analysis phase fixes that.
3. **`isolate.apply_bleed_gate` already exists** (`isolate.py:1442`) but is opt-in and never uses vocals as a competitor. The Demucs branch also passes the guitar stem in as its own competitor (`separate.py:820-827`, `_maybe_bleed_gate`), which is a bug.
4. **Guitar-ft writes all six stems** (`separate.py:323`), so one separation can feed both the inventory and the tab phase.
5. **pywebview defaults to private mode** (`packaging/launcher.py:198`), so `localStorage` is wiped on every launch. Persisted view state has to live in `meta.json`.
6. **App.svelte unmounts Entry when the screen changes**, so the draft state has to move up into App for Back to keep it.
7. **The tab engine assumes 6 strings** (`tab_generate.py:310` `range(6)`, `:424` `len(raw_tuning) == 6`). Bass needs the string count generalised.
8. **Accent token:** `app.css` has `--accent #F6AD49` and PRODUCT.md says `#e8a317`. Always use `var(--accent)` and never hard-code a hex. The mismatch is flagged in the docs task.
9. **`graphify-out` is stale** (built at 82b2a96, HEAD is 772a335). Step 0.3 refreshes it.

## Intent
After you press Convert, show which instruments are in the song. You pick which parts to tab, and the result shows them one at a time or stacked together. Guitar comes first, and the Lead/Rhythm split is visible and honest. Vocals stop turning into fake guitar notes.

## Goals
- G1 picker between Entry and Waiting, fed by a one-time cached analysis.
- G2 Lead / Rhythm / Combined guitar rows that follow the real split outcome.
- G3 Single and Together views over a generic `tracks[]` model.
- G4 de-bleed driven by the vocals stem, proven with numbers.
- New tabbable parts: bass (4-string tab), vocals, keys and other (staff notation), drums (rough kit staff).

## Non-goals
- Engraving-grade notation. v1 has no key signatures, rests, ties or tuplets on the staff.
- Toms and cymbal types on the drum staff.
- Bass tuning options (standard EADG only).
- GP5 multi-track export, and PDF for notation or drum parts.
- An editable score.

## Anti-goals
These would make the work a failure even if it technically runs:
- Separating or downloading twice.
- Pre-checking Lead + Rhythm + Combined together.
- A fake tab for a part with no real transcription.
- Raw exceptions shown in the UI.
- Removing real guitar notes in order to remove vocal notes.
- Changing what solo runs or legacy runs produce.

## Constraints
- Dark theme only, `var(--accent)` as the one accent, visible labels, 44 px targets, one `h1` per screen, 200%-zoom safe, 960 px minimum width.
- Local only: no accounts, telemetry or cloud. No new Python or npm dependencies (librosa `pyin`, scipy and numpy are already present).
- Preserve: the solo preset, current exports, error-copy rules, the lead/rhythm split, `guitar_roles`, the MusicXML/GP5 exports and all their tests.

## Approaches considered
1. **Two-phase run (analysis job, then tab job) with an on-disk analysis cache. Chosen.** It gives real presence data before the user picks, and the tab phase can only reuse the cached stems, never re-separate.
2. **One job that pauses for input mid-pipeline.** Rejected: the thread would sit blocked on the user, retry would break, and cancel and back would be harder.
3. **Estimate instruments from the mix without separating.** Rejected: unreliable, and the tab phase would have to separate anyway.

For rendering: a custom SVG staff that shares the tab viewer's measure grid. Chosen over VexFlow or alphaTab because the user picked it, and because Together mode needs pixel-shared measures, playhead and loop.

## Design

### D1 — Analysis API and storage
- **Endpoints:** `POST /api/analyses` takes `{source, title, preset, config, trim_start_sec}` and returns 202 `{analysis_id}`. Also `GET /api/analyses/{id}` (snapshot), `POST /api/analyses/{id}/cancel` and `DELETE /api/analyses/{id}`.
- **Snapshot shape:** the same as a job snapshot, plus `inventory` when done, plus `fingerprint`.
- **On disk:** `data_dir/analyses/<analysis_id>/` holds:
  - `source.wav` (normalised and trimmed once)
  - `stems/{vocals,drums,bass,guitar,piano,other}.wav`
  - optional `lead_guitar.wav` / `rhythm_guitar.wav` plus `lead_rhythm_split_diagnostics.json`, or `lead_rhythm_fallback.json`
  - `stem_presence.json`, `inventory.json`, `analysis.json` (source, fingerprint, model, created_at, state)
  - `list_runs` already skips folders without `meta.json`.
- **Fingerprint** = sha1 of the source identity (upload_id, URL, or media path) plus every setting that affects separation: model/engine, guitar_checkpoint, demucs_quality, max_duration_sec, trim_start_sec.
- **How the tab job uses it:** `POST /api/jobs` gains optional `analysis_id` and `parts: string[]`. With `analysis_id`, the source is read from the analysis. If the request's separation fingerprint doesn't match, it returns 409 `analysis_mismatch`, so a tuning or capo change never invalidates the analysis. The pipeline receives an `AnalysisBundle` and skips ingest, trim and separation entirely.
- **When the run succeeds:** the cached stems move into `run/stems/` as artifacts `<stem>_stem` and the analysis folder is deleted. If the run fails, the analysis stays so retry can reuse it.
- **Lifecycle and TTL:**
  - **Back** keeps the analysis. On the next Convert, the frontend reuses it when the fingerprint matches; otherwise it sends `DELETE` and starts a new one.
  - **Cancel** deletes it once the worker stops.
  - **Sweep:** on server start, delete every `analyses/*` folder (they can't be reached after a restart). On each new `POST /api/analyses`, delete folders whose state isn't running and are older than **2 h**.
  - **Disk:** about 250 MB for a 4-minute song.

### D2 — Inventory and what can be tabbed

| id | Label | Source stem | Engine | Tab kind | Default checked |
|---|---|---|---|---|---|
| `lead` | Lead guitar | lead_guitar | existing lead path | tab (6-string) | yes, if the split succeeded |
| `rhythm` | Rhythm guitar | rhythm_guitar | existing rhythm path | tab | yes, if the split succeeded |
| `combined` | Combined guitar | guitar | existing single-guitar path | tab | yes only when the split is unavailable or failed; otherwise offered unchecked |
| `bass` | Bass | bass | Basic Pitch, range 28–67, ≤ 2 notes per onset | tab (4-string EADG) | if detected |
| `vocals` | Vocals | vocals | librosa `pyin`, segmented to notes | staff (treble) | if detected |
| `keys` | Piano / keys | piano | Basic Pitch, range 21–108, ≤ 8 notes per onset | staff (grand, split at middle C = 60) | if detected |
| `drums` | Drums (rough) | drums | band-split onsets: kick, snare, hi-hat | drums staff | if detected |
| `other` | Other instruments | other | Basic Pitch | staff (treble) | **no**: leftover mix, so it's offered but unchecked |

- **Guitar presence** uses `detect_present_stems` on the six stems. Lead and Rhythm presence comes from a second `detect_present_stems({lead, rhythm})` call.
- **Undetected rows** are still listed and can still be selected, with the copy "Barely audible, may produce few notes." They start unchecked, except Lead and Rhythm after a successful split.
- **Lead and Rhythm are always in the main grid**, detected or not.
- **Plain-English reason** comes from `presence_reason_text(p)`, for example "Clearly present: about 34% of the mix" or "Barely audible: likely not in this song". The raw technical reason stays in `inventory.json`.
- **Guitar fallback:**
  - If the split fails or is unavailable (no runtime, audio too long, `LeadRhythmSplitError`), Lead and Rhythm are greyed out ("Not separated") and **Combined guitar** is checked, with the existing fallback notice wording from `lead_rhythm_fallback.json.reason`.
  - Combined is locked while Lead or Rhythm is checked. The lock is on the picker only; the API accepts any combination.
- **At least one part must be checked.** Otherwise Start is disabled and the reason shows next to it.

### D3 — Exports
- **Single-part exports don't change.** `ExportRequest` gains an optional `part`. With no `part`, behaviour is exactly as today, guarded by the legacy test.
- **Formats by part kind:**
  - tab parts: PDF, .tab, MIDI, GP5, MusicXML
  - staff parts: MIDI, MusicXML
  - drum part: MIDI (GM channel 10, notes 36/38/42) and MusicXML percussion
  - Formats a part doesn't support are disabled with the visible reason "PDF isn't available for notation parts yet; use MusicXML".
- **Together mode** exports the focused part by default and adds "All shown parts" for MIDI (multi-track) and MusicXML (multi-part, through `write_musicxml(parts=[…])`, which already takes a list).

### D4 — Picker timing versus advanced settings
- Entry keeps the source and all settings, Advanced included.
- Convert decides the route:
  - **To the picker:** preset `full_mix`, separation on, and `caps.demucs or caps.roformer`.
  - **Straight to `POST /api/jobs` (today's path):** preset `solo`, or separation turned off. This is expected, so no notice is shown.
  - **Straight to today's path, with a notice:** separation is wanted but no separator is installed. The notice on Waiting reads "Instrument detection needs the stem separator, which isn't installed, so this converts the whole recording as one guitar tab."
- The picker has a "Change settings" link that goes back to Entry with the draft intact.

### D5 — G4 technique and acceptance

**Chosen technique:** vocal-referenced **note-level rejection with a unison guard** (`vocal_debleed.py`), applied to guitar-part note lists after transcription and before cleanup and role assignment.

**Why this technique:**
- Bleed is an attenuated copy of the singer, so a guitar note that matches the vocal f0 and is much weaker than the vocal stem at that pitch is a bleed artefact.
- A real guitar note in unison with the singer has its own pluck onset and a strong guitar-to-vocal ratio.
- Unlike spectral masking, it never touches the audio, so real guitar notes outside the vocal pitch can't be lost.
- It's measurable per note.

**A/B arm:** spectral suppression, i.e. `apply_bleed_gate` with `vocals` added to competitors and the self-competitor bug fixed. It is evaluated on the same fixture and **off by default** unless it beats the note-level arm on both metrics.

**Algorithm (per guitar note: pitch p, onset t0, end t1):**
- Vocal f0 comes from `librosa.pyin(vocals_mono, sr=22050, fmin=65, fmax=1100, frame_length=2048, hop_length=256)`, computed once.
- In the window [t0, min(t1, t0 + 0.5 s)]:
  - `match` = fraction of frames that are voiced (prob ≥ 0.5) with |midi(f0) − (p + 12k)| ≤ 0.5 for some k ∈ {−1, 0, 1}.
  - `ratio` = guitar-stem CQT magnitude at p divided by vocals-stem CQT magnitude at p, as a median over the window.
  - `pluck` = whether the guitar stem's own onset strength has a peak within 40 ms of t0 that is above 1.5 × its median.
- **Remove the note iff** `match ≥ 0.6 and ratio < 0.5 and not (pluck and ratio ≥ 0.25)`.
- All constants are module-level, recorded in diagnostics, and can be overridden for the eval.

**Gating:**
- `PipelineConfig.vocal_debleed: str = "auto"`, one of `auto | on | off`.
- `auto` means enabled iff separation ran, a `vocals` stem exists, and vocals presence is `present`.
- Kill switch: the config key `vocal_debleed: "off"` (allowed in `routes_jobs._ALLOWED_CONFIG`), plus an Advanced checkbox, on by default, labelled "Remove singing that leaks into guitar".
- Solo or unseparated input has no vocals stem, so it's a no-op and the output is byte-identical (tested).

**Diagnostics** go to `vocal_debleed_diagnostics.json`:
`{attempted, reason, enabled_by, parts{lead|rhythm|combined: {notes_in, notes_removed, removed[{start, pitch, match, ratio, pluck}]}}, thresholds{…}, vocal_voiced_fraction}`

**Acceptance on the synthetic fixture,** using `scripts/eval_tabs.note_match_f1` with ±50 ms onset tolerance:
- Vocal-pitch false notes in the guitar tab fall by **≥ 70%**, to **≤ 2** absolute.
- Guitar note recall drops by **≤ 0.02** absolute.
- The planted unison guitar note survives.

Plus one real-song manual comparison: notes removed, and a spot-check of 3 removed and 3 kept notes by ear. The user will be asked for a clip; `/Users/JJ/Downloads/フルスピード・ボーイ.mp3` was used before.

### D6 — Result bar and persistence
**Control bar:**
- A View segmented control (`role="radiogroup"`): **Single | Together**.
- **Single:** a `role="tablist"` of selected parts. Each is `role="tab"` with `aria-selected`, roving tabindex, ←/→/Home/End navigation, and `aria-controls` pointing at the sheet.
- **Together:** toggle chips (`aria-pressed`) choose which parts are shown, with at least one required.
- Shortcut `T` toggles the view. It's added to TabPlayer's Keys list and has no conflict with Space, [, ], L, Esc, −, = or M/C.

**Together rendering:**
- One sheet. Each measure is a column holding N staves (tab, staff or drums).
- The column width is the maximum across the shown tracks. Each staff has a short label on the left of the first measure of each line.
- One cursor spans every stave, with one follow-scroll and one pointer/loop handler. Bar numbers sit on the top staff.
- Measures use `content-visibility: auto` so three tracks over a long song stay smooth.
- Measures are shared because every part is quantised onto **one run-level beat grid** (`grid.json`, built from the guitar stem exactly as the lead/rhythm path does today, so guitar output doesn't regress).

**Persistence:** `PUT /api/runs/{id}/view` takes `{mode, part, shown[]}` and merges into `meta.json` under the `view` key. It's read back through run meta, and unknown ids are dropped. Tuning, capo, transpose and bars changes re-fetch the score but leave the selection alone. Switching parts is client-side only, since `tab.tracks` already holds every track.

**Settings scope:** tuning and capo apply to guitar tab parts; transpose applies to every pitched part; drums are unaffected.

**Legacy runs:** with no `details.parts`, parts and the payload come from today's logic unchanged (snapshot test).

**Listen sources:** `AudioKind` becomes `'original' | 'stem' | 'lead' | 'rhythm' | `part:${string}``. The new kinds map to `<id>_stem` artifacts, and the old kinds keep working.

## Builder calls (settled here)
- `combined` keeps id `combined`, and its label changes from "Guitar" to "Combined guitar" only in new runs (legacy label kept).
- The role repair needs both stems, so if only one of Lead and Rhythm is selected, both are still transcribed internally and only the selected one is shown or exported.
- The `other` stem is offered unchecked.
- The analysis always uses a 6-stem separator: guitar-ft htdemucs_6s when its weights are cached, otherwise htdemucs_6s, or `bs_roformer_sw` if the user picked it explicitly. A MelBand guitar engine choice becomes `guitar_refine` on the cached guitar stem.
