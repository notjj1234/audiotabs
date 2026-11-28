# Lead/Rhythm guitar split

The `lead_rhythm_split` mode (Streamlit: "Lead + Rhythm" engine; `IsolateConfig(model="lead_rhythm_split")`) is the pipeline's first genuine *lead vs rhythm* separator. It runs: guitar isolation pre-pass → Mel-Band RoFormer Lead/Rhythm split → per-stem transcription → per-stem tab + exports (`.tab`, `.pdf`, `.gp5`, per-stem MIDI, two-track `stems.mid`, MusicXML 4.0).

## Why the guitar pre-pass runs first

The split model (`mbr_lead_rhythm_guitar_listra92`) was trained on isolated-guitar material: it expects one guitar performance and splits it into "the lead line" vs "everything else that guitar plays". Fed a full mix, it instead splits "most prominent guitar" vs "the rest of the mix", which is not what the tabs need. The pre-pass gives it a single clean guitar stem. Since 2026-11-26 that stem comes from BS-RoFormer SW when it can run (GPU + `[roformer]` extra), with the guitar-ft fine-tune of htdemucs_6s (`adityalakhani/htdemucs-6s-guitar-ft`, integrated in `separate.py`) as the fallback. On band mixes this raised guitar SI-SDR from 8.96 to 14.55 dB and rhythm F1 from 0.483 to 0.575 ([guitar separation eval](guitar-separation-eval.md)). The pre-pass is on by default in this mode; turn off "Separate guitar stem" (pipeline: `separate_stems=False`) when the input file is already an isolated guitar stem — it is skipped then. Pre-pass quality uses the existing fast/balanced/high/extreme shifts/overlap map.

## Why this model is the only lead/rhythm splitter

- `htdemucs_6s` has one combined guitar stem — structurally incapable of lead/rhythm (Demucs is never the lead/rhythm splitter here).
- `mbr_lead_rhythm_guitar_listra92` is, as of integration (2026-11), the only Mel-Band RoFormer checkpoint in the integrated set trained for exactly the two stems `[Lead, Rhythm]` (`training.instruments`, `target_instrument: Lead`, 44.1 kHz, single-target + residual). No second lead/rhythm model is integrated, and there is no "auto" choice between them.
- The older `lead_rhythm.py` (`IsolateConfig.lead_rhythm` / `dual_guitar`) remains a post-hoc heuristic classifier on one guitar stem — a fallback for when the RoFormer runtime (`pip install -e ".[roformer]"`, bs-roformer-infer) is not installed, not a separator.

Checkpoint facts: 337,073,664 bytes, SHA256 `b3c47bca33609ca1ba0bb2d2076410bfd1eb941b051b72afc1f3e24d12b17eef`, cached under `separator_cache_dir()`, pinned via urllib (no huggingface_hub). Hosted on the community mirror `noblebarkrr/mvsepless_resources` — **no license is stated; treat as all-rights-reserved** (same posture as BS-RoFormer-SW).

