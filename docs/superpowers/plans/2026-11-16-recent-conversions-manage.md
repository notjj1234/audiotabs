# Recent Conversions Manage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show 3 recent conversions with Show more, and hard-delete one/selected/all with confirmation.

**Architecture:** Add hard-delete helpers in `ui/common.py`; extend the Recent Conversions card in `ui/tab_pdf.py` with checkbox rows, confirm state, and show-more; light CSS for new controls.

**Tech Stack:** Python, Streamlit, pytest, existing `data/ui_runs` + `meta.json` storage.

**Spec:** `docs/superpowers/specs/2026-11-16-recent-conversions-manage-design.md`

## Global Constraints

- Visible default: 3; fetch limit: 20.
- Hard delete only (entire `run_dir`); no soft delete/undo.
- Every delete path needs an inline second confirmation (Cancel / Delete).
- Match `.st-key-tab_recent` studio styling.

## Review Focus

- Delete while that run is open in session → clear result session state.
- Delete unavailable (missing PDF) runs → still removable.
- Confirm cancel → no files removed.
- After delete, checkboxes/confirm state reset; list refreshes.
- Show less after expand → back to 3 rows.

---

### Task 1: Hard-delete helpers

**Files:**
- Modify: `ui/common.py`
- Test: `tests/test_common_recent_runs.py` (create if missing) or extend existing common tests

**Interfaces:**
- Produces: `delete_run(run_dir: str | Path) -> bool`, `delete_runs(run_dirs: list[str | Path]) -> int`
- Consumes: `DATA_DIR`, existing run layout from `list_recent_runs` / `write_run_metadata`

- [x] **Step 1: Write failing tests** for deleting one run dir and deleting several; refuse paths outside `DATA_DIR`; missing dir returns False / skips.

- [x] **Step 2: Run tests — expect fail** (helpers missing)

- [x] **Step 3: Implement `delete_run` / `delete_runs`** — resolve path, ensure it is under `DATA_DIR`, `shutil.rmtree` the run folder.

- [x] **Step 4: Run tests — expect pass**

---

### Task 2: Recent list UI — show more + delete chrome

**Files:**
- Modify: `ui/tab_pdf.py` (recent block ~1139–1164)
- Modify: `ui/studio_theme.py` (`.st-key-tab_recent` styles as needed)
- Modify: `tests/test_studio_ui.py` (assertions for limit=5 → new wiring)

**Interfaces:**
- Consumes: `list_recent_runs("tab_pdf", limit=20)`, `delete_run`, `delete_runs`
- Session keys: `tab_recent_expanded`, `tab_recent_confirm` (kind + targets), checkbox keys per run

- [x] **Step 1: Update/add tests** asserting fetch limit 20, show-more wiring, delete/clear helpers referenced; keep no-expander rule.

- [x] **Step 2: Run — expect fail** where old `limit=5` assertion breaks / new asserts missing.

- [x] **Step 3: Implement UI**
  - Slice visible runs to 3 unless expanded.
  - Row: checkbox, title, when, Delete, Reopen.
  - Footer: Show more/less; Delete selected when any checked; Clear all when list non-empty.
  - Confirm panel replaces actions until Cancel or confirmed Delete.
  - On successful delete of open run artifacts, clear session result keys (same set Reopen sets / failure clears).

- [x] **Step 4: Run targeted pytest — expect pass**

---

### Task 3: Verify

- [x] **Step 1:** `pytest tests/test_studio_ui.py tests/test_common_recent_runs.py -q` (or equivalent paths) green
- [x] **Step 2:** `graphify update .`
