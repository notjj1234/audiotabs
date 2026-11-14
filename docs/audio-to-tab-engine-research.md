# Audio→Tab Engine Research — OSS upgrade decision document

Date: 2026-11-14. Scope: engine accuracy only (notes, timing, fingering). All web claims verified against primary sources on 2026-11-14 unless noted. Songsterr evidence: `songsterr-ai-tabs/` (read-only; all artifacts dated 2026-11-13). Claims tagged `[verified]` (repo code or live evidence), `[inferred]` (reasoned from evidence), `[unknown]`, `[unverified]` (could not confirm from primary source — never relied on for a verdict).

---

## 1. Gap analysis — Songsterr observed behavior vs this repo

Songsterr stages from `songsterr-ai-tabs/06-pipeline.md` (Stage 1 is `[inference]` — their models are unpublished per `09-unknowns.md`; no claim here replicates them).

| Songsterr behavior | This repo today | Gap |
|---|---|---|
| Presigned intake, direct object-storage upload; mp3 up to full songs [observed] | Local file / yt-dlp ingest, ffmpeg normalize | None material (local app). |
| Musical hints: per-track instrument+tuning+capo, auto firstBarTempo/firstBarSignature/anacrusisSignature with user override [code+UI] | tempo override only; fixed beats_per_measure=4; no downbeat/meter/anacrusis detection | **No meter/downbeat/anacrusis**; wrong meter breaks barlines. |
| Server-side separation into lead/rhythm/bass/drums/vocals/keys; per-stem transcription [inference from product capability] | Optional guitar-stem-only separation (Demucs htdemucs_6s / guitar-ft / BS-RoFormer / SCNet); lead/rhythm heuristic split (`lead_rhythm.py`) gated to high confidence, else single stem | No bass/drums/vocals note transcription; lead/rhythm split is heuristic-only `[verified in lead_rhythm.py]`. |
| Per-stem note transcription with pitch/onset/duration + techniques (bend/vibrato/slide/palm-mute) [docs claim; schema unverified] | Basic Pitch (ICASSP 2022) monophonic-tolerant multipitch, thresholds + MIDI cleanup | Basic Pitch is the weakest stage: no techniques, limited polyphony, aggressive default thresholds (onset ≥0.58, frame ≥0.40, ≥90 ms under mix-aware) filter valid notes `[verified in pipeline.py, ANALYSIS.md #4]`. |
| Beat grid: tempo, time signature, anacrusis auto-detected [observed auto-detect in UI] | librosa onset-envelope tempo (clamped 60–180 BPM) + MIDI median-IOI fallback; 16th-note grid quantize with fixed 4/4 | No downbeats, no meter, no anacrusis; BPM clamp 60–180 loses slow/fast songs; no tempo-tap UI affordance beyond override field. |
| Quantization onto grid, durations as fractions [observed] | `quantize_sec=0.05` flat in cleanup + 16th grid in `rhythm.py` | Grid is tempo-derived but the cleanup quantize (50 ms fixed) and the tab grid are decoupled; double-grid can drift. |
| String/fret assignment from absolute pitch + tuning + capo, fingering model [observed `{fret,string,spn}`; forum reports single-string-movement bias] | Heuristic playability cost (fret distance, string-change cost, open-string penalty) `[verified in tab_generate.py]` | No learned fingering; known bias toward low-fret positions. Songsterr itself shows a fingering bias, so this gap is smaller than it looks `[inferred]`. |
| Measures/voices/beats grid, rest padding, per-track shards [observed] | ASCII tab + PDF, `TabDocument` events | Equivalent for single-track; no multi-track data model. |

## 2. Stage table

