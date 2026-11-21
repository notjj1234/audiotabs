# Phase A: Result & Wait Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the competitor Phase A gaps: progress elapsed + tip, Original vs Guitar-stem listen, export audience subtitles, and typed failure recovery CTAs — without rebuilding the checklist, player speeds/loop/metronome, or download popover that already exist.

**Architecture:** Keep pure helpers in `src/audio_to_tab/` (progress tip/elapsed formatting, listen-source resolution, download subtitles, failure kinds). Extend `progress_card_html` and thin Streamlit wiring in `ui/tab_pdf.py` / `ui/studio_shell.py`. No new packages; Guitar stem replaces the ruled-out fluidsynth Synth path.

**Tech Stack:** Python 3.11, Streamlit, existing `player_bar` / `progress_checklist` / `tab_bundle` / `user_errors`.

**Spec:** `docs/superpowers/plans/2026-11-18-competitor-ui-workflow-findings.md` §9 Phase A (items 1–5).

## Global Constraints

- Python `>=3.10,<3.13`. Do not add a dependency, network host, account, or paywall control.
- Do not add a Synth / fluidsynth listen path; use **Original** and optional **Guitar stem** only (prior ruling in `2026-11-10-tab-result.md`).
- Speeds `0.25 / 0.5 / 0.75 / 1`, loop drag, and metronome stay as implemented in `player_html`; this plan does not rework the player JS.
- Checklist stage ids stay `ingest | separate | transcribe | tab | chords | lyrics | pdf` from `progress_checklist.STAGES`.
- `.tab` download stays unwrapped; on-screen wrap unchanged.
- Do not commit unless the user explicitly asks. Skip every Commit step below (user rule overrides).
- Prefer the smallest Streamlit-native diff; no new routes or pages.

## Review Focus

- Progress card with `elapsed_sec=0` and empty tip must still render % and rows (no blank head). Test: `test_progress_card_html_with_zero_elapsed_and_no_tip`.
- When artifacts have no `guitar_stem` file, listen options are Original-only and the Streamlit radio is not shown. Test: `test_listen_options_omit_missing_stem`.
- Download items without a subtitle key must not crash the popover; subtitle is optional for callers that only use `label`. Test: `test_download_menu_includes_audience_subtitles`.
- `EmptyTranscriptionError` still clears downloads and offers Solo + Expert recovery. Test: `test_failure_ux_empty_keeps_solo_and_expert_actions` (+ existing `test_empty_transcription_writes_no_downloads`).
- YouTube failure recovery must not set empty-recovery buttons. Test: `test_failure_ux_youtube_kind_has_upload_action_only`.

## File map

| File | Responsibility |
| --- | --- |
| `src/audio_to_tab/progress_tips.py` | Tip strings keyed by stage id; `format_elapsed(seconds) -> str` |
| `ui/studio_shell.py` | `progress_card_html` accepts `elapsed_sec` + `tip` |
| `src/audio_to_tab/player_bar.py` | `listen_options(artifacts) -> list[dict]` (`key`, `label`, `path`) |
| `ui/tab_pdf.py` | Paint elapsed/tip during run; source radio; download subtitle caption; recovery CTAs by kind |
| `src/audio_to_tab/tab_bundle.py` | `DOWNLOAD_SPECS` + `download_menu` include `subtitle` |
| `src/audio_to_tab/user_errors.py` | `failure_kind` + `failure_actions` beside `user_facing_message` |
| `tests/test_studio_ui.py` | Progress card elapsed/tip |
| `tests/test_result_studio.py` | Listen options + download subtitles |
| `tests/test_failure_ux_contracts.py` | Failure kinds / action ids (source + pure helpers) |

## Already shipped (do not rebuild)

- Named checklist + weighted % (`progress_checklist` + `progress_card_html`)
- Practice player speeds, loop, metronome, waveform tip (`player_bar.player_html`)
- Download popover listing PDF / MIDI / ASCII tab / GP5 / Guitar stem when files exist
- Empty-transcription Solo / Expert buttons (`tab_pdf_empty_recovery`)

