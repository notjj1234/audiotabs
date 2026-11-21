---
name: Studio UI polish plan
overview: Phased, file-scoped plan to auto-fill conversion titles from source, fix screenshot UX defects, label every Advanced control, and make progress advance in small increments during long stages—preserving the existing dark/orange studio look with the smallest correct Streamlit-native diff.
todos: []
isProject: false
---

# Studio UI: naming, Advanced clarity, progressive progress

Using **brainstorming** (approaches locked below), **graphify** (orienting), **writing-plans** (this plan), **impeccable** + **unslop-ui** (Operate-mode clarity polish, keep brand), and **accessibility-game-ui** (visible labels / readable controls).

**UI direction (locked):** Operate surface; quiet chrome; keep `#0f1115` / `#e8a317` studio tokens. No new brand, no purple glow, no expander reintroduction (tests forbid `st.expander`). Prefer Streamlit `label` + `help=` over custom HTML.

**Spec path on execute:** also persist under `docs/superpowers/plans/2026-11-18-studio-ui-naming-advanced-progress.md` when implementation starts (Plan mode forbids writing it now).

---

## 1. Findings (current behavior)

### Naming — default sticks forever
- [`ui/tab_pdf.py`](ui/tab_pdf.py) `_init_setup_state` (~L493) does `setdefault("tab_pdf_title", "Guitar Tab")`.
- Title widget (~L914–919): `st.text_input("Title", value="Guitar Tab", key="tab_pdf_title", …)`.
- YouTube already stores the real title in `tab_youtube_title` via `_select_youtube_hit` (~L150–155) but **never copies** into `tab_pdf_title`.
- Upload keeps filename via [`save_upload`](ui/common.py) / `_safe_upload_name`; media URL basename exists at download time in [`download_direct_media`](src/audio_to_tab/ingest.py) — neither writes the Title field.
- [`_title_stem`](src/audio_to_tab/ingest.py) (~L382) is alnum casefold for **file matching**, not display titles. Do not reuse it for UI names.

### Advanced / screenshot chrome
- Tuning: `st.columns([2, 1, 1])` + full preset key `"Standard (EADGBE)"` from [`TUNING_PRESETS`](src/audio_to_tab/tuning.py) → BaseWeb ellipsis (`Standard (EAD…`).
- Upload “+”: CSS in [`studio_css`](ui/studio_theme.py) (~L264–284) restyles Browse as a plus while the whole dropzone is already clickable; tests lock the plus (`tests/test_studio_ui.py` ~L478).
- Advanced: tiny muted secondary button (~L984–990) + CSS ~L956–973; when open, duplicate uppercase heading via [`advanced_panel_heading_html`](ui/studio_shell.py).
- Unlabeled / no-help Advanced controls: Max duration, Trim start, full-track confirm checkbox, Guitar separation radio, Tempo override, Onset/Frame sliders (inventory in explore).

### Progress
- Checklist: [`new_checklist` / `apply_progress`](src/audio_to_tab/progress_checklist.py) — 7 equal stages; `detail = message` always.
- Percent: [`progress_card_html`](ui/studio_shell.py) `(finished + 0.45 if active) / len(rows)` → separate lands ~**21%** and freezes.
- UI path [`run_pipeline`](src/audio_to_tab/pipeline.py) emits **one** `"Separating stems"` then calls `separate_guitar_stem` with **no** progress hook. `_separate_progress_label` exists but is unused on this path.
- Dup rows: `"Loading audio — Loading audio"` because detail echoes the stage label.

```mermaid
flowchart LR
  source[Upload_YT_URL] --> titleWidget[tab_pdf_title]
  titleWidget -->|"today: stuck Guitar Tab"| convert[Convert]
  convert --> runPipeline[run_pipeline]
  runPipeline -->|"one separate msg"| onProgress[on_progress]
  onProgress --> applyProgress[apply_progress]
  applyProgress --> paint[progress_card_html]
  paint -->|"equal stages + 0.45"| bar["~21% freeze"]
```

---

## 2. Screenshot defect → fix mapping

