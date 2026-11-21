# Phase B: Intake & Intent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make first-run intake feel like one converter card with a clear selected-source chip, a short Quick setup (including Use defaults + fingering), and a one-click sample tab that proves the destination without running the full pipeline.

**Architecture:** Pure helpers for source chips and demo materialization; Streamlit entry wiring only. No multi-page wizard modal. Reuse `_reopen_run` / result shell for the demo. Map “style” to existing `fingering_preference` (`playable` | `low_fret` | `position`).

**Tech Stack:** Python 3.11, Streamlit, pretty_midi, existing `tab_bundle` / `pipeline` / `common`.

**Spec:** `docs/superpowers/plans/2026-11-18-competitor-ui-workflow-findings.md` §9 Phase B (items 6–9).

## Global Constraints

- Python `>=3.10,<3.13`. No new dependencies, accounts, or paywalls.
- Keep Upload / YouTube / Media URL as one segmented control — do not add mic/OMR.
- Do not replace Advanced; Quick setup is the visible intent layer; Advanced stays for power users.
- Demo must not download the network; all demo bytes are local.
- Do not commit unless the user explicitly asks.
- Prefer smallest Streamlit-native diff; stay on branch `phase-a-result-wait-polish` (or current feature branch).

## Review Focus

- Empty Upload/YouTube/URL tabs must not invent a chip. Test: `test_source_chip_requires_name`.
- Upload chip shows size when bytes known; duration caption when probed. Test: `test_source_chip_formats_size_and_duration`.
- Use defaults resets preset=`solo`, tuning=`Standard (EADGBE)`, capo=`0`, fingering=`playable`. Test: `test_quick_setup_defaults_values`.
- Demo materialize writes `meta.json` + usable `midi`/`result` under a run dir and is idempotent. Test: `test_ensure_demo_run_idempotent`.
- Convert pending includes `fingering_preference` from Quick setup. Test: source contract or unit on pending builder if extracted; else `test_tab_pdf_wires_fingering_preference`.

## File map

| File | Responsibility |
| --- | --- |
| `src/audio_to_tab/source_chip.py` | Chip model + caption formatting |
| `src/audio_to_tab/demo_pack.py` | Build/copy sample run artifacts |
| `ui/studio_theme.py` | `.studio-converter-card` styles |
| `ui/tab_pdf.py` | Entry card, chip UI, Quick setup, Try sample, fingering → pending |
| `ui/common.py` | Optional: demo path helper only if needed |
| `tests/test_source_chip.py` | Chip helpers |
| `tests/test_demo_pack.py` | Demo materialize |
| `tests/test_result_studio.py` / `tests/test_studio_ui.py` | Wiring contracts |

## Already shipped (extend, don’t rebuild)

- Segmented Upload / YouTube / URL (`tab_source_tab`)
- YouTube selection chip (title + duration + Change/Remove)
- Upload `st.audio` + duration caption
- Transcription preset Solo / Full mix + tuning/capo before Convert
- Recent reopen path

---

### Task 1: Source chip helper

**Files:**
- Create: `src/audio_to_tab/source_chip.py`
- Test: `tests/test_source_chip.py`

**Interfaces:**
- Produces:
  - `source_chip(*, name: str, size_bytes: int | None = None, duration_sec: float | None = None) -> dict`
  - `format_source_chip_caption(chip: dict) -> str` — joins size (`format_size_kb`) and `Duration about M:SS` when present; empty string if neither

- [ ] **Step 1: Write failing tests**

```python
def test_source_chip_requires_name():
    from audio_to_tab.source_chip import source_chip
    import pytest
    with pytest.raises(ValueError):
        source_chip(name="  ")

def test_source_chip_formats_size_and_duration():
    from audio_to_tab.source_chip import source_chip, format_source_chip_caption
    chip = source_chip(name="riff.mp3", size_bytes=1536, duration_sec=65)
    assert chip["name"] == "riff.mp3"
    caption = format_source_chip_caption(chip)
    assert "1.5 KB" in caption
    assert "1:05" in caption
```

- [ ] **Step 2: Run RED** — `pytest tests/test_source_chip.py -v`
- [ ] **Step 3: Implement helpers** (reuse `format_size_kb` from `tab_bundle`; duration via same M:SS floor as `_clock`)
- [ ] **Step 4: Run GREEN**
- [ ] **Step 5: Commit** — skip unless asked

---

### Task 2: Unified converter card + upload chip

**Files:**
- Modify: `ui/studio_theme.py` (`.studio-converter-card`)
- Modify: `ui/tab_pdf.py` (`_render_entry` source block)
- Test: `tests/test_studio_ui.py` (CSS/contract) + extend result studio if needed

