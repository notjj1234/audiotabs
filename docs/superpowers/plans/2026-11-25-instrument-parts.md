# Instrument Parts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-11-25-instrument-parts-design.md`

**Goal:** Two-phase conversion (analysis, picker, tab job), a generic multi-part result with a Together view, every instrument tabbable (guitar first), and de-bleed driven by the vocals stem.

**Architecture:**
- Split separation into "run model, keep every stem" and "post-process guitar".
- Add an `AnalysisManager` on top of the `JobManager` patterns, with cooperative cancel.
- `run_pipeline` accepts an `AnalysisBundle` plus `parts`.
- A server parts registry drives a generic `tracks[]` payload rendered by a multi-staff viewer.

**Tech stack:** FastAPI, Svelte 5 runes, Demucs/htdemucs_6s, Mel-Band RoFormer, Basic Pitch, librosa (pyin and onsets), scipy, vitest, pytest.

## Global constraints
- No new dependencies. No commits or pushes (the user tests the working tree). Never revert the user's WIP; build on it.
- All UI colour comes from `app.css` tokens. Targets are ≥ 44 px, labels visible, one `h1`, safe at 960 px and 200% zoom.
- Error copy goes through `user_facing_message`. No raw exceptions reach the UI.
- Legacy runs and the solo preset must behave byte-for-byte as before.

## Review focus
Each item below is pinned by a test in the task named.
1. **Cancel during the in-process guitar-ft or Mel-Band inference,** which can't be interrupted. The UI should return straight away, and the worker should clean up at the next check without writing an orphan run. (Task 2.3: test the cancel flag set mid-stage, the folder removed, state `cancelled`.)
2. **Back, then a settings change, then Convert:** reuse the analysis when the fingerprint matches, otherwise delete and re-analyse. Must never separate twice for the same fingerprint. (Task 4.1: fingerprint test; Task 3.1: counter test.)
3. **A song with no detected guitar** (piano ballad): the guitar rows show as undetected and unchecked, keys is checked, and the run produces only a keys staff with no empty guitar tab. (Task 3.2.)
4. **Lead/Rhythm split refused for long audio:** show the Combined row checked with the fallback reason, and never a silent single tab. (Task 2.2.)
5. **A part transcribes to zero notes** (for example drums on an acoustic track): the part shows "No notes found in this part", other parts still render, and the job doesn't fail. Today `EmptyTranscriptionError` would fail it. (Task 3.2.)

---

### Phase 0 — Setup (no product code)
**Task 0.1:** Run `git checkout -b feat/instrument-parts`, which keeps the WIP in place. Run the baseline with the verification commands below and record any failures that already exist, so they aren't blamed on this work.

**Task 0.2:** Write the spec (Part A) and plan (Part B) into `docs/superpowers/…` in the repo formats.

**Task 0.3:** Run `graphify update .`.

### Phase 1 — Foundation: one separation, cooperative cancel
**Task 1.1: Split separation into run and post-process** (`src/audio_to_tab/separate.py`, `tests/test_separate_split.py`)
- Produces:
  - `run_full_separation(src: Path, out_dir: Path, *, model: str, guitar_checkpoint: str|None, device: str, quality: str, demucs_segment: int|None, demucs_jobs: int, should_abort: Callable[[], bool]|None = None, on_progress=None) -> dict[str, Path]` keeps every stem the model writes.
  - `postprocess_guitar_stem(stems: dict[str, Path], out: Path, *, guitar_refine, fold_other_mode, bleed_gate, bleed_gate_competitors: tuple[str,...] = ("other","bass","drums"), sub_bass_debleed, low_end_restore_db, adaptive_fold_gain, guitar_ensemble_src: Path|None, recovery_diagnostics_path, bleed_gate_diagnostics_path, device, model) -> Path`.
  - `separate_guitar_stem(...)` keeps its signature and becomes run plus post-process.
  - Module counter `SEPARATION_CALLS: int`, incremented in `run_full_separation`, used by the tests.
- Tests:
  - All existing `test_pipeline_guitar.py`, `test_separate_progress.py` and `test_scnet.py` stay green.
  - `test_bleed_gate_excludes_guitar_self` fails before the fix: the competitors passed to `apply_bleed_gate` never contain `"guitar"`.
  - `test_run_full_separation_keeps_six_stems` uses the faked Demucs output pattern from `test_pipeline_guitar.py:147`.