| Defect | Root cause | Target file(s) | Fix approach |
|---|---|---|---|
| Title stuck on "Guitar Tab" | Never overwrite from source | [`ui/tab_pdf.py`](ui/tab_pdf.py), small helper in [`ui/common.py`](ui/common.py) | Auto-fill only when title empty/`"Guitar Tab"` |
| Truncated Tuning | Narrow col + long preset string | [`ui/tab_pdf.py`](ui/tab_pdf.py) | `format_func` short labels; widen tune column slightly; keep preset keys |
| Upload “+” confusion | Browse restyled as + on full-tile dropzone | [`ui/studio_theme.py`](ui/studio_theme.py), tests | Hide Browse chrome; one upload icon/affordance (match YT/URL quiet chrome) |
| Weak Advanced affordance | Tiny muted text button; no expand cue; dup heading | [`ui/tab_pdf.py`](ui/tab_pdf.py), [`ui/studio_theme.py`](ui/studio_theme.py), [`ui/studio_shell.py`](ui/studio_shell.py) | `"Advanced ▾"` / `"Advanced ▴"`; stronger CSS; drop duplicate heading when open |
| Ambiguous name field | Label "Title" | [`ui/tab_pdf.py`](ui/tab_pdf.py) | Relabel **"Tab title"**; keep existing help |
| `"X — X"` progress rows | detail always set to message == label | [`ui/studio_shell.py`](ui/studio_shell.py) | Omit detail when equal (casefold strip) |
| Giant % jumps / freeze on separate | Equal stage weights; no intra-separate updates | [`progress_checklist.py`](src/audio_to_tab/progress_checklist.py), [`studio_shell.py`](ui/studio_shell.py), [`pipeline.py`](src/audio_to_tab/pipeline.py), [`separate.py`](src/audio_to_tab/separate.py) | Weighted % + real sub-phase fractions + capped Demucs creep |

---

## 3. Recommended approach (locked)

### Naming
Add `suggested_conversion_title(...)` in [`ui/common.py`](ui/common.py) (display-safe stem from filename / YT title / URL path basename; strip extension; light whitespace clean — **not** `_title_stem`).

In [`_render_entry`](ui/tab_pdf.py), **before** the Title widget, and in `_select_youtube_hit`:
- If `tab_pdf_title` is missing or exactly `"Guitar Tab"`, set from active source.
- Never overwrite a user-edited title.
- `_clear_song` continues to reset → default until a new source is chosen.

### Advanced IA / copy
Keep custom show/hide (no expander). Groups inside panel with short captions:
1. **Length** — safer length, max duration, trim, full-track confirm  
2. **Separation** — stem toggle, engine radio, guitar-ft  
3. **Expert** — surgery + transcription thresholds  

Every control gets visible `label` + concise `help=` (what it does + when to change). Prefer checkbox over mixing toggle/checkbox only where a one-line change is natural; do **not** restyle the whole panel.

### Progressive progress
1. **Dedupe detail** in `progress_card_html`.
2. Extend checklist rows with optional `fraction` in `[0,1]` for the active stage (`apply_progress` accepts optional `fraction=None`).
3. **Weighted percent** in `progress_card_html`: heavier weight on `separate` (and slightly on `transcribe`); `ratio = (sum finished weights + active_weight * fraction) / total_weight`. Default active fraction `0.05` at stage entry so bar moves immediately without implying completion.
4. **Real sub-phases** in `separate_guitar_stem`: optional `on_progress: Callable[[str, float], None]` at known boundaries (start model → after primary model → refine/fold/recovery/ensemble/collect as applicable). `run_pipeline` maps these to `progress("separate", label, fraction=…)`, using `_separate_progress_label` / `separate_progress_message` for non-duplicative detail.
5. **Demucs-only capped creep:** while the primary model subprocess/in-process call runs and no finer hook exists, allow a background/thread-or-poll updater (or callback wrapper around the blocking call’s wall time) that advances fraction **only within the demucs sub-band** (e.g. 0.15→0.75 of the separate weight), asymptotically, **never ≥ stage complete until the call returns**, never backwards except cancel/error. Document honesty: this is elapsed-time comfort motion inside a known long phase, not model completion %.

No new dependencies. Do not change separation/transcription quality math.

---

## 4. Phased tasks

### Phase A — Auto-name conversions
**Files:** [`ui/common.py`](ui/common.py), [`ui/tab_pdf.py`](ui/tab_pdf.py) (`_select_youtube_hit`, `_render_entry` before Title widget), tests.

