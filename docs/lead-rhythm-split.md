# Lead/Rhythm guitar split

The `lead_rhythm_split` mode (Streamlit: "Lead + Rhythm" engine; `IsolateConfig(model="lead_rhythm_split")`) is the pipeline's first genuine *lead vs rhythm* separator. It runs: guitar isolation pre-pass → Mel-Band RoFormer Lead/Rhythm split → per-stem transcription → per-stem tab + exports (`.tab`, `.pdf`, `.gp5`, per-stem MIDI, two-track `stems.mid`, MusicXML 4.0).

## Why the guitar pre-pass runs first

The split model (`mbr_lead_rhythm_guitar_listra92`) was trained on isolated-guitar material: it expects one guitar performance and splits it into "the lead line" vs "everything else that guitar plays". Fed a full mix, it instead splits "most prominent guitar" vs "the rest of the mix", which is not what the tabs need. The pre-pass gives it a single clean guitar stem, and the guitar-ft fine-tune of htdemucs_6s (`adityalakhani/htdemucs-6s-guitar-ft`, integrated in `separate.py`) is the project's best single-guitar source. The pre-pass is on by default in this mode; turn off "Separate guitar stem" (pipeline: `separate_stems=False`) when the input file is already an isolated guitar stem — it is skipped then. Pre-pass quality uses the existing fast/balanced/high/extreme shifts/overlap map.

## Why this model is the only lead/rhythm splitter

- `htdemucs_6s` has one combined guitar stem — structurally incapable of lead/rhythm (Demucs is never the lead/rhythm splitter here).
- `mbr_lead_rhythm_guitar_listra92` is, as of integration (2026-11), the only Mel-Band RoFormer checkpoint in the integrated set trained for exactly the two stems `[Lead, Rhythm]` (`training.instruments`, `target_instrument: Lead`, 44.1 kHz, single-target + residual). No second lead/rhythm model is integrated, and there is no "auto" choice between them.
- The older `lead_rhythm.py` (`IsolateConfig.lead_rhythm` / `dual_guitar`) remains a post-hoc heuristic classifier on one guitar stem — a fallback for when the RoFormer runtime (`pip install -e ".[roformer]"`, bs-roformer-infer) is not installed, not a separator.

Checkpoint facts: 337,073,664 bytes, SHA256 `b3c47bca33609ca1ba0bb2d2076410bfd1eb941b051b72afc1f3e24d12b17eef`, cached under `separator_cache_dir()`, pinned via urllib (no huggingface_hub). Hosted on the community mirror `noblebarkrr/mvsepless_resources` — **no license is stated; treat as all-rights-reserved** (same posture as BS-RoFormer-SW). The `audio-separator` UVR stack cannot load it (registry-only model loader; also blocked by its NumPy 2 requirement), so inference uses the in-process bs-roformer runtime that `run_melband_guitar` already prefers.

Inside the mode, any failure is loud (`Lead/rhythm split failed: …`) — nothing silently falls back to a combined guitar stem. Outside the mode, behavior is unchanged.

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