**Task 1.2: Cancel token** (`src/audio_to_tab/cancel.py`, `app/server/jobs.py`, `app/server/routes_jobs.py`, `tests/test_api_jobs.py`)
- Produces:
  - `class CancelToken` with `cancel()`, `is_cancelled() -> bool` and `check()`; `check()` raises `subprocess_util.JobAborted`.
  - `JobRecord.state` adds `cancelling | cancelled`.
  - `JobManager.cancel(job_id) -> bool`.
  - `POST /api/jobs/{id}/cancel` returns 202.
  - `run_pipeline(..., cancel: CancelToken|None = None)` calls `cancel.check()` at each progress call and passes `should_abort=cancel.is_cancelled` into `run_demucs`.
- On `JobAborted`, the job state becomes `cancelled`, the output dir is removed, and no `meta.json` is written.
- Tests:
  - `test_cancel_between_stages_removes_folder` uses a fake runner that blocks on an Event and calls `on_progress`.
  - `test_cancel_unknown_job_404`.
  - The existing retry tests still pass.

### Phase 2 — Analysis phase (backend)
**Task 2.1: Inventory model** (`src/audio_to_tab/inventory.py`, `tests/test_inventory.py`)
- Produces:
  - `@dataclass PartCandidate(id, label, family, stem, detected: bool, confidence: float, reason: str, tabbable: bool, tab_kind: Literal["tab","staff","drums"], default_selected: bool, note: str|None)`.
  - `presence_reason_text(p: StemPresence) -> str`.
  - `build_inventory(presence: dict[str, StemPresence], *, lead_rhythm: LeadRhythmOutcome) -> list[PartCandidate]`.
  - `@dataclass LeadRhythmOutcome(ok: bool, reason: str|None, presence: dict[str, StemPresence])`.
- Tests:
  - Split ok: lead and rhythm checked, combined offered unchecked.
  - Split failed: only combined, checked, with the reason in the note.
  - `other` is never default-checked.
  - Undetected rows are unchecked.
  - Drums: `tab_kind == "drums"`.
  - The reason text contains no "dBFS".

**Task 2.2: `run_analysis`** (`src/audio_to_tab/analysis.py`, `tests/test_analysis.py`)
- Produces:
  - `@dataclass AnalysisBundle(dir: Path, work_audio: Path, stems: dict[str, Path], lead_rhythm: LeadRhythmOutcome, lead_rhythm_paths: dict[str, Path], inventory: list[PartCandidate], model: str, fingerprint: str)`.
  - `run_analysis(*, audio_path, youtube_url, analysis_dir, config: PipelineConfig, on_progress, cancel: CancelToken) -> AnalysisBundle`.
  - `load_analysis(dir: Path) -> AnalysisBundle`.
  - `analysis_fingerprint(source: dict, config: PipelineConfig, trim_start_sec: float) -> str`.
- Stages: `ingest` → `separate` → `split` → `detect`, using the progress rows from `progress_checklist.new_analysis_checklist()`. The split reuses `lead_rhythm_sep.run_lead_rhythm_split` and catches `LeadRhythmSplitError` and the long-audio refusal into the outcome.
- Ingest and trim come out of `pipeline.py:254-266` into a shared helper, `prepare_work_audio(...)`, so both phases use one code path. This also honours `trim_start_sec`, which today is ignored.
- Tests (monkeypatching `run_full_separation` and `run_lead_rhythm_split`):
  - The bundle round-trips through `load_analysis`.
  - Split failure produces the Combined-only inventory.
  - Long-audio refusal produces the fallback (Review Focus 4).
  - Cancel after separate leaves no folder.

**Task 2.3: AnalysisManager and routes** (`app/server/analyses.py`, `app/server/routes_analyses.py`, `app/server/main.py`, `app/server/schemas.py`, `tests/test_api_analyses.py`)
- Produces `AnalysisManager(data_dir, runner=None)` with `start`, `get`, `snapshot`, `cancel`, `delete` and `sweep(max_age_sec=7200, all_idle=False)`, plus the four endpoints from D1.
- Source resolution is shared with `routes_jobs` by moving `_resolve_upload` and the media-URL download into a helper.
- `sweep(all_idle=True)` runs on app startup.
- Tests:
  - start, poll, then done with inventory
  - cancel produces `cancelled` and removes the dir (Review Focus 1)
  - delete removes the dir
  - the sweep removes idle folders older than the TTL and keeps running ones
  - unknown config gives 422
  - error copy contains no raw exception text