**Interfaces:**
- Consumes: `source_chip`, `format_source_chip_caption`
- Behavior:
  - Wrap `tab_source_entry` contents visually with converter-card CSS (class on a markdown wrapper or container styling already keyed).
  - When upload selected and file present: show **name** + caption (size from `uploaded.size` if available, duration when probed) above/beside existing `st.audio`.
  - Keep YouTube chip; ensure Media URL with a non-empty paste shows a name chip (basename or host path).

- [ ] **Step 1: Write failing contract test** that `tab_pdf.py` contains `source_chip` / `format_source_chip_caption` and `studio-converter-card` appears in theme CSS
- [ ] **Step 2: RED**
- [ ] **Step 3: Implement CSS + upload/URL chip wiring**
- [ ] **Step 4: GREEN**
- [ ] **Step 5: Commit** — skip

---

### Task 3: Quick setup — Use defaults + fingering

**Files:**
- Modify: `ui/tab_pdf.py` (setup block + `_execute_pending` `PipelineConfig`)
- Test: `tests/test_result_studio.py` or new `tests/test_quick_setup.py`

**Interfaces:**
- Produces session defaults helper:

```python
def apply_quick_setup_defaults(state: dict) -> None:
    # preset solo, Standard tuning, capo 0, fingering playable, safer_length True
```

Place in `ui/tab_pdf.py` or `src/audio_to_tab/quick_setup.py` — prefer `src/audio_to_tab/quick_setup.py` for testability.

- Locked UI:
  - Section label **Quick setup**
  - Existing preset / tuning / capo stay
  - New radio **Fingering**: `playable` → “Balanced”, `low_fret` → “Low frets”, `position` → “Stay in position” (`key="tab_setup_fingering"`)
  - Button **Use defaults** (`key="tab_quick_setup_defaults"`)
  - Pending + `PipelineConfig(..., fingering_preference=...)`

- [ ] **Step 1: Failing tests for `apply_quick_setup_defaults` + wiring contract `tab_setup_fingering` / `fingering_preference`**
- [ ] **Step 2: RED**
- [ ] **Step 3: Implement helper + UI + pending/config wiring**
- [ ] **Step 4: GREEN**
- [ ] **Step 5: Commit** — skip

---

### Task 4: Bundled sample tab (destination proof)

**Files:**
- Create: `src/audio_to_tab/demo_pack.py`
- Modify: `ui/tab_pdf.py` (entry: **Try sample tab** when no source chosen / always visible secondary)
- Test: `tests/test_demo_pack.py`

**Interfaces:**
- Produces:
  - `DEMO_TITLE = "Sample tab"`
  - `ensure_demo_run(data_dir: Path) -> dict` — creates `data_dir / "demo-sample-tab"` with `meta.json`, tiny MIDI, `result.json`, ASCII `.tab`, minimal PDF; returns meta including `run_dir` + `artifacts` absolute paths; second call leaves files, returns same shape
- UI: button **Try sample tab** (`key="tab_try_sample"`) calls `ensure_demo_run(DATA_DIR)` then `_reopen_run(meta)`

**Ruling:** Demo MIDI is 2–4 notes at 120 BPM C major (synthetic). No copyrighted audio. PDF via existing `write_tab_exports` / `render_structured_tab_pdf` path.

- [ ] **Step 1: Failing tests for ensure_demo_run idempotent + midi/result/pdf/tab exist**
- [ ] **Step 2: RED**
- [ ] **Step 3: Implement demo_pack + entry button**
- [ ] **Step 4: GREEN**
- [ ] **Step 5: Commit** — skip

---

### Task 5: Verification sweep

- [ ] **Step 1: Run**

```bash
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 pytest \
  tests/test_source_chip.py \
  tests/test_demo_pack.py \
  tests/test_quick_setup.py \
  tests/test_studio_ui.py -k "converter or source_chip or fingering or sample" \
  tests/test_result_studio.py -k "fingering or source_chip or chip" \
  -v
```

(Adjust node ids to match tests actually added.)

- [ ] **Step 2: Manual** — entry shows card; upload chip; Use defaults; Try sample opens result shell
- [ ] **Step 3: Commit** — skip

---

## Spec coverage

| Phase B item | Task |
| --- | --- |
| 6. Unified converter card | Task 2 |
| 7. File chip + preview + duration/size | Tasks 1–2 |
| 8. Short wizard + Use defaults | Task 3 |
| 9. Bundled demo | Task 4 |