| Stage | Songsterr behavior | Current implementation | Candidate(s) | Evidence | License | Local runtime (Apple Silicon) | Verdict |
|---|---|---|---|---|---|---|---|
| Intake/trim | Presigned upload, start/end trim hints | ffmpeg normalize + trim | keep | `pipeline.py:_trim_audio` | MIT | trivial | Keep |
| Separation — guitar from mix | Must produce usable lead+rhythm guitar stems `[inference]` | Demucs htdemucs_6s (default), guitar-ft fine-tune (330 MB), BS-RoFormer SW, SCNet, ensemble | keep guitar-ft/RoFormer path; add Mel-Band RoFormer guitar model | ANALYSIS.md #3; thuhcsi/SCNet; audio-separator | MIT (Demucs code); weights NC historically `[unverified in current README]` | CPU/MPS, RAM-guarded already | Keep+upgrade (P1) |
| Separation — lead vs rhythm guitar | Two guitar tracks `[observed output]` | Heuristic spatial/register/role gate; emits split only when confident | trained 2-guitar separator (none OSS-proven) | `lead_rhythm.py` header (Foulon 2013, Pati & Lerch 2017) | — | — | Keep heuristic (no OSS model beats it reliably) |
| Separation — bass/drums/vocals stems | Per-track output stems `[inference]` | Demucs 6s emits them but only guitar+vocals kept | keep htdemucs_6s full stem set | `separate.py` | as above | fine | Keep (P2 wiring) |
| Transcription — guitar notes | Per-stem pitch/onset/duration (+techniques claimed) | Basic Pitch ICASSP 2022 + threshold cleanup | **hppss-tars? no — Practical: keep Basic Pitch but fix thresholds; research models (FretNet, YourMT3) not production-ready for this wiring** | `transcribe.py`; arXiv 2212.03023 (FretNet); arXiv 2407.04822 (YourMT3+) | Apache-2.0 (Basic Pitch) | CPU fast | Keep model (P0 threshold work), replace later only if eval shows gain |
| Transcription — techniques (bend/vibrato/slide/palm-mute) | Claimed in docs `[unknown]` schema | None | Guitar-TECHS dataset (arXiv 2501.03720) — no ready OSS inference model | docs claim only | dataset CC (paper); model `[unverified]` | — | Out of scope; honest "not supported" label (P2) |
| Transcription — drums | Drum track in output `[observed]` | None | ADTOF (MZehren/ADTOF) via MDX23C drum stem | github.com/MZehren/ADTOF; xavriley/adtof_plus_drum_transcription | **CC BY-NC-SA 4.0 — non-commercial** | CPU ok | Skip (license + out of single-guitar scope) |
| Beat/tempo/downbeat/meter/anacrusis | Auto tempo+signature+anacrusis with override `[observed]` | librosa tempo (60–180 clamp) + MIDI IOI | **Beat This! (CPJKU/beat_this, MIT)** for beats/downbeats; librosa for meter/anacrusis heuristics | arXiv 2407.21658; GTZAN downbeat F1 75.5% (cited in arXiv 2508.09790) | MIT | torch, ~tens of MB weights | **Upgrade (P0/P1)** |
| Quantization | Fractional durations on inferred grid | 50 ms cleanup quantize + 16th tab grid | librosa beat-synchronous quantize using Beat This! grid | `rhythm.py`, `midi_cleanup.py` | BSD | CPU | Upgrade with beat stage |
| String/fret + fingering | Tuning+capo-aware `{fret,string,spn}`, fingering model with known bias | Playability-cost heuristic | keep heuristic; optional position-preference user knob; research (arXiv 2608.30854 playability-aware A2T) not packaged | `tab_generate.py` | MIT | trivial | Keep (P1 polish) |
| Tab assembly/export | Per-track measure/voice/beat shards + rest padding | ASCII tab + PDF via reportlab + result JSON | optional PyGuitarPro (.gp5) export; music21/partitura not needed | `tab_bundle.py`, `write_tab_exports` | PyGuitarPro `[unverified]`; music21 BSD-3; partitura Apache-2.0 | trivial | Keep; P2 optional .gp5 |

## 3. Candidate research (verified 2026-11-14)