### Phase 3 — Tab phase reuses the analysis
**Task 3.1: Pipeline consumes `AnalysisBundle` and `parts`** (`src/audio_to_tab/pipeline.py`, `tests/test_pipeline_analysis.py`)
- Changes `run_pipeline(..., analysis: AnalysisBundle|None = None, parts: list[str]|None = None, cancel=None)`.
- With `analysis` set:
  - No ingest, trim or separation. It copies `work_audio` to `playback.wav` and calls `postprocess_guitar_stem` on the cached stems.
  - If the split succeeded, lead/rhythm reuse the cached lead and rhythm stems in `_run_lead_rhythm_stage` through a new `split_paths` argument.
  - A combined transcription runs only when `combined` is selected (artifacts `combined_midi` / `combined_result`).
- `parts=None` keeps today's behaviour.
- Writes `grid.json` (beats and downbeats, BPM, meter) and `details.parts`.
- Tests:
  - `test_tab_phase_never_separates`: `SEPARATION_CALLS` and the yt-dlp download stub stay at 0 across the job.
  - Lead-only selection hides rhythm in `details.parts`.
  - `parts=None` produces the same artifacts as today.

**Task 3.2: Per-part transcription for non-guitar families** (`src/audio_to_tab/part_transcribe.py`, `src/audio_to_tab/drum_transcribe.py`, `src/audio_to_tab/vocal_notes.py`, `tests/test_part_transcribe.py`, `tests/test_drum_transcribe.py`, `tests/test_vocal_notes.py`)
- Produces:
  - `transcribe_part(part_id: str, stem: Path, out_dir: Path, *, grid: BeatGrid, cfg: PipelineConfig) -> PartResult`.
  - `@dataclass PartResult(part_id, kind, midi: Path|None, result: Path|None, note_count: int, empty_reason: str|None)`.
  - `vocal_notes.pyin_notes(path, *, min_dur=0.10, merge_gap=0.05) -> list[Note]`.
  - `drum_transcribe.transcribe_drums(path) -> list[DrumHit(start, piece: Literal["kick","snare","hihat"], velocity)]`. Bands: kick below 150 Hz; snare 150–2500 Hz plus broadband flux; hi-hat above 6 kHz. Onsets come from `librosa.onset.onset_detect` per band.
- Staff and drum `result.json` shape: `{kind, clef?, notes|hits, tempo_bpm, beats_per_measure}`.
- Zero notes produce `empty_reason` and never raise (Review Focus 5). Bass goes through Task 7.1.
- Tests use synthetic sines, a gliding sine with vibrato, and clicks with band-limited noise:
  - pyin recovers the planted melody within 50 ms and the correct pitch
  - kick, snare and hi-hat each classified at ≥ 80% on the planted pattern
  - silence produces `empty_reason`
  - a no-guitar inventory produces only the keys result (Review Focus 3)

**Task 3.3: Jobs accept `analysis_id` and `parts`** (`app/server/routes_jobs.py`, `app/server/jobs.py`, `app/server/schemas.py`, `tests/test_api_jobs.py`)
- `JobRequest` gains `analysis_id: str|None` and `parts: list[str]|None`.
- Validation:
  - Fingerprint mismatch returns 409 `analysis_mismatch`.
  - An empty `parts` list returns 422 `no_parts`.
  - Unknown part ids return 422.
- On success, stems move into the run and the analysis is deleted. `details` gains `parts`, `inventory` and `lead_rhythm_fallback` (unchanged contract).
- Tests: reuse from a fake analysis; 409 on mismatch; 422 on empty parts; the analysis dir is gone after success and kept after failure.

### Phase 4 — Picker UI (G1/G2)
Load `impeccable` before this phase.

**Task 4.1: Lift the Entry draft and route on Convert** (`app/web/src/App.svelte`, `app/web/src/lib/screens/Entry.svelte`, `app/web/src/lib/components/AppBar.svelte`, `app/web/src/lib/convertFlow.ts`, `app/web/src/lib/convertFlow.test.ts`)
- Produces:
  - `type EntryDraft` holding the source tab, the upload/URL fields, title and every setting.
  - `routeForConvert(draft, caps): 'picker' | 'direct' | 'direct_with_notice'`.
  - `analysisFingerprint(draft): string`, matching the server fields.
  - `Screen` adds `'analyzing' | 'instruments'`, in both unions.