Provenance (checked 2026-11-25): the mirror file is byte-identical (same size and LFS SHA256) to `listra92/MyModels/misc/model_mel_band_roformer_ep_72_sdr_3.2232.ckpt` with config `misc/config_mel_band_roformer_Lead_Rhythm_Guitar.yaml` (https://huggingface.co/listra92/MyModels/tree/main/misc). The only quality figure is the SDR 3.22 in the file name (validation set unknown; general guitar-vs-rest models score 7–9). Training data is not documented. That repo's card says `license: openrail++` for the whole repo, which mostly holds Stable Diffusion files; whether it covers this checkpoint is unverified, so the all-rights-reserved posture stays. The original config uses `num_overlap: 1`; the mirror's uses 2 (measured below: overlap does not change the roles). The only other downloadable lead/rhythm separator found, `demucs4_lead_rhythm_guitar_drypaint` on the same mirror, publishes no metrics and no license. The `audio-separator` UVR stack cannot load it (registry-only model loader; also blocked by its NumPy 2 requirement), so inference uses the in-process bs-roformer runtime that `run_melband_guitar` already prefers.

Inside the mode, any failure is loud (`Lead/rhythm split failed: …`) — nothing silently falls back to a combined guitar stem. Outside the mode, behavior is unchanged.

## Bar-level role check (after transcription)

The splitter decides roles from sound; lead and rhythm are *functional* roles (Régnier, Martin & Bigo, ISMIR 2021), and in an isolated stem only textural cues survive. `guitar_roles.assign_roles` re-checks every bar of the two transcribed stems before tabs are built:

- **Chords lean rhythm:** the monophonic lead path keeps one note per attack, but it also records whole chord attacks (≥ 3 distinct pitches; two-note double-stops stay lead; an attack made only of one note's harmonics — octave, octave + fifth, two octaves… — is that single note, while root + fifth + octave stays a power chord). Each such chord goes to rhythm, all notes, when the rhythm stem has no attack within 60 ms, and the leftover lead note is removed; when rhythm is already playing there it is treated as rhythm heard in the lead stem and left alone. Counts are in `lead_rhythm_roles.json` (`chords_to_rhythm`, `chords_left_in_lead`).
- **Bleed:** a rhythm note that repeats a lead note (same pitch, onset within 60 ms) on its own is the lead heard in the residual and is dropped; a copy inside a rhythm chord stays.
- **Solo/fill filed as rhythm:** a rhythm bar that is a single-note line (≤ 1.25 notes per onset, ≥ 4 onsets), moves stepwise (≥ 60% steps of ≤ 4 semitones), does not repeat elsewhere (Jaccard < 0.6 on onset/pitch-class) and has no lead playing moves to lead.
- **Riff filed as lead:** a lead bar that spells out one triad (≥ 80% of sounding time), repeats, and has no rhythm playing moves to rhythm. Repeating single-note riffs stay rhythm.
- Roles switch inside songs, so decisions are per bar; a move needs a neighbouring bar that agrees or ≥ 6 onsets. Ambiguous bars never move.

Bars come from the detected beat grid phased to the downbeats (as in the viewer). Every bar's textures and every move with its reason are written to `lead_rhythm_roles.json`; a summary line goes into the warnings in `lead_rhythm_notes.json`. Bends/vibrato, panning, tone and foreground salience are not used: they are unreliable or not recoverable from a stem.

## Runtime (2026-11-25)

The model code is bundled in `src/audio_to_tab/vendor/mel_band_roformer/` (copied from
ZFTurbo/Music-Source-Separation-Training, MIT). The pip packages `bs-roformer-infer` (no
MelBand module) and `melband-roformer-infer` (hard-codes `mlp_expansion_factor=4`; this
checkpoint uses 2) cannot load it. The checkpoint is loaded with `strict=True`, so a layout
mismatch fails loudly. Measured: 30 s of guitar splits in about 17 s on Apple MPS.

## In the instrument picker (2026-11-25)

With the picker flow the split runs **once, during the analysis phase**, on the guitar stem
from the single 6-stem separation (with the vocal copy removed, see "Accuracy work"), and its
stems are cached for the tab job (which never re-splits). The picker shows what actually happened:

- **Split succeeded:** *Lead guitar* and *Rhythm guitar* rows, both checked; *Combined guitar*
  is locked while Lead or Rhythm is checked.
- **Split failed, unavailable or refused (audio too long):** *Lead* and *Rhythm* are greyed out
  and *Combined guitar* is checked, with the reason from `lead_rhythm_fallback.json`.
- **The web app always requests the split.** Only a direct API call with another engine gets
  "Lead and Rhythm splitting wasn't requested".

Choosing only Lead (or only Rhythm) still transcribes both parts internally (the lead stem and
the combined guitar stem, see below), because the bar-level role check needs both; only the
chosen part is shown and exported. Before the role check, each part's notes go through the
vocal de-bleed (see the engine research doc, G4).

## Accuracy work (2026-11)

Diagnosis and the measurements behind each change are in the session plan; the numbers below
come from `scripts/eval_lead_rhythm.py`.

**Evaluation harness.** `python scripts/eval_lead_rhythm.py guitarset --out data/eval_runs --tag <name>`
mixes the `comp` (rhythm) and `solo` (lead) take of one GuitarSet excerpt per player and genre
(30 clips, CC BY 4.0, downloaded to `~/.cache/audio_to_tab/datasets/guitarset/`: `annotation/`
and `audio_mono-mic/`), runs the real lead/rhythm stage and scores notes against the JAMS
annotations (pitch + onset ±50 ms, `scripts/eval_tabs.note_match_f1`): lead F1 vs the solo,
rhythm F1 vs the comp, both-stems F1, and role accuracy (of the notes transcribed correctly in
either stem, the share filed in the right one). `labels` mode runs the app's own path on your
songs (the analysis phase — separation, vocal suppression, split — then the tab job) and scores
it against hand-marked sections (`data/eval_labels/*.json`, format in the script's docstring); it
also reports label-free proxies per song (lead-share spread and changes per minute, notes left
out of the rhythm part, vocal residue in Lead). Splits and analyses are cached per clip (an
analysis is redone when the clip's audio, start or end changes); pass `--fresh-split` after
changing anything that feeds the splitter.

| GuitarSet, 30 clips | lead F1 | rhythm F1 | both F1 | recall | role accuracy |
|---|---|---|---|---|---|
| Before | 0.454 | 0.556 | 0.656 | 0.602 | 0.825 |
| After | 0.461 | 0.616 | 0.695 | 0.695 | 0.844 |

What changed, each measured on its own:

- **Transcription floors per part** (`pipeline.LEAD_STEM_FLOORS` / `RHYTHM_STEM_FLOORS`,
  separated input only, never below the user's thresholds). The general separated-input floors
  (frame 0.40, velocity 55, 80 ms) cost more rhythm recall than they gained precision. The lead
  keeps velocity 55 / 80 ms; the rhythm drops to 40 / 50 ms; both drop the frame floor to the
  default 0.30. Lead F1 +0.006, rhythm F1 +0.023, role accuracy +0.009.
- **Lead note pick.** From a multi-pitch attack the lead path keeps the loudest note unless it is
  a harmonic of a lower note in the attack, then that note. Neutral on GuitarSet (acoustic, few
  overtone ghosts; lead F1 +0.001); on distorted songs 17% of the old picks were an octave above
  the lowest note.
- **Rhythm notes from the combined guitar stem.** The rhythm stem is a residual with subtraction
  holes and smear, so rhythm notes are transcribed from the guitar stem the split started from.
  A note leaves the rhythm part only when the lead part already has it (same pitch within 60 ms,
  or one of its harmonics) **and** the lead stem holds ≥ 90% of both stems' energy at that pitch
  during the attack (`lead_rhythm_tab.drop_lead_owned`; the count is in `lead_rhythm_notes.json`
  → `rhythm_source`). Lower cut-offs dropped more comp notes than lead notes; no cut-off put lead
  lines back into the rhythm tab (lead notes in the rhythm tab 12.5% → 16.9%); and without the
  "lead part has it" condition, a song whose split files most rhythm playing as Lead lost a
  quarter of its notes from both tabs (now 98–99.7% of the guitar stem's notes end up in a tab).
  Rhythm F1 +0.038, role accuracy +0.011.
- **Vocal suppression before the split** (`vocal_debleed.guitar_for_split`, follows the vocal
  de-bleed setting). The splitter files singing as Lead (a vocals-only input went 99% to Lead),
  and the guitar stem carries a vocal copy at 0.24–0.35 of the vocal level at the sung pitch. The
  splitter now gets the guitar stem with that copy removed by power spectral subtraction
  (bleed gain × |vocals|, cut floor −20 dB); the report is in
  `lead_rhythm_split_diagnostics.json` → `vocal_suppression`. GuitarSet has no vocals, so this is
  measured on songs only: on one test song the vocal left in the Lead stem fell by 65% (from 0.12
  to 0.04 of the vocal level at the sung pitch) while the guitar stem lost 0.05 dB overall; on
  the other, the Lead stem held no measurable vocal to begin with. It adds the vocal pitch track
  (pyin) to the analysis phase: about 35–45 s for a 4–5 minute song, computed once and reused
  by the note de-bleed.

Measured and **not** adopted:

- **Chunking, overlap, windowing, TTA.** Shifting the 3 s chunk grid by 0.75 s changed the role
  in 0.2–0.8% of windows, with no pattern at chunk boundaries; the upstream ZFTurbo `demix`,
  overlap 4 and test-time augmentation each changed ≤ 0.4%. Roles come from the model, not from
  inference settings.
- **Per-note roles from the split's energy** (and a bar-level two-state HMM on top). With a Lead
  stem at ~2 dB SDR on GuitarSet, the per-pitch energy split is too noisy: filing every note by it
  lowered lead F1 and role accuracy, and deciding which copy of a duplicated note to keep by it
  was worse than the current bleed rule. The HMM could not be calibrated (GuitarSet has only 7
  lead-silent bars out of 360) and turned real lead bars off; it needs labelled songs.

## Remaining limits

- The split itself is the ceiling: on GuitarSet the Lead stem scores ~2 dB SDR and about a
  quarter of the lead tab's notes are rhythm notes that leaked into the Lead stem. Nothing
  tested after the split reduced that without losing real lead notes.
- On songs the model's idea of "Lead" changes from song to song (one test song: 81% of the
  playing in Lead; another: half of it ambiguous, label changes 21 times a minute). The role
  check and the changes above fix notes, not the audio stems you listen to.

## Diagnostics and warnings

`lead_rhythm_split_diagnostics.json` (warn-only, never blocks): per-stem RMS (dBFS), peak, spectral centroid, silence ratio, integrated loudness (BS.1770-style gated LUFS, numpy/scipy implementation — approximation, not ITU-certified), Pearson correlation of the two stems' 50 ms RMS envelopes, and the resample record. Warnings fire for: near-silent stems (< −60 dBFS), envelope correlation > 0.85, clipped input, mono input, very short input (< 5 s).

Technique hints (slides, hammer-ons, pull-offs, palm mute, harmonics) are **inferred heuristics from pitch/onset/timing** with a `low`/`medium` confidence label and an evidence string; bends and vibrato are never emitted because semitone-quantized MIDI carries no pitch-bend evidence. Weak evidence is omitted rather than guessed. Notes are gated on per-frame energy; low-confidence regions are marked in `lead_rhythm_notes.json`, never filled.

## Known failure modes

- **Dense mixes** — both guitars plus keys/pads in one band contaminate the rhythm residual; the rhythm tab gets extra voices.
- **Heavy distortion** — harmonic overlap makes the two stems' envelopes correlate; watch the > 0.85 warning.
- **Double-tracked guitars panned apart** — the model may assign one performance per stem, or merge both into one stem; the residual then contains the other performance plus bleed.
- **Mono or collapsed sources** — no stereo cues; short clips (< 5 s) give unreliable stats.
- **Rhythm stem is a residual** — subtraction artifacts and occasional peaks are possible; stems are peak-guarded at 0.99.

Real boundary conditions live in `tests/test_lead_rhythm_sep.py` (loader, pins, residual math, resample record, fail-loud), `tests/test_lead_rhythm_tab.py` (transcription paths, technique heuristics), `tests/test_musicxml_export.py`, `tests/test_pipeline_lead_rhythm.py` (routing, pre-pass default, no-fallback), and `tests/test_isolate_lead_rhythm.py`.