---

### Task 1: Progress elapsed time + stage tip

**Files:**
- Create: `src/audio_to_tab/progress_tips.py`
- Modify: `ui/studio_shell.py` (`progress_card_html`)
- Modify: `ui/tab_pdf.py` (`_paint_checklist`, `_execute_pending.on_progress`)
- Test: `tests/test_studio_ui.py`

**Interfaces:**
- Consumes: `progress_checklist.STAGES` ids
- Produces:
  - `format_elapsed(seconds: float) -> str` → `"0:00"` / `"1:05"` (floor, never negative)
  - `progress_tip_for(stage_id: str) -> str` → non-empty tip for known ids; `""` for unknown
  - `progress_card_html(rows, *, elapsed_sec: float | None = None, tip: str | None = None) -> str`
  - `_paint_checklist(slot, rows, *, elapsed_sec: float | None = None, tip: str | None = None) -> None`

**Locked tip copy (exact):**

| stage_id | tip |
| --- | --- |
| `ingest` | `Large or remote files take longer to load.` |
| `separate` | `Full-band mixes take longer than clean solo guitar.` |
| `transcribe` | `Busy mixes may need the Solo / fingerstyle preset.` |
| `tab` | `Fret positions are a draft — check them before you trust them.` |
| `chords` | `Chord names follow the sounding pitch after capo and transpose.` |
| `lyrics` | `Lyrics appear only when a vocal stem and transcriber are available.` |
| `pdf` | `Writing the PDF and download files.` |

- [ ] **Step 1: Write the failing tests**

```python
def test_format_elapsed_floors_and_clamps():
    from audio_to_tab.progress_tips import format_elapsed
    assert format_elapsed(-1) == "0:00"
    assert format_elapsed(65.9) == "1:05"

def test_progress_tip_for_known_and_unknown_stages():
    from audio_to_tab.progress_tips import progress_tip_for
    assert "solo guitar" in progress_tip_for("separate").lower()
    assert progress_tip_for("tempo") == ""

def test_progress_card_html_shows_elapsed_and_tip():
    from ui.studio_shell import progress_card_html
    html = progress_card_html(
        [{"id": "separate", "state": "active", "label": "Separating stems", "detail": "", "fraction": "0.2"}],
        elapsed_sec=65.0,
        tip="Full-band mixes take longer than clean solo guitar.",
    )
    assert "Elapsed 1:05" in html
    assert "Full-band mixes take longer than clean solo guitar." in html
    assert 'class="studio-progress-tip"' in html

def test_progress_card_html_with_zero_elapsed_and_no_tip():
    from ui.studio_shell import progress_card_html
    html = progress_card_html(
        [{"id": "ingest", "state": "active", "label": "Loading audio", "detail": "", "fraction": "0.05"}],
        elapsed_sec=0.0,
        tip="",
    )
    assert "Elapsed 0:00" in html
    assert "studio-progress-tip" not in html
    assert "Loading audio" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_studio_ui.py::test_format_elapsed_floors_and_clamps tests/test_studio_ui.py::test_progress_tip_for_known_and_unknown_stages tests/test_studio_ui.py::test_progress_card_html_shows_elapsed_and_tip tests/test_studio_ui.py::test_progress_card_html_with_zero_elapsed_and_no_tip -v`  
Expected: FAIL (import / missing elapsed markup)

- [ ] **Step 3: Implement helpers + HTML + wiring**