- Entry takes `bind:draft` and an `onconvert` prop instead of POSTing.
- Tests: the routing table from D4, and that the fingerprint ignores tuning, capo and fingering.

**Task 4.2: Analysis progress with a real cancel** (`app/web/src/lib/screens/Waiting.svelte`, `app/web/src/lib/api.ts`)
- Waiting gains `kind: 'job' | 'analysis'` and a Cancel button that's always visible (44 px, `ghost`). Cancel POSTs `/cancel`, shows "Cancelling…" for that click, and returns to Entry straight away with the draft intact.
- It renders the `notice` prop for `direct_with_notice`.

**Task 4.3: Instruments screen** (`app/web/src/lib/screens/Instruments.svelte`, `app/web/src/lib/partsSelection.ts`, `app/web/src/lib/partsSelection.test.ts`)
- Layout:
  - `h1` "Instruments in this song"
  - a Guitar group first, with Lead, Rhythm and Combined rows
  - then the other instruments
- Each row is a native checkbox inside a label, at least 44 px, showing the name, a detected/not-detected chip, "confidence 82%", and the plain reason. The kind hint reads "Tab", "Notation" or "Drum hits (rough)".
- The fallback notice sits in the guitar group.
- Footer: "Change settings" (Back) and the primary button "Tab N parts", disabled with a reason when N = 0.
- Produces: `defaultSelection(inv)`, `toggle(sel, id)`, `selectionNote(sel, inv)` (the Combined-repeats note) and `canStart(sel)`.
- Tests: defaults per D2, the at-least-one rule, and the Combined note.

**Checkpoint A** (with the user): the guitar path works end to end. Upload and YouTube both reach the picker, the counter shows one separation, cancel and back work, and the result shows Lead and Rhythm in the existing single view. Run the verification commands.

### Phase 5 — Generic parts model and Together (G3)
**Task 5.1: Parts registry and generic payload** (`app/server/parts.py`, `app/server/score.py`, `tests/test_score_tracks.py`, `tests/test_score_parts.py`)
- Produces:
  - `PartSpec(id, label, kind, midi_key, result_key, audio_key)`.
  - `available_parts(record) -> list[str]`. It reads `details.parts` when present and otherwise falls back to the current logic, moved here unchanged.
  - `build_tab_payload` emits `tracks[{id, label, kind, strings?, clef?, events, empty_reason?}]` on the shared `grid.json` measures.
  - Staff events carry `pitch` and `spelling` (sharps only). Drum events carry `piece`.
- `_TRACK_LABELS` and the hardcoded triple are removed in favour of the registry.
- Tests: a legacy fixture's payload is byte-identical to a snapshot taken before the change, and a five-part run produces five tracks with shared measure indices.

**Task 5.2: View state and part-aware export and audio** (`app/server/routes_runs.py`, `app/server/score.py` `export_run`, `tests/test_api_runs.py`)
- `PUT /api/runs/{id}/view`.
- `ExportRequest.part` is optional; `all_shown: bool` applies to MIDI and MusicXML only.
- The audio `kind=part:<id>` maps to the `<id>_stem` artifact.
- Tests: an export with no `part` is byte-identical to today; view state round-trips and invalid ids are dropped; an unsupported format for a part returns 422 with a friendly message.

**Task 5.3: Multi-staff viewer** (`app/web/src/lib/components/TabViewer.svelte` (refactored in place), `app/web/src/lib/components/staves/TabStaff.svelte`, `NotationStaff.svelte`, `DrumStaff.svelte`, `app/web/src/lib/notation.ts`, `notation.test.ts`, `tabModel.ts`)
- TabViewer's props change from `trackId` to `trackIds: string[]`. Each measure is a column of staves.
- The existing tab markup moves into `TabStaff` unchanged.
- One cursor, one follow-scroll, one pointer/loop handler, and `content-visibility: auto`.
- `notation.ts` produces:
  - `staffStep(pitch, clef) -> number` (diatonic step from the bottom line)
  - `accidental(pitch) -> '#' | null`
  - `ledgerLines(step) -> number[]`
  - `splitGrand(notes, 60)`
  - `drumRow(piece) -> number`
