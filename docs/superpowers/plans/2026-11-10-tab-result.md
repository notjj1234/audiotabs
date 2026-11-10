# Tab result page implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add chords, a real progress checklist, lyrics-when-possible, and an on-screen result (views, player, one download menu) beside the current Tab PDF pipeline.

**Architecture:** Pure helpers in `src/audio_to_tab/` turn the MIDI this pipeline already writes into wrapped ASCII, chord names, a staff SVG, a piano roll, and a player model. `run_pipeline` calls those helpers and reports the real stage. The Streamlit page renders that model and does not re-transcribe when capo, transpose, tuning, or bars per line change.

**Tech Stack:** Python 3.11, pretty_midi, soundfile, reportlab, Streamlit. No new packages.

**Spec:** Approved session prompt, 2026-11-10. No separate design file.

## Global Constraints

- Python `>=3.10,<3.13`. Do not add a dependency, a CLI flag, or a network host.
- Keep `midi_to_tab` / `tab_to_ascii` as the only tab generator. Reuse `_group_notes_into_events` and `_pick_chord_positions`.
- Local only. No account, pricing, quota, cookie, checkout, or upgrade control.
- Streamlit theme file stays server limits only. No imported palette, font, logo, or brand CSS.
- `.tab` download is the unwrapped document. On-screen text wraps at 100 characters.
- Do not commit. User rule overrides every commit step below.
- Leave `isolate.py`, `roformer.py`, `scnet.py`, `hardware.py`, and CLI output paths alone.

## Review Focus

- A staff wider than 100 characters, including ANSI CSI `m`/`K`, must split on screen and stay one document in the `.tab` file. Test: `test_wrap_splits_wide_staff_and_download_stays_raw`.
- Capo and transpose must move sounding pitch and chord names by the same semitone sum. Test: `test_capo_and_transpose_shift_pitch_and_chord_names`.
- No vocal stem must skip lyrics, say they were not produced, and still write the tab. Test: `test_pipeline_skips_lyrics_without_vocal_and_still_writes_tab`.
- `EmptyTranscriptionError` must write no PDF, MIDI, or tab download and must mention a cleaner solo-guitar clip. Test: `test_empty_transcription_writes_no_downloads`.
- Bars per line 1 versus 8 must change PDF bytes and on-screen staff rows. Test: `test_bars_per_line_changes_pdf_and_staff_rows`.
- Speed 0.25 must survive even though `clamp_playback_rate` floors at 0.5. Test: `test_player_speed_keeps_quarter_speed`.

## Rulings

- Ruling: sounding shift is `transpose + capo` semitones. Capo also raises the tuning MIDI by the same amount, so fret numbers are relative to the capo. Chord names use the shifted pitches. Why: both controls have to change the sounding names, and a capo chart that only renumbers frets would leave the chord name put. Cost if wrong: a capo-2 chart sounds a step higher than the original recording.
- Ruling: tuning options are Standard (EADGBE), Drop D, and Half-step down. Why: a one-value tuning control cannot change output and must not be rendered. Cost if wrong: three tunings instead of a label.
- Ruling: no MusicXML, LilyPond, or GP5. Why: this repo has no writer that can round-trip those bytes. Cost if wrong: the download menu is shorter than the reference apps.
- Ruling: no Synth source button. Why: rendering MIDI audio needs `fluidsynth` / pyfluidsynth, which is not a project dependency, and a new oscillator package was forbidden. Cost if wrong: the player has Original only.
- Ruling: player speeds are the allow-list 0.25, 0.50, 0.75, 1. `clamp_playback_rate` is not applied to 0.25 because its floor is 0.5. Waveform data still comes from `waveform_peaks`. Click times come from `metronome_grid_times`. Cost if wrong: 0.25 would play at 0.5.
- Ruling: consecutive identical chord names collapse into one rail entry. Why: the rail is the progression, not every repeated strum. Cost if wrong: repeated chords show once.
- Ruling: lyrics copy `vocals.wav` out of separation only when that file was produced. No lyrics package is added. Why: the stage runs only when both a vocal stem and an importable Whisper-compatible transcriber exist. Cost if wrong: lyrics stay skipped on this machine.

---

### Task 1: Staff wrap

**Files:**
- Create: `src/audio_to_tab/staff_wrap.py`
- Test: `tests/test_result_studio.py`

**Interfaces:**
- Produces: `strip_ansi_csi(text: str) -> str`, `wrap_tab_staff(text: str, width: int = 100) -> str`

- [ ] **Step 1: Write the failing wrap test**
- [ ] **Step 2: Run `pytest tests/test_result_studio.py::test_wrap_splits_wide_staff_and_download_stays_raw -v` and see it fail**
- [ ] **Step 3: Implement wrap. Six lines that each contain `|` are one staff. Split only when a line is wider than 100. Keep the prefix through the first `|`. Insert `--- Part n/m ---`. Blank line between parts. Strip CSI `m` and `K` only.**
- [ ] **Step 4: Re-run the test and see it pass**
- [ ] **Step 5: Do not commit**

### Task 2: Chords, capo, transpose, tuning