In `progress_tips.py`, implement `format_elapsed` and `progress_tip_for` with the locked table.  
In `progress_card_html`, after the `%` / heading head, when `elapsed_sec is not None` render `<span class="studio-progress-elapsed">Elapsed {format_elapsed(...)}</span>`; when `tip` is non-empty after strip, render `<p class="studio-progress-tip">…</p>` under the bar (before `<ul>`).  
In `_execute_pending`, `t0 = time.monotonic()` before `run_pipeline`; `on_progress` computes `elapsed_sec = time.monotonic() - t0`, finds the active row id, and passes `tip=progress_tip_for(active_id)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: same pytest line as Step 2  
Expected: PASS

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 2: Original vs Guitar-stem listen toggle

**Files:**
- Modify: `src/audio_to_tab/player_bar.py`
- Modify: `ui/tab_pdf.py` (`_render_result` player block ~670–679)
- Test: `tests/test_result_studio.py`

**Interfaces:**
- Consumes: artifact keys `playback`, `guitar_stem` (string paths)
- Produces: `listen_options(artifacts: dict | None) -> list[dict]`  
  Each dict: `{"key": "original"|"guitar_stem", "label": "Original"|"Guitar stem", "path": Path}`  
  Include a row only when `Path(str(raw)).is_file()`. Prefer order Original then Guitar stem.

**Rulings:**
- Do not call `synth_source_available` for UI. Leave the function in place for existing tests.
- Changing listen source does not change tab/MIDI; only which WAV the player loads.
- Default selection: `original` if present, else first available option.

- [ ] **Step 1: Write the failing tests**

```python
def test_listen_options_original_and_stem(tmp_path: Path):
    from audio_to_tab.player_bar import listen_options
    original = tmp_path / "playback.wav"
    stem = tmp_path / "guitar_stem.wav"
    original.write_bytes(b"RIFF")
    stem.write_bytes(b"RIFF")
    opts = listen_options({"playback": original, "guitar_stem": stem})
    assert [o["key"] for o in opts] == ["original", "guitar_stem"]
    assert [o["label"] for o in opts] == ["Original", "Guitar stem"]

def test_listen_options_omit_missing_stem(tmp_path: Path):
    from audio_to_tab.player_bar import listen_options
    original = tmp_path / "playback.wav"
    original.write_bytes(b"RIFF")
    opts = listen_options({"playback": original, "guitar_stem": tmp_path / "missing.wav"})
    assert [o["key"] for o in opts] == ["original"]
```

Also extend an existing source-contract test (or add one) that `ui/tab_pdf.py` source contains `listen_options` and `tab_listen_source`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_result_studio.py::test_listen_options_original_and_stem tests/test_result_studio.py::test_listen_options_omit_missing_stem -v`  
Expected: FAIL with `listen_options` not defined

- [ ] **Step 3: Implement `listen_options` and wire the result player**

Before `_render_player` in the result path:
1. `opts = listen_options(artifacts)`
2. If `len(opts) > 1`, `st.radio("Listen", …, format_func=label, key="tab_listen_source", horizontal=True)` using option keys.
3. Resolve selected path from `opts`; call `_render_player(selected, …)`.
4. Update the caption: when stem is selected, say you are hearing the guitar stem; when original, keep “Playing the original audio…”.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_result_studio.py::test_listen_options_original_and_stem tests/test_result_studio.py::test_listen_options_omit_missing_stem tests/test_result_studio.py::test_player_speed_keeps_quarter_speed -v`  
Expected: PASS (speeds regression still green)

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 3: Export menu audience subtitles

**Files:**
- Modify: `src/audio_to_tab/tab_bundle.py` (`DOWNLOAD_SPECS`, `download_menu`)
- Modify: `ui/tab_pdf.py` (Download popover loop)
- Test: `tests/test_result_studio.py`

**Interfaces:**
- Consumes: existing artifact keys
- Produces: `download_menu` items include `"subtitle": str` (may be `""`)

**Locked subtitle copy (exact):**

| key | label (unchanged) | subtitle |
| --- | --- | --- |
| `pdf` | `PDF` | `Printable chart` |
| `midi` | `MIDI` | `For DAWs` |
| `tab` | `ASCII tab` | `Plain text for editors` |
| `gp5` | `Guitar Pro 5` | `For Guitar Pro` |
| `guitar_stem` | `Guitar stem` | `Isolated guitar audio` |

- [ ] **Step 1: Write the failing test**

```python
def test_download_menu_includes_audience_subtitles(tmp_path: Path):
    pdf = tmp_path / "transcription.pdf"
    midi = tmp_path / "transcription.mid"
    pdf.write_bytes(b"%PDF")
    midi.write_bytes(b"MThd")
    items = download_menu({"pdf": pdf, "midi": midi})
    by_key = {item["key"]: item for item in items}
    assert by_key["pdf"]["subtitle"] == "Printable chart"
    assert by_key["midi"]["subtitle"] == "For DAWs"
    assert by_key["pdf"]["label"] == "PDF"
