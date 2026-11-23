# Tab rhythm visibility — implementation plan

> Spec: `docs/superpowers/specs/2026-11-22-tab-rhythm-visibility-design.md`

**Goal:** Dark-theme tab ink + Songsterr-style stems/beams/flags on the Result Tab view.

## Tasks

1. `src/audio_to_tab/tab_rhythm.py` — duration snap + beam groups
2. `notation_view.py` — dark defaults + rhythm glyphs; piano/chord ink
3. `Result.svelte` — deepen `.score` with `--art` mix
4. Tests: `tests/test_tab_rhythm.py`, `tests/test_web_tokens.py`