- Tests: E4 on treble sits on the bottom line, C4 needs one ledger below, F#4 gets a sharp, the grand split at 60, and the drum rows.

**Task 5.4: Result control bar** (`app/web/src/lib/screens/Result.svelte`, `app/web/src/lib/scoreParts.ts` (generalised: `ScorePart = string`), `scoreParts.test.ts`, `TabPlayer.svelte` (keys list and per-part listen options))
- The View radiogroup, the Single tablist with roving tabindex and arrow keys, and the Together chips with at-least-one.
- The `T` shortcut. The selection is held outside the score fetch and saved through PUT view with a 300 ms debounce. The export menu is per part, with "All shown parts".
- Tests: `scoreParts.test.ts` covers `nextTab(ids, cur, key)`, `restoreView(saved, available)` and the defaults for legacy parts.

**Checkpoint B:** a three-part run in Together mode, with the playhead and loop spanning every stave; check 960 px and 200% zoom; run the verification commands.

### Phase 6 — De-bleed (G4)
**Task 6.1: Synthetic fixture and eval helpers** (`tests/audio_fixtures.py`, `tests/test_vocal_debleed_eval.py`)
- Produces:
  - `pluck(freq, dur, sr, seed)` (Karplus-Strong)
  - `vocal_tone(melody, sr)` (sine plus three harmonics, 5.5 Hz vibrato at ±30 cents, 40 ms attack)
  - `make_bleed_fixture(tmp) -> (guitar_stem, vocals_stem, guitar_ref_mid, vocal_ref_mid)`
- The fixture plants 16 guitar notes and a 12-note vocal melody that's disjoint in pitch except for one unison note. Bleed is mixed in at 0.3 (−10 dB).
- Metrics come from `scripts.eval_tabs.note_match_f1`:
  - recall against `guitar_ref`
  - vocal-pitch notes = hypothesis notes that match `vocal_ref` and don't match `guitar_ref`
- It runs real Basic Pitch and skips if `basic_pitch` can't be imported. It prints a before/after JSON table.

**Task 6.2: `vocal_debleed.py`** (`src/audio_to_tab/vocal_debleed.py`, `src/audio_to_tab/pipeline.py`, `tests/test_vocal_debleed.py`)
- Produces:
  - `VocalPitchTrack.from_stem(path)`
  - `reject_vocal_bleed(notes: list[pretty_midi.Note], guitar_stem: Path, track: VocalPitchTrack, *, thresholds=DEFAULTS) -> tuple[list[Note], PartDebleedReport]`
  - `VocalDebleedDiagnostics` (dataclass with `write_json`, matching the existing diagnostics pattern)
  - `resolve_vocal_debleed(cfg, stems, presence) -> tuple[bool, str]`
- It's wired after transcription for `combined`, and for lead and rhythm before `_apply_role_check`.
- Deterministic unit tests (synthetic f0 arrays and note lists, no Basic Pitch):
  - match plus low ratio removes the note
  - a unison note with a pluck is kept
  - an octave match is removed
  - `auto` is off without vocals and off for solo
  - `off` skips
  - the solo pipeline output is byte-identical (artifact hashes)
- The eval test asserts the D5 thresholds.
- A/B arm: rerun the eval with `bleed_gate=True` plus the vocals competitor. Record both rows in the research doc and keep the spectral arm off by default unless it wins both metrics.
- If the thresholds are missed: load `systematic-debugging` and change one variable at a time (window, ratio, match), logging each eval row.

**Task 6.3: Kill switch in the UI** (`routes_jobs._ALLOWED_CONFIG`, Entry Advanced checkbox "Remove singing that leaks into guitar", default on). Test: the config key passes through, and `"off"` disables the stage.

**Checkpoint C:** the eval numbers are pasted into the research doc, plus the real-song comparison (ask the user for a clip).

### Phase 7 — Bass tab
**Task 7.1: Generalise the string count** (`tab_generate.py`, `tuning.py`, `tab_bundle.py`, `musicxml_export.py`, `gp5_export.py`, `tests/test_tab.py`, `tests/test_bass_tab.py`)
- Strings come from `len(tuning)`. Adds tuning `"Bass standard (EADG)"` = (28, 33, 38, 43).
- `read` accepts tuning lists of 4 to 7 strings.
- Tests:
  - every existing 6-string test unchanged
  - a 4-string doc renders 4 tab lines
  - the MusicXML staff has 4 lines
  - GP5 writes a 4-string track (if `guitarpro` is present)
