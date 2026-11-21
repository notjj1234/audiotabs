# Phase C: Depth & Differentiation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a successful conversion, surface feature depth (go-deeper banner), a cheap Accurate? signal + Try Capo N hint, clearer engine education tooltips, and a MusicXML “Soon” stub — without adding mic input, wait surveys, or a real MusicXML writer.

**Architecture:** Pure helpers for depth-banner actions, capo suggestion, and accuracy feedback state. Thin Streamlit wiring in `_render_success` + Advanced `help=` copy. Reuse existing bars-per-line, piano-roll view, and GP5 download (already shipped). No new dependencies.

**Tech Stack:** Python 3.11, Streamlit, existing `chords.detect_key` / `PC_NAMES`, `studio_shell` / `studio_theme`, `tab_bundle.download_menu`.

**Spec:** `docs/superpowers/plans/2026-11-18-competitor-ui-workflow-findings.md` §9 Phase C (items 10–15), scoped.

## Global Constraints

- Python `>=3.10,<3.13`. No new packages, accounts, paywalls, or network downloads for education copy.
- Do **not** implement mic input or wait-time survey (Phase C items 15 — deferred).
- Do **not** implement a real MusicXML exporter — download menu may show a disabled “Soon” row only.
- Do **not** build a Note Editor / MuseScore-class engraving (explicit non-goal).
- Bars-per-line (1–8) and Piano roll score view already exist — do not rebuild; banner may deep-link into them.
- Feedback is local session only (no analytics backend).
- Do not commit unless the user explicitly asks. Skip every Commit step.
- Prefer smallest Streamlit-native diff; stay on `phase-a-result-wait-polish` (current feature branch).

## Review Focus

- Depth banner omits actions whose targets are unavailable (no GP5 → no Export Guitar Pro CTA; no midi → no piano-roll CTA). Test: `test_depth_banner_actions_omit_unavailable`.
- Capo suggestion returns `None` for friendly keys and `Unknown`. Test: `test_suggest_capo_skips_friendly_and_unknown`.
- Capo suggestion returns lowest fret 1–7 that yields a friendly written key. Test: `test_suggest_capo_finds_lowest_friendly`.
- Accurate? Yes/No persists in session under stable keys; second click same value is idempotent. Test: `test_accuracy_feedback_roundtrip`.
- MusicXML Soon stub never appears as a real `st.download_button` path. Test: `test_download_menu_excludes_musicxml_soon` (or contract that Soon is UI-only).
- Education help strings mention Basic Pitch, Demucs, and Guitar-FT by name in Advanced. Test: `test_tab_pdf_education_tooltips`.

## File map

| File | Responsibility |
| --- | --- |
| `src/audio_to_tab/depth_banner.py` | Banner action list from artifacts / run details |
| `src/audio_to_tab/capo_suggest.py` | `suggest_capo_for_key(key_name, *, current_capo=0) -> int \| None` |
| `src/audio_to_tab/accuracy_feedback.py` | Session get/set helpers for Yes/No |
| `ui/studio_shell.py` | Optional `depth_banner_html(...)` |
| `ui/studio_theme.py` | `.studio-depth-banner` styles |
| `ui/tab_pdf.py` | Wire banner, Accurate?, Try Capo, education `help=`, MusicXML Soon caption |
| `tests/test_depth_banner.py` | Banner actions |
| `tests/test_capo_suggest.py` | Capo helper |
| `tests/test_accuracy_feedback.py` | Feedback helpers |
| `tests/test_studio_ui.py` / `tests/test_result_studio.py` | Wiring contracts |

## Already shipped (extend, don’t rebuild)

- Result Tuning / Capo / Transpose / Bars per line
- Score views Staff | Chords | Text | Piano roll
- GP5 in `DOWNLOAD_SPECS` + download popover with audience subtitles
- Staff row playhead markers; on-screen wrap vs raw `.tab` export
- Demucs / guitar-ft Advanced toggles (improve `help=` only)

## Deferred (out of this plan)

- Optional mic input; wait tips/survey for long runs (item 15)
- Real MusicXML / Dorico pipeline (item 14 beyond Soon stub)
- Verse/Chorus structural part labels (no section detector in engine)

---

### Task 1: Capo suggestion helper

**Files:**
- Create: `src/audio_to_tab/capo_suggest.py`
- Test: `tests/test_capo_suggest.py`

**Interfaces:**
- Produces:
  - `FRIENDLY_KEYS: frozenset[str]` — at least `C major`, `G major`, `D major`, `A major`, `E major`, `A minor`, `E minor`, `D minor`
  - `suggest_capo_for_key(key_name: str, *, current_capo: int = 0) -> int | None`
    - Parse `"Root quality"` using `PC_NAMES` roots (sharps). Unknown / unparseable → `None`.
    - If `key_name` already in `FRIENDLY_KEYS` → `None`.
    - Else lowest `n` in `1..7` such that written key `(root - n) % 12` + same quality is friendly **and** `n != current_capo`; else `None`.