```

Update `test_downloads_hide_missing_stem_and_unwritten_formats` only if it asserts full item shape — keep key order assertions intact.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_result_studio.py::test_download_menu_includes_audience_subtitles -v`  
Expected: FAIL on missing `subtitle`

- [ ] **Step 3: Extend `DOWNLOAD_SPECS` to 4-tuples `(key, label, mime, subtitle)` and pass `subtitle` through `download_menu`. In the popover, render `st.caption(item["subtitle"])` above each `st.download_button` when subtitle is non-empty; button label stays `item["label"]`.**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_result_studio.py::test_download_menu_includes_audience_subtitles tests/test_result_studio.py::test_downloads_hide_missing_stem_and_unwritten_formats -v`  
Expected: PASS

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 4: Typed failure recovery CTAs

**Files:**
- Modify: `src/audio_to_tab/user_errors.py`
- Modify: `ui/tab_pdf.py` (`record_failure`, error UI ~1455–1479)
- Test: `tests/test_failure_ux_contracts.py`

**Interfaces:**
- Consumes: same exception types as `user_facing_message`
- Produces:
  - `failure_kind(exc: BaseException) -> str` one of: `empty | youtube | ffmpeg | roformer | read | separate | generic`
  - `failure_actions(kind: str) -> tuple[str, ...]` action ids for the UI
  - `record_failure` sets `tab_pdf_failure_kind` (and keeps `tab_pdf_empty_recovery` True iff kind == `empty` for back-compat)

**Kind rules (exact):**

| Condition | kind |
| --- | --- |
| `EmptyTranscriptionError` | `empty` |
| `YouTubeDownloadError` | `youtube` |
| `FFmpegMissingError` | `ffmpeg` |
| `RoFormerTooLongError` | `roformer` |
| `FileNotFoundError` / `OSError` | `read` |
| `"Guitar stem separation failed"` in `str(exc)` | `separate` |
| else | `generic` |

**Action ids (exact):**

| kind | actions |
| --- | --- |
| `empty` | `("solo_preset", "open_expert")` |
| `youtube` | `("use_upload",)` |
| `roformer` | `("use_demucs",)` |
| `separate` | `("retry_without_separation",)` |
| `ffmpeg` / `read` / `generic` | `()` |

**UI button labels (exact):**

| action id | button label | effect |
| --- | --- | --- |
| `solo_preset` | `Use Solo / fingerstyle preset` | existing empty recovery |
| `open_expert` | `Open Expert thresholds` | existing empty recovery |
| `use_upload` | `Switch to Upload` | set source tab to upload; clear error |
| `use_demucs` | `Use Demucs instead` | set engine/model off RoFormer path; clear error; open Advanced |
| `retry_without_separation` | `Retry without stem separation` | set `separate_stems` / solo path flags False; clear error |

- [ ] **Step 1: Write the failing tests**

```python
def test_failure_kind_and_actions_table():
    from audio_to_tab.pipeline import EmptyTranscriptionError
    from audio_to_tab.ingest import YouTubeDownloadError
    from audio_to_tab.user_errors import failure_kind, failure_actions
    assert failure_kind(EmptyTranscriptionError("x")) == "empty"
    assert failure_actions("empty") == ("solo_preset", "open_expert")
    assert failure_kind(YouTubeDownloadError("blocked")) == "youtube"
    assert failure_actions("youtube") == ("use_upload",)
    assert failure_kind(RuntimeError("Guitar stem separation failed: boom")) == "separate"
    assert failure_actions("separate") == ("retry_without_separation",)
    assert failure_actions("generic") == ()