- Wire `bass` in `part_transcribe` (Basic Pitch range 28–67, `max_notes_per_onset=2`).

### Phase 8 — Notation parts in the viewer and exports
**Task 8.1:** Implement `NotationStaff` (treble and grand) and `DrumStaff` (3-line kit: kick, snare, hi-hat with an x-head). These are the components Task 5.3 created as stubs, now filled in with rhythm stems and beams reusing the `tab_rhythm` payload. Add MusicXML pitched and percussion parts and multi-track MIDI. Tests: `notation.test.ts` additions; `test_musicxml_export.py` checks a pitched part has no `<technical><fret>` and a percussion part uses `<unpitched>`.

### Phase 9 — Docs, screenshots, review, verification
**Task 9.1:** Update docs:
- `docs/lead-rhythm-split.md`: the split now runs in analysis, plus the picker rows and fallback.
- The research doc: mark the P2 "keep the full htdemucs_6s stem set" as done; add the G4 eval table and the drums heuristic with its limits.
- README: the new flow.
- PRODUCT.md: multi-part tab and notation parts; note the accent mismatch.

**Task 9.2:** Screenshots of the picker and the Together view at 960×720 and 1440×900. Use the `agent-browser` skill against a seeded three-part fixture run and one real run. Save them under `docs/ui-audit/2026-11-25-instrument-parts/`.

**Task 9.3:** Run `verification-before-completion` (the commands below), then `requesting-code-review` over the whole diff, then hand back with no commits.

## Risks
| Risk | Impact | Mitigation |
|---|---|---|
| The wait before the picker grows (6-stem separation plus the Mel-Band split, possibly 3–6 min on CPU) | High (UX) | Real staged progress and a working cancel. The analysis is reused on Back. The split's long-audio guard falls back to Combined. |
| In-process inference can't be interrupted | Med | Cancel returns the UI immediately and the worker cleans up at the next check (Review Focus 1). |
| The tab engine's 6-string assumptions run deeper than the two known sites | Med | Phase 7 sits after the guitar phases. The existing tests guard the 6-string path, and if it gets too big, bass ships behind the generic model last. |
| The custom notation staff is basic (no key signature or rests) | Med | Labelled v1 in the docs. MusicXML export gives full notation in other apps. |
| Heuristic drums are inaccurate | Med | Labelled "Drum hits (rough)" in the picker and on the staff. Only kick, snare and hi-hat. |
| De-bleed removes real unison guitar | High | The unison guard, the planted unison test, the ≤ 0.02 recall-drop gate, and the `off` kill switch. |
| Disk use from cached stems (~250 MB per analysis) | Low | The 2 h TTL sweep, deletion on cancel and on consume, and the startup sweep. |
| The user's in-progress WIP conflicts in jobs, score, pipeline, Result, TabViewer and Waiting | Med | Build on the current working tree, never revert, ask on any semantic conflict. No commits. |
| Long-song DOM cost with 3 or more staves | Med | `content-visibility: auto`, client-side part switching, no re-fetch on switch. |
| pyin runtime on long vocals (~20–60 s) | Low | Computed once and shared by de-bleed and vocal notes. |

## Verification (run and paste the output)
```bash
PYTHONPATH=src:. .venv311/bin/python -m pytest tests/ -q
cd app/web && npm run check && npm test && npm run build
PYTHONPATH=src:. .venv311/bin/python -m app.server --port 8533   # manual smoke
```
Manual smoke steps:
1. Upload a clip and convert. The picker appears with staged progress, `SEPARATION_CALLS == 1` shows in the log, and the defaults are correct.
2. Cancel mid-analysis. You're back on Entry with the draft intact and the analysis folder is gone.
3. Back from the picker and change the capo. The analysis is reused.
4. YouTube URL: same as step 1.
5. Three-part result: Single and Together, keyboard tablist, `T`, loop over every stave, reload and the view is restored.
6. Solo preset: no picker, and output identical to before.
7. Legacy run from `data/ui_runs`: opens exactly as before.