- [ ] **Step 1: Write failing tests** (`test_suggest_capo_skips_friendly_and_unknown`, `test_suggest_capo_finds_lowest_friendly`)
- [ ] **Step 2: RED** — `pytest tests/test_capo_suggest.py -v`
- [ ] **Step 3: Implement helper**
- [ ] **Step 4: GREEN**
- [ ] **Step 5: Commit** — skip

---

### Task 2: Accuracy feedback helper

**Files:**
- Create: `src/audio_to_tab/accuracy_feedback.py`
- Test: `tests/test_accuracy_feedback.py`

**Interfaces:**
- Produces:
  - `ACCURACY_KEY = "tab_accuracy_feedback"`  # maps run_id → `"yes" | "no"`
  - `get_accuracy_feedback(state: dict, run_id: str) -> str | None`
  - `set_accuracy_feedback(state: dict, run_id: str, value: str) -> None` — only `"yes"` / `"no"`; others raise `ValueError`

- [ ] **Step 1: Failing tests for roundtrip + reject bad value**
- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**
- [ ] **Step 4: GREEN**
- [ ] **Step 5: Commit** — skip

---

### Task 3: Depth banner actions + HTML/CSS

**Files:**
- Create: `src/audio_to_tab/depth_banner.py`
- Modify: `ui/studio_shell.py` (`depth_banner_html`)
- Modify: `ui/studio_theme.py` (`.studio-depth-banner`)
- Test: `tests/test_depth_banner.py`

**Interfaces:**
- Produces:
  - `depth_banner_actions(*, artifacts: dict | None, details: dict | None, has_midi: bool) -> list[dict]`
    - Each item: `{"id": str, "label": str}`
    - Include `piano_roll` when `has_midi`
    - Include `guitar_pro` when `artifacts` has readable `gp5` path
    - Include `try_separation` when `details.get("separate")` is falsy
    - Order: piano_roll, try_separation, guitar_pro (omit missing)
  - `depth_banner_html(actions: list[dict]) -> str` — heading “Go deeper” + short line; empty actions → `""`

- [ ] **Step 1: Failing tests for omit-unavailable + empty → empty html**
- [ ] **Step 2: RED**
- [ ] **Step 3: Implement helpers + CSS + `depth_banner_html`**
- [ ] **Step 4: GREEN**
- [ ] **Step 5: Commit** — skip

---

### Task 4: Wire result shell (banner, Accurate?, Try Capo, education, MusicXML Soon)

**Files:**
- Modify: `ui/tab_pdf.py` (`_render_success` + Advanced help strings)
- Test: extend `tests/test_studio_ui.py` / new contract tests

**Behavior:**
- After result header (before Playback): render depth banner HTML; Streamlit buttons for each action id:
  - `piano_roll` → `st.session_state["tab_pdf_view"] = "Piano roll"`
  - `try_separation` → set `tab_transcription_preset` / separate flag for next convert + `st.info` copy (do not auto-rerun pipeline)
  - `guitar_pro` → `st.info("Guitar Pro 5 is in the Downloads menu.")`
- Accurate? Yes / No buttons near header; keyed by current run id (`tab_pdf_run_dir` or artifacts parent); show caption of last choice
- If `suggest_capo_for_key(song_key, current_capo=capo)` returns `n`: button **Try Capo {n}** sets `tab_result_capo = n`
- Advanced: ensure `help=` (or captions) explicitly name **Basic Pitch** (onset/frame or transcription), **Demucs**, and **Guitar-FT**
- Downloads popover: after real items, `st.caption("MusicXML — Soon (for MuseScore / Dorico)")` — never a download button

- [ ] **Step 1: Failing wiring contracts** (`depth_banner`, `suggest_capo`, `accuracy_feedback`, `MusicXML`, Basic Pitch/Demucs/Guitar-FT strings in `tab_pdf.py`)
- [ ] **Step 2: RED**
- [ ] **Step 3: Implement wiring**
- [ ] **Step 4: GREEN**
- [ ] **Step 5: Commit** — skip

---

### Task 5: Verification sweep

- [ ] **Step 1: Run**

```bash
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 pytest \
  tests/test_capo_suggest.py \
  tests/test_accuracy_feedback.py \
  tests/test_depth_banner.py \
  tests/test_studio_ui.py -k "depth or capo or accuracy or education or musicxml or MusicXML" \
  -v
```

- [ ] **Step 2: Manual** — open Try sample tab; see Go deeper, Accurate?, optional Try Capo; Downloads shows MusicXML Soon
- [ ] **Step 3: Commit** — skip

---

## Spec coverage

| Phase C item | Task / note |
| --- | --- |
| 10. Go deeper banner | Tasks 3–4 |
| 11. Accurate? + Try Capo N | Tasks 1–2, 4 |
| 12. Bars-per-line / part markers | Already shipped — no new work |
| 13. Education tooltips | Task 4 |
| 14. MusicXML / GP | GP shipped; MusicXML Soon stub in Task 4 |
| 15. Mic / wait survey | Deferred |