def test_failure_ux_empty_keeps_solo_and_expert_actions():
    source = _tab_pdf_source()
    assert "solo_preset" in source or "tab_empty_solo" in source
    assert "failure_kind" in source or "tab_pdf_failure_kind" in source

def test_failure_ux_youtube_kind_has_upload_action_only():
    from audio_to_tab.user_errors import failure_actions
    assert failure_actions("youtube") == ("use_upload",)
    assert "solo_preset" not in failure_actions("youtube")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_failure_ux_contracts.py::test_failure_kind_and_actions_table tests/test_failure_ux_contracts.py::test_failure_ux_youtube_kind_has_upload_action_only -v`  
Expected: FAIL (`failure_kind` missing)

- [ ] **Step 3: Implement `failure_kind` / `failure_actions`; teach `record_failure` to store `tab_pdf_failure_kind`; render buttons from `failure_actions(kind)` instead of only the empty branch (keep existing Solo/Expert behavior for `empty`). Clear `tab_pdf_failure_kind` wherever errors are cleared today.**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_failure_ux_contracts.py -v`  
Expected: PASS (including existing contract string tests — update string asserts only if a renamed key is required; prefer keeping `tab_pdf_empty_recovery` and `user_facing_message` asserts)

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 5: Verification sweep

**Files:** none new

**Interfaces:** Consumes Tasks 1–4

- [ ] **Step 1: Run the focused suite**

Run:

```bash
pytest \
  tests/test_studio_ui.py::test_format_elapsed_floors_and_clamps \
  tests/test_studio_ui.py::test_progress_tip_for_known_and_unknown_stages \
  tests/test_studio_ui.py::test_progress_card_html_shows_elapsed_and_tip \
  tests/test_studio_ui.py::test_progress_card_html_with_zero_elapsed_and_no_tip \
  tests/test_studio_ui.py::test_progress_card_percent_rises_with_active_fraction \
  tests/test_result_studio.py::test_listen_options_original_and_stem \
  tests/test_result_studio.py::test_listen_options_omit_missing_stem \
  tests/test_result_studio.py::test_player_speed_keeps_quarter_speed \
  tests/test_result_studio.py::test_download_menu_includes_audience_subtitles \
  tests/test_result_studio.py::test_downloads_hide_missing_stem_and_unwritten_formats \
  tests/test_failure_ux_contracts.py \
  -v
```

Expected: all PASS

- [ ] **Step 2: Manual smoke (local app)**

1. Convert a short file with stem separation on → progress shows **Elapsed** ticking and a tip under the bar.  
2. On result, with a guitar stem present → **Listen** radio Original | Guitar stem swaps audio.  
3. Open Download → each item shows a subtitle caption.  
4. Force empty transcription (or use existing empty path) → Solo + Expert still appear.  
5. Speeds / Loop / Metronome still work on the player.

- [ ] **Step 3: Commit** — skip unless user asks

---

## Spec coverage (self-review)

| Phase A item | Task |
| --- | --- |
| 1. Align stages + elapsed + tip | Task 1 (stages already aligned; elapsed + tip added) |
| 2. Practice player speeds / loop / metronome | Already shipped; Task 2 Step 4 + Task 5 regress |
| 3. Original vs guitar-stem listen | Task 2 |
| 4. Export audience subtitles | Task 3 |
| 5. Failure class copy + recovery CTAs | Task 4 |

## Out of scope (Phase B+)

Pre-convert wizard, unified converter card demos, Accurate?/Try Capo N, MusicXML, destination demo scores — see findings §9 Phase B/C.