- **Demucs v4 / htdemucs_6s** — github.com/facebookresearch/demucs. Code MIT [verified via repo license API]. Hybrid Transformer, 6 stems. Default in repo. Weights auto-download via torch hub (~166 MB). Historical README stated weights CC-BY-NC 4.0; current main README License section states only MIT for code — weight license now `[unverified]`; flagged as risk, not a blocker for local personal use. Failure modes: guitar bleed in full mixes (ANALYSIS.md #3, `[verified]` internal).
- **audio-separator / BS-RoFormer / Mel-Band RoFormer** — github.com/nomadkaraoke/python-audio-separator, MIT [verified]. Wraps ZFTurbo/Anjok07 community weights (MDX23, Mel-Band RoFormer guitar models on HF; most model cards carry no SPDX license `[verified via HF API — license field None]`, i.e. all-rights-reserved defaults — treat as non-commercial research use). Mel-Band RoFormer paper arXiv 2310.01809. Already wired in repo (`roformer.py`, bs_roformer_sw / melband_roformer_guitar models). RAM guard exists (90 s/180 s limits) `[verified]`.
- **SCNet** — github.com/thuhcsi/SCNet, MIT [verified]. Paper arXiv 2401.13276: MUSDB18-HQ avg SDR 9.0 dB, CPU inference 48 % of HTDemucs time [verified via paper/CSDN summary of paper]. Already wired (`scnet.py`). 4-stem — no dedicated guitar stem; guitar path stays Demucs/RoFormer.
- **Basic Pitch** — github.com/spotify/basic-pitch, Apache-2.0 [verified]. ICASSP 2022; ONNX weights bundled with pip install. Current transcription stage. Failure modes: octave errors, weak polyphony, thresholds over-prune under mix-aware defaults (ANALYSIS.md #4, `[verified]`).
- **MT3 / YourMT3+** — github.com/magenta/mt3, Apache-2.0 code [verified]; T5X/JAX stack, multi-task multi-instrument. YourMT3+ (arXiv 2407.04822) improves encoder + stem augmentation; code release not located in primary search `[unverified]`. Integration cost L (JAX/t5x on macOS, checkpoint plumbing); benefit for *solo guitar* over Basic Pitch unclear — MT3 class shines on multi-instrument, which is P2 scope. Not P0.
- **FretNet** — github.com/cwitkowitz/guitar-transcription-continuous (paper arXiv 2212.03023). Continuous pitch contours per string/fret; research codebase (MIT per sibling repo cwitkowitz/guitar-transcription-with-inhibition `[verified]`; this repo's license file not fetched `[unverified]`), training-data plumbing (GuitarSet) required. Not packaged for drop-in inference. Watchlist only.
- **Guitar-TECHS** — dataset paper arXiv 2501.03720 (electric guitar, techniques, multi-hardware). Dataset/resource, not an inference model `[verified from paper]`. No ready OSS technique-transcription model found `[verified via bounded search]`.
- **ADTOF** — github.com/MZehren/ADTOF. Dataset + CRNN drum transcription. License CC BY-NC-SA 4.0 [verified via repo license file mirror] — non-commercial; conflicts with nothing here (drums out of scope) but excludes it. Skip.
- **Omnizart** — github.com/Music-and-Culture-Technology-Lab/omnizart, MIT code [verified]; covers drum/beat/vocal/chord transcription. Heavy deps (magenta-tensorflow), model downloads from project site, maintenance slow. Superseded by targeted picks. Skip.
- **Beat This!** — github.com/CPJKU/beat_this, MIT [verified]; paper arXiv 2407.21658 ("Accurate beat tracking without DBN postprocessing"). `beat-this==1.1.0`; `final0` weights are 77.3 MiB, SHA256 `8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331` [verified 2026-11-14]. Reported downbeat F1 75.5 % on GTZAN, SOTA-class at publication [verified via arXiv 2508.09790 citation table]; BeatFM (arXiv 2508.09790) claims +4.1 % over it but code/weights `[unverified]`. Directly fills the downbeat/meter gap; pip-installable, torch-only. **Primary P0/P1 upgrade.**
- **madmom** — PyPI madmom 0.16.1: BSD code, model files CC BY-NC-SA [verified via PyPI metadata]. Downbeat tracking (DBN) is its strength but Beat This! beats it with MIT weights. Skip.
- **librosa** — already a dependency; tempo/onset/meter heuristics; ISC/BSD lineage, free. Keep as fallback and for anacrusis heuristics.
- **music21** (BSD-3-Clause [verified via repo license API]) — chord/key/musicXML; repo's `chords.py` already does chord naming; no need.
- **partitura** (Apache-2.0 [verified via PyPI]) — symbolic music I/O; useful only if MusicXML export wanted. Defer.
- **alphaTab** (MPL-2.0 [verified via LICENSE file]) — JS/.NET renderer, GP import. UI-level; out of engine scope per constraints.
- **PyGuitarPro** — PyPI 0.11 active; upstream `LICENSE` verified LGPL-3.0 on 2026-11-14 (`https://github.com/Perlence/PyGuitarPro/blob/master/LICENSE`). Commercial use is permitted under LGPL obligations; keep it as an optional, unmodified dependency. Optional .gp5 export (P2).

## 4. Build-vs-keep verdicts

1. **Separation (guitar): KEEP.** Repo already matches best OSS guitar isolation (guitar-ft Demucs + BS-RoFormer + SCNet options, RAM guards) `[verified]`. Marginal gain from swapping is unproven; cost is high. P1 micro-upgrade: default `melband_roformer_guitar` where RAM allows.
2. **Transcription: KEEP Basic Pitch for P0; fix its configuration.** Evidence of material gain from replacing it *for solo guitar* is absent — MT3-class integration is L-effort with unclear per-guitar gain `[inferred from task mismatch]`. P0 instead removes the self-inflicted accuracy loss: mix-aware thresholds (onset ≥0.58/frame ≥0.40/≥90 ms) and cleanup floors over-prune valid notes (ANALYSIS.md #4/#16, `[verified]`). Tune per-path with eval harness before/after.
3. **Beat/tempo: UPGRADE.** Add Beat This! for beats/downbeats (MIT, torch, small), keep librosa/MIDI-IOI fallback. Largest single gap vs the Songsterr contract (meter/downbeat/anacrusis auto-detect) at S–M effort.
4. **Quantization: UPGRADE with beat grid.** Drive quantize from detected beat grid; remove decoupled 50 ms cleanup quantize on the tab path.
5. **Lead/rhythm split: KEEP heuristic.** No OSS model demonstrably better; repo gate already prefers "ambiguous over wrong" `[verified]`.
6. **Fingering: KEEP heuristic.** Songsterr's own fingering has a reported bias; our cost model is competitive for P0. P1: add low-fret vs position preference knob.
7. **Drums/techniques/other stems: SKIP (P2 at most).** ADTOF non-commercial; technique models don't exist OSS; multi-track output is a scope decision (§5).

## 5. Output scope decision

**Stay single-guitar tab for P0–P1.** Rationale: the product's differentiator and the eval metric are guitar-tab correctness; multi-track (bass/drums/vocals notation) requires drum transcription (best OSS option non-commercial), a per-track data model, and export work — L effort for value the current UI doesn't present. P2 may add bass + drum *grid placeholder* tracks from htdemucs_6s stems only if a permissive drum model appears. Songsterr parity is the contract for *behavior*, not the mandate for *scope*.

## 6. Target architecture

Stages and selected implementations (changes relative to current `pipeline.py`):

1. **Ingest/trim** — unchanged.
2. **Separate** — unchanged backend; optional Mel-Band RoFormer guitar model selection already present. Fallback chain: guitar-ft/RoFormer → htdemucs_6s → transcribe mix (existing).
3. **Beat grid (NEW, `src/audio_to_tab/beatgrid.py`)** — Beat This! (`beat_this` pip pkg, MIT) → beats + downbeats; derive BPM (uncapped, fix 60–180 clamp to e.g. 40–240), meter (4/4 vs 3/4 by downbeat spacing), anacrusis (first downbeat offset). Fallback: existing librosa/MIDI-IOI path, unchanged behavior. `resolve_tempo()` gains optional `beat_model` input; `TempoEstimate` gains `beats_per_measure`, `downbeats`, `anacrusis_sec` fields (additive — old fields untouched, `PipelineConfig` compatible).
4. **Transcribe** — Basic Pitch, thresholds made path-dependent and eval-tuned; cleanup floors relaxed on separated-stem path (stems are cleaner than full mixes, so mix-aware floor justification weakens `[inferred]`).
5. **Quantize** — quantize note starts/ends to Beat-This! beat-synchronous 16th grid in `rhythm.py`; retire the 50 ms cleanup-quantize on the tab path (keep for MIDI artifact only).
6. **Tab/fingering** — unchanged heuristic; `beats_per_measure` fed from detected meter (already a config field).
7. **Export** — unchanged ASCII/PDF/result; data model gains meter/downbeat metadata for future P2.

Public interface deltas: `PipelineConfig` gains optional `beat_model: str = "beat_this" | "librosa"` and `auto_meter: bool = True` (defaults preserve current behavior when dependency absent). No removals.

## 7. Evaluation protocol

Harness: `scripts/eval_tabs.py` (new, this phase). Inputs: `--audio` clip(s), optional `--reference-midi`. Runs `run_pipeline()`, computes:

- **Note F1 vs reference MIDI**: match equal MIDI pitches with onset ±50 ms using maximum-cardinality matching per pitch; `mir_eval` is not required.
- **Tempo error**: |bpm − ref| / ref; downbeat F1 if reference MIDI has barlines.
- **Playability**: % of consecutive notes with fret jump > 4; % chord spans > 5 frets; open-string usage under position (from `TabDocument`).
- **Density sanity**: notes/sec vs reference ratio (catches over/under-pruning).

Metrics printed as JSON; `--before/--after` runs diffed. Synthetic clips cover reference-MIDI note/tempo metrics. The user supplied `/Users/JJ/Downloads/フルスピード・ボーイ.mp3` for local validation on 2026-11-14; it is not copied into the repository or redistributed. No reference MIDI was supplied for it, so real-audio note F1 remains unavailable. The harness also accepts fingering, model, and duration overrides for reproducible A/B runs.

## 8. Roadmap

| Priority | Item | Quality impact | Effort | Risk | Files | Deps/license cost |
|---|---|---|---|---|---|---|
| **P0** | Eval harness + baseline; tune transcription thresholds per path (remove over-pruning on stem path) | Direct: fewer false negatives, fewer EmptyTranscriptionError | S | Low (config-level) | `pipeline.py`, `midi_cleanup.py`, `scripts/eval_tabs.py`, tests | none |
| **P0** | Beat This! beat/downbeat/meter/anacrusis stage with librosa fallback | High: correct barlines, tempo uncapped | M | Medium (new dep `beat-this`, torch weights ~tens MB) | `beatgrid.py` (new), `tempo.py`, `pipeline.py`, `tab_bundle.py`, tests | MIT pkg; weights from the authors' project storage, SHA256 recorded above |
| P1 | Quantize to beat-synchronous grid; retire 50 ms dual quantize | Medium: timing readability | S | Low | `rhythm.py`, `midi_cleanup.py` | none |
| P1 | Mel-Band RoFormer guitar default on capable RAM; fingering preference knob | Medium | S | Low | `separate.py` wiring, `tab_generate.py`, UI label | none (already supported) |
| P2 | .gp5 export (PyGuitarPro) after license check; technique labeling only if OSS model materializes; multi-track scope revisited | Optional | M–L | Medium | `tab_bundle.py` | per-item |
| P2 | MT3-class multi-instrument transcription if eval justifies | Unknown | L | High (JAX stack) | new module | Apache-2.0 code |

**Expected accuracy ceiling**: with OSS-local stack, realistic ceiling is "good draft, needs human pass" — same class Songsterr itself claims (help center: draft quality, human review expected). Unsolved after P0–P2: techniques (bends/vibrato/slides) — no OSS model; true lead/rhythm separation in same-register center mixes — architecturally open research problem (noted in `lead_rhythm.py`).

## 9. Risks

- **Licenses**: community separation weights (MDX/RoFormer HF cards) carry no explicit license → treat as non-commercial research use; Demucs weight license now unstated in current README (historically CC-BY-NC) → local personal use is fine, redistribution is not. ADTOF explicitly NC (skipped). Mitigation: record licenses in doc; prefer MIT/Apache picks (Beat This!, SCNet, audio-separator wrapper).
- **Model drift**: hosted weights can move; guitar-ft already SHA256-pinned `[verified]`; Beat This! uses pinned package `beat-this==1.1.0`, named checkpoint `final0`, and a recorded SHA256.
- **Hardware**: Beat This! torch inference is light vs existing RoFormer guards; keep `hardware.py` gates; fallback to librosa path on any failure.
- **Regressions**: all changes behind additive config fields + eval harness before/after; `make test` gate; threshold changes validated on real clips before merging.
- **Rollback**: P0 touches are config-level + one new module; revert = single commit. No schema or API removals anywhere.

## Evidence gaps (explicit)

1. Real-audio reference MIDI remains unavailable; the supplied user clip supports smoke/playability validation, not note-F1 measurement.
2. Demucs/RoFormer weight licenses not machine-verifiable (see §9).
3. YourMT3+ code/weights not found in primary sources.
4. Songsterr technique fields never observed in evidence (schema `[unknown]`) — nothing to copy even if wanted.

## 10. Implementation validation — 2026-11-14

P0 and P1 are implemented. P1 adds detected-beat 16th-note quantization, preserves the 50 ms grid only for the final MIDI artifact, selects Mel-Band guitar automatically when its installed runtime and duration/RAM guards pass, and adds `playable`, `low_fret`, and `position` fingering preferences. Existing positional `PipelineConfig` fields remain unchanged; new fields are appended. The evaluation harness requests the unquantized tab-source MIDI through the additive `include_tab_source` pipeline option, so playability metrics measure the same note timings used to build the production tab rather than the separately quantized MIDI download.

Measured results:

| Clip / configuration | Note F1 | Tempo error | Notes | Fret jumps >4 | Chord spans >5 |
|---|---:|---:|---:|---:|---:|
| Synthetic 120 BPM, before/after P1 | 0.8421 / 0.8421 | 0.0 / 0.0 | 11 / 11 | — | — |
| Synthetic 200 BPM, before/after P1 | 0.1923 / 0.1923 | 0.0 / 0.0 | 26 / 26 | — | — |
| User clip, default before/after P1 | unavailable | unavailable | 1262 / 1262 | 6.36% / 6.36% | 1.46% / 1.46% |
| User clip, low-fret preference | unavailable | unavailable | 1262 | 2.15% | 1.46% |
| User clip, position preference | unavailable | unavailable | 1262 | 2.87% | 1.46% |
| User clip, first 60 s, separated Demucs fallback | unavailable | unavailable | 167 | 3.95% | 0.0% |
| User clip, first 60 s, unseparated | unavailable | unavailable | 282 | 3.61% | 0.0% |

The real clip's full-mix detected tempo is 187.5 BPM at low confidence; the final separated 60-second validation detected 240 BPM. Beat-synchronous versus fixed-grid tab reconstruction shifts event starts by 25.367 ms mean and 80 ms maximum on 1117 events. The 200 BPM synthetic reference is intentionally alternating-pitch material; its low note F1 is not evidence of production transcription quality. Repeated real-audio smoke runs can vary at the note-count level, and the supplied clip has no reference MIDI, so these metrics do not establish transcription accuracy or prove that separation improves it.

The evaluation matcher now uses maximum-cardinality onset matching per pitch. Its unsorted-reference regression test failed before the fix and passes afterward.

Conditional P2 items remain evidence-gated: MT3-class replacement is not justified without real reference-MIDI gains; technique inference has no verified packaged OSS model; multi-track drums still lack a permissive production choice. Optional GP5 export is implemented with the verified LGPL-3.0 PyGuitarPro dependency. Round-trip tests cover tempo, meter, string/fret assignments, cross-measure ties, two-voice overlaps, more-than-two-overlap overflow tracks, duplicate same-string onsets, missing-dependency guidance, and pipeline artifacts.

Automatic Mel-Band selection checks actual model capability, not only package presence. `bs-roformer-infer==0.1.5` provides BS-RoFormer but no Mel-Band architecture; without `audio-separator`, automatic mode falls back to `htdemucs_6s` instead of failing. Installation of `audio-separator` remains blocked by dependency resolution: the tested releases 0.37.1 through 0.48.0 require NumPy 2, while this project requires `numpy>=1.24,<2`. No dependency resolver override or NumPy upgrade was applied.

Final real-audio GP5 validation used the first 60 seconds with automatic model selection and the Demucs fallback. PyGuitarPro parsed the regenerated file successfully: 59 measures, 198 notes, and 32 ties across one track. GP5 note counts include tied continuations and are therefore not expected to equal pipeline note counts. Final verification: `make test` reported 228 passed and 1 skipped; scoped Ruff and `git diff --check` passed.