**Files:**
- Create: `src/audio_to_tab/chords.py`
- Modify: `src/audio_to_tab/tuning.py`
- Modify: `src/audio_to_tab/tab_generate.py` (`midi_to_tab` writes `tuning_names`; ASCII header uses those names)
- Test: `tests/test_result_studio.py`

**Interfaces:**
- Consumes: `_group_notes_into_events`, `_pick_chord_positions`, `midi_to_tab`
- Produces: `TUNING_PRESETS`, `tuning_preset(name) -> (midi, names)`, `name_chord(pitches) -> str | None`, `ChordHit`, `chords_from_midi(path, *, transpose, capo, tuning_name) -> list[ChordHit]`, `placed_note(path, *, transpose, capo, tuning_name) -> TabNote`, `detect_key(pitches) -> str`

- [ ] **Step 1: Write failing tests for C then G names, capo 2 and transpose 2 both naming D, sounding pitch `64 + capo + transpose`, and Drop D fret 2 for MIDI 40**
- [ ] **Step 2: Run those tests and see them fail**
- [ ] **Step 3: Implement exact pitch-class templates. Collapse consecutive names. Pass `tuning_names` through `midi_to_tab`.**
- [ ] **Step 4: Re-run and see them pass**
- [ ] **Step 5: Do not commit**

### Task 3: Views, bars per line, downloads, player model

**Files:**
- Create: `src/audio_to_tab/notation_view.py`
- Create: `src/audio_to_tab/player_bar.py`
- Create: `src/audio_to_tab/progress_checklist.py`
- Modify: `src/audio_to_tab/pdf_render.py` (`measures_per_row: int = 4`)
- Test: `tests/test_result_studio.py`

**Interfaces:**
- Produces: `clamp_bars_per_line`, `measure_rows`, `tab_staff_svg`, `piano_roll_svg`, `chord_diagram_svg`, `align_chords_to_lyrics`, `download_menu`, `downloads_after_run`, `format_size_kb`, `show_convert_action`, `PLAYER_SPEEDS`, `player_speed`, `player_click_times`, `player_peaks`, `synth_source_available`, `new_checklist`, `apply_progress`

- [ ] **Step 1: Write failing tests for bars, piano-roll pitch, skipped checklist reason, empty-run downloads, quarter-speed, and synth omitted**
- [ ] **Step 2: Run them and see them fail**
- [ ] **Step 3: Implement the helpers. PDF measure width scales so 1–8 bars fit the page. Diagrams and the roll are SVG from this app.**
- [ ] **Step 4: Re-run and see them pass**
- [ ] **Step 5: Do not commit**

### Task 4: Pipeline stages

**Files:**
- Create: `src/audio_to_tab/lyrics.py`
- Create: `src/audio_to_tab/tab_bundle.py`
- Modify: `src/audio_to_tab/pipeline.py`
- Modify: `src/audio_to_tab/separate.py` (optional `vocal_output: Path | None = None`)
- Test: `tests/test_result_studio.py`

**Interfaces:**
- Produces: `lyrics_skip_reason(path) -> str | None`, `transcribe_lyrics(path) -> list[LyricLine]`, `build_tab_bundle(...) -> dict`, pipeline artifacts `midi`, `tab`, `pdf`, `playback`, optional `guitar_stem`, optional `result`

- [ ] **Step 1: Write failing pipeline tests: lyrics skipped with no vocal stem, checklist stages in order, empty transcription writes nothing and mentions a cleaner solo-guitar clip**
- [ ] **Step 2: Run them and see them fail**
- [ ] **Step 3: Emit progress for ingest, separate (or `skipped: Separation is off`), transcribe, tab, chords, lyrics, pdf, done. Copy `playback.wav`. Copy vocals only when separation wrote `vocals.wav`. Do not call a missing transcriber.**
- [ ] **Step 4: Re-run and see them pass. Then run `make test`.**
- [ ] **Step 5: Do not commit**

### Task 5: Streamlit result page

**Files:**
- Modify: `ui/app.py` (`layout="wide"`)
- Modify: `ui/pages/tab_pdf.py`
- Test: `tests/test_result_studio.py` source assertions plus the pure helpers the page calls

**Interfaces:**
- Consumes: every helper above
- Produces: the page states empty, busy, success, error

- [ ] **Step 1: Assert the page source keeps the experimental warning, the YouTube caption, separation and safer-length controls, and `EmptyTranscriptionError`, and that it clears artifacts on failure**
- [ ] **Step 2: Implement the page. Setup order: title, tuning, capo, then the controls that already exist. File chip is name and size to one decimal, then audio preview. Convert shows only for a file or a valid YouTube URL. Checklist is `apply_progress` on the real callback. Success header is view switch, download popover, then tuning, capo, transpose, key, tempo. Rail on Chords and Tab. Text view is wrapped ASCII. Tab view is the SVG staff. Piano roll is the SVG roll. Bars per line rebuilds staff and PDF. Player is original audio. Details sit in an expander.**
- [ ] **Step 3: Run `make test`**
- [ ] **Step 4: Do not commit**

### Task 6: Verify

- [ ] Run `make test`
- [ ] Run the Streamlit app and exercise file chip, convert, checklist, four views, bars per line, transpose, player loop, each real download, and a bad file with no download. Wide and narrow.
- [ ] Run `graphify update .`
- [ ] One ponytail review of the diff. Fix defects. Do not commit.
