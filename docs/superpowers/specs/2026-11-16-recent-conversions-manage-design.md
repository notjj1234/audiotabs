# Recent conversions: show more + hard delete

**Date:** 2026-11-16  
**Size:** Small change  
**Status:** Approved

## Intent

Keep Recent Conversions glanceable (3 rows up front), let people open the rest via Show more, and let them permanently remove one, several, or all saved runs — with a confirmation before anything is wiped.

## Goals

- Show at most 3 runs initially; reveal the rest with Show more when count > 3.
- Per-row delete, multi-select delete, and Clear all.
- Every delete path hard-deletes the run folder on disk (artifacts + `meta.json`).
- Every delete path requires an explicit second confirmation.

## Non-goals

- Soft delete / trash / undo.
- Cloud sync or account-level history.
- Changing how Reopen works (except disappearing after delete).
- Renaming or editing run titles.

## Anti-goals

- Deleting without confirmation.
- Leaving orphaned files after removing a list entry.
- Expanding the card into a full history browser.

## Constraints

- Streamlit UI in `ui/tab_pdf.py`; storage helpers in `ui/common.py` (`list_recent_runs`, `data/ui_runs/<uuid>/`).
- Match existing studio styling (`.st-key-tab_recent`).
- Existing tests assert `list_recent_runs(..., limit=5)` — update those with the new behavior.

## Approaches considered

| | Approach | Tradeoff |
|---|---|---|
| A | Checkboxes + Delete selected only | No one-click clear-all |
| B | Clear all only | No selective prune |
| **C (chosen)** | Per-row + selected + Clear all | Slightly denser card; covers all tidy-up cases |

Chosen because the user wants bulk options and single deletes; C is the flexible set without a separate history screen.

## Design

### List / Show more

- Fetch a sensible cap of recent `tab_pdf` runs (e.g. 20) so Show more has something to reveal.
- Default visible count: **3**.
- If total > 3 and collapsed: show a **Show more** control under the list that expands to the full fetched set.
- When expanded: **Show less** collapses back to 3.
- Empty list: hide the whole Recent Conversions panel (same as today).

### Row layout

`[checkbox] title · timestamp · [Delete] [Reopen]`

- Checkbox participates in multi-select.
- Delete is available even when Reopen is disabled (unavailable PDF) so users can clean dead entries.
- Reopen behavior unchanged when the PDF still exists.

### Delete semantics

- Hard delete: remove the entire `run_dir` under the data dir (same folder `list_recent_runs` reads).
- If the deleted run is the one currently open in session (`tab_pdf_artifacts` pointing at that dir), clear that session result state so the UI does not point at missing files.
- Add `delete_run(run_dir)` (and optionally `delete_runs(run_dirs)`) in `ui/common.py`; UI never `rmtree`s ad hoc.

### Confirmations

- Single: confirm dialog/copy like “Permanently delete **{title}** and its files? This cannot be undone.” → Cancel / Delete.
- Selected: “Permanently delete **N** conversions and their files? …”
- Clear all: “Permanently delete all **N** recent conversions and their files? …”
- Confirmation is a second step in the card (Streamlit has no native modal): clicking Delete / Delete selected / Clear all enters a confirm state; Cancel aborts; confirming runs the wipe then refreshes the list.
- Only one pending confirm at a time.

### Bulk chrome

- When any checkbox is selected: show **Delete selected (N)**.
- When the list is non-empty: show **Clear all** (header or footer of the card).
- Selecting none hides Delete selected.

### Builder calls (settled here)

- Visible default = 3; fetch limit = 20.
- Confirm UX = inline second step in the card (not a browser `confirm()`).
- Show more expands in place to the full fetched list (not paginate by 3).

## Out of builder scope unless needed

- CSS tweaks only as required to keep row alignment with the new checkbox + Delete control.