**Acceptance:** Upload stem / YT title / URL-derived name fill `tab_pdf_title` when still default; user edits stick; clear-song restores default until next source.

### Phase B — Screenshot UI defects
**Files:** [`ui/tab_pdf.py`](ui/tab_pdf.py) (columns + Tab title + Advanced button labels), [`ui/studio_theme.py`](ui/studio_theme.py) (upload Browse hide; Advanced toggle CSS), [`ui/studio_shell.py`](ui/studio_shell.py) (stop emitting duplicate Advanced heading from entry, or stop calling it), update locked CSS tests.

**Acceptance:** Tuning readable; one clear upload affordance; Advanced looks like a disclosure control; name field reads as PDF/tab title.

### Phase C — Advanced labels + help
**Files:** [`ui/tab_pdf.py`](ui/tab_pdf.py) Advanced block ~L993–1179 only.

**Acceptance:** Every checkbox/slider/toggle/radio/number_input has label + help; related controls grouped under short captions; copy matches studio tone.

### Phase D — Progressive loading
**Files:** [`progress_checklist.py`](src/audio_to_tab/progress_checklist.py), [`studio_shell.py`](ui/studio_shell.py) `progress_card_html`, [`pipeline.py`](src/audio_to_tab/pipeline.py) `run_pipeline` / `_separate_progress_label`, [`separate.py`](src/audio_to_tab/separate.py) optional progress hook + Demucs creep wrapper, [`ui/tab_pdf.py`](ui/tab_pdf.py) `on_progress` only if signature gains optional fraction.

**Acceptance:** No `"Label — Label"`; during separation bar advances in small steps; percent/bar/active step stay consistent; never claim 100% before pipeline done; no quality behavior change.

### Phase E — Tests + verification
Update/add tests listed below; run focused pytest; manual upload + YouTube checks from Done when.

---

## 5. Test plan

**Unit / UI (extend existing):**
- [`tests/test_studio_ui.py`](tests/test_studio_ui.py): progress card omits dup detail; percent increases when active `fraction` rises; Advanced toggle CSS assertions; upload plus assertions replaced with “no plus / one affordance”; Advanced heading not double-rendered.
- New small tests for `suggested_conversion_title` (upload stem with unicode e.g. `フルスピード・ボーイ.mp3`, YT title, URL basename, does not use alnum-only stem).
- [`tests/test_result_studio.py`](tests/test_result_studio.py): `apply_progress` preserves/sets fraction; unknown stages still ignored.
- Pipeline: when `on_progress` recorded, separate emits ≥2 distinct updates with non-decreasing fractions (mock `separate_guitar_stem`).

**Manual:**
1. Upload `フルスピード・ボーイ.mp3` → Tab title auto-fills from stem; edit sticks.
2. Pick YouTube hit → title becomes video title.
3. Paste media URL → best available basename/title fills.
4. Open Advanced → every control labeled + help; Tuning fully readable.
5. Convert with stem separation on → bar creeps during long stage; checklist rows clean.

---

## 6. Done when (binary)

- [ ] Upload file auto-fills name from stem
- [ ] YouTube selection auto-fills from video title
- [ ] Media URL auto-fills from best available title/filename
- [ ] Advanced: every control labeled + explained; no blank checkbox/slider/toggle
- [ ] Tuning dropdown text readable (not truncated into uselessness)
- [ ] Progress moves in small increments during long stages; no giant jumps as the normal path
- [ ] Progress rows do not show duplicated `"X — X"` labels
- [ ] Existing convert pipeline behavior otherwise unchanged

---

## 7. Out of scope

- Packaging/launcher, model weights, Demucs/RoFormer quality math
- Moving stem-sep toggle out of Advanced into the main row
- Reintroducing `st.expander`
- New dependencies / design system / light theme / purple accents
- Isolate-path checklist stage IDs (`guitar_refine`, etc.) as new rows
- Claiming true Demucs completion percentage from fake creep
- DB/schema, deleting files, unrelated pipeline/transcription threshold defaults

---

## 8. Open questions

None blocking. Locked defaults above (default-only title overwrite; short tuning display labels; real sub-phases + capped Demucs creep; Advanced stays custom toggle with stronger affordance).
