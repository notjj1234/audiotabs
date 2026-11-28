# Guitar separation: evaluation and decisions (2026-11-26)

The Lead/Rhythm split can only be as good as the guitar stem it gets. Until this change the
web app's default path (*Lead + Rhythm* engine) always fed it the htdemucs_6s guitar stem
(guitar-ft when cached), even when BS-RoFormer SW, a much stronger guitar separator, was
installed. This page records how that was measured, what changed, and what was tried and
dropped.

All numbers come from `scripts/eval_guitar.py`, which runs the app's own path: the analysis
phase (`analysis.run_analysis`: 6-stem separation, vocal suppression, Lead/Rhythm split) and
then the tab job (`pipeline.run_pipeline`, parts lead + rhythm). Raw results are in
`data/eval_runs/guitar/*.json` (git-ignored).

## Test material: band mixes with a known guitar part

GuitarSet has the exact notes of every take, but it is isolated acoustic guitar, so it can't
show what separation does. `eval_guitar.py bandmix` puts each GuitarSet comp + solo pair
(rhythm = comp, lead = solo; one excerpt per player and genre, 30 clips) over real drums, bass
and vocals stems from the MUSDB18 7-second sample set, at guitar 3 dB below the backing. The
backing comes from real multitracks, not from either separator, so neither model is
favoured. MUSDB's `other` stem is left out because it often holds guitars. Datasets:

- GuitarSet (CC BY 4.0): `~/.cache/audio_to_tab/datasets/guitarset/`
- MUSDB18 7 s sample (research use only):
  https://zenodo.org/records/3270814/files/MUSDB18-7-STEMS.zip, unpacked to
  `~/.cache/audio_to_tab/datasets/musdb18_7s/raw/`

Metrics: guitar-stem SI-SDR against the true guitar; note F1 (pitch + onset ±50 ms) of the lead
tab against the solo, the rhythm tab against the comp, and both tabs against both takes; role
accuracy (of the notes transcribed correctly in either tab, the share in the right one).
Label-free proxies per run: % of tab notes outside the guitar's range, notes per second,
median polyphony per part, and bass-stem/guitar-stem envelope correlation (a bleed indicator).

## Stage 1: BS-RoFormer SW feeds the split

| Stage 1 (30 band mixes) | guitar SI-SDR | lead F1 | rhythm F1 | both F1 | recall | role acc. | analysis s/clip |
|---|---|---|---|---|---|---|---|
| htdemucs_6s + guitar-ft (before) | 8.96 dB | 0.432 | 0.483 | 0.589 | 0.570 | 0.810 | 24 |
| BS-RoFormer SW (after) | 14.55 dB | 0.458 | 0.575 | 0.662 | 0.661 | 0.836 | 88 |
| clips better / worse | 30 / 0 | 17 / 11 | 30 / 0 | 30 / 0 | | 25 / 5 | |

Clips are 12–30 s, so analysis time is about 3.5× the clip length with BS-RoFormer on Apple
MPS, against about 1× with Demucs. Out-of-range notes were 0% in both runs and the bass/guitar
envelope correlation was about 0 in both: on this material neither separator leaves bass in
the guitar stem.

Two real songs (the `data/eval_labels/` test songs `boukyaku_no_mobel` and
`full_speed_boy`, first 180 s, `eval_guitar.py proxies`) have no note labels, so they can
only be checked with the label-free proxies:

| Real songs, 0–180 s | bass/guitar env. corr. | notes/s | rhythm polyphony | out of range | analysis s/song |
|---|---|---|---|---|---|
| htdemucs_6s + guitar-ft | 0.077 / 0.438 | 14.7 / 6.3 | 5 / 2 | 0% | 115 |
| BS-RoFormer SW | 0.066 / 0.344 | 14.6 / 7.0 | 5 / 2 | 0% | 256 |

The lower bass/guitar correlation on `full_speed_boy` points to less bass in the guitar stem.
The other proxies barely move, and they can't show tab accuracy. Over full songs BS-RoFormer
analysis took about 2.2× as long as Demucs, about 1.4× the song length on MPS.

What changed (`roformer.split_stage1_skip_reason`, `analysis.analysis_separation_model`,
`isolate._run_lead_rhythm_split_isolation`):

- With the *Lead + Rhythm* engine, the analysis separates with `bs_roformer_sw` when
  `bs-roformer-infer` is installed (`[roformer]` extra) and the device is CUDA or MPS.
- CPU-only hosts, a missing runtime, or a chosen Demucs guitar checkpoint keep htdemucs_6s
  (guitar-ft when cached). The reason is written to `analysis.json` → `separation.roformer_skipped`.
- If BS-RoFormer fails (clip over the RoFormer length cap, download or runtime error), the
  analysis separates again with Demucs instead of failing. `analysis.json` → `separation`
  records `fallback_from` and `fallback_reason`. Choosing the `bs_roformer_sw` engine directly
  still fails loudly as before.
- `ATT_SPLIT_STAGE1=demucs` turns the upgrade off; `ATT_SPLIT_STAGE1=bs_roformer_sw` forces it
  on CPU.
- Weights: `enerjazzer/BS-ROFO-SW-Fixed`, SHA256 `24e7d35e…916e`, downloaded on first use to
  the bs-roformer-infer cache (or `separator_cache_dir()`), never committed. **No license is
  stated for these weights.**

The analysis fingerprint still keys on the chosen engine, so the tab job's mismatch check
(HTTP 409) behaves exactly as before. Only the stems inside a new analysis change.

## Stereo pre-split (`guitar_roles_stereo.py`, opt-in)

The module splits a guitar stem into a centre part (lead candidate) and the sides (rhythm
candidate) with soft STFT masks (n_fft 4096, hop 1024). The pan index is
`p = (|R| - |L|) / (|R| + |L|)`; the centre weight is 1 up to |p| = 0.2 and falls linearly
to 0 at |p| = 0.6. Near-mono stems (L/R correlation > 0.95) pass through, and the decision is
logged.

Pan alone fails on the case it is meant for. Two independent, equally loud guitars
hard-panned left and right have similar magnitudes in the bins they share, so p ≈ 0 and both
are filed as centre: in the unit test, half of the hard-panned side noise leaked into the
centre part. The centre weight is therefore multiplied by a short-time inter-channel
coherence weight (`use_coherence`, on by default, 8-frame smoothing, 0 at coherence ≤ 0.5,
1 at ≥ 0.9). A real centre source is phase-coherent between channels; independent
performances are not. Every threshold is in `StereoSplitConfig`.

With `ATT_STEREO_PRESPLIT=1`, `lead_rhythm_sep.run_lead_rhythm_split` gives the Lead/Rhythm
model the centre part. The rhythm stem stays the residual of the **full** input, so side
content the model never saw stays in rhythm. The report is written to
`lead_rhythm_split_diagnostics.json` → `stereo_presplit`.

### Measured on panned band mixes: stays opt-in

The default band mixes put both guitar parts in the centre, where the pre-split does nothing.
`eval_guitar.py bandmix --layout` pans the parts (equal-power, 10 clips, BS-RoFormer SW
stage 1): `lead_centre_rhythm_left` follows the convention, `lead_left_rhythm_centre` breaks it.

| Layout (10 clips) | pre-split | lead F1 | rhythm F1 | both F1 | role acc. |
|---|---|---|---|---|---|
| lead centre, rhythm left | off | 0.648 | 0.658 | 0.704 | 0.950 |
| lead centre, rhythm left | on | 0.655 | 0.663 | 0.706 | 0.954 |
| lead left, rhythm centre | off | 0.183 | 0.564 | 0.663 | 0.705 |
| lead left, rhythm centre | on | 0.022 | 0.549 | 0.669 | 0.637 |

On the convention layout the pre-split adds under 0.01 (lead F1 better on 7 clips, worse on
3), because the Lead/Rhythm model already gets 0.95 role accuracy there. When the convention
is broken, it wipes out the lead (lead F1 and role accuracy worse on 9 of 10 clips): the
model only sees the centre, where the rhythm part is. A small gain in one case doesn't pay for
that loss in the other, so `ATT_STEREO_PRESPLIT` stays off by default.

The second row also shows something about the Lead/Rhythm model itself. Moving the lead off
centre drops lead F1 from 0.65 to 0.18, so the model leans heavily on pan position. Songs
with an off-centre lead will get poor lead tabs whatever stage 1 does.

## Role check: one config, hysteresis, per-note roles

`guitar_roles.py` (the bar-level role check after transcription) now takes every threshold
from one frozen `RoleConfig` dataclass (`assign_roles(..., config=)`). Its defaults are the
old module constants, which are kept. The rule "a weak bar moves only when a neighbour wants
the same move" is now a setting, `min_run_bars` (default 2, the old behaviour): a bar without
strong evidence moves only inside a run of that many agreeing bars. `lead_rhythm_roles.json`
also has a `notes` list with each final note's role, bar and source (`split`, `moved_bar`, or
`lead_chord` for chord attacks given from the lead stem to rhythm), plus the `config` used.
On the 30 GuitarSet clips every per-clip result is identical before and after (lead F1
0.4607, rhythm 0.6161, role accuracy 0.8444).

**No per-note confidence.** A confidence made from the bar's texture cues (share of single
notes, stepwise contour, no repetition, no chord outline that agree with the note's role) was
measured on the same 30 clips, on the 5,895 notes that match exactly one of the two takes. It
pointed the wrong way: AUC 0.46, with notes at confidence 1.0 right 74% of the time and notes
at 0.25 right 81%. Rhythm-tab notes are right 78–89% of the time whatever the bar looks like;
lead-tab notes 49–70%, and the most "lead-like" bars are where comp notes leak into the lead
stem. A number that ranks the worst notes as the safest would mislead, so none is reported.

## Note transcription: YourMT3+ (opt-in, 2026-11-27)

Better separation lifted real songs only ~2%, and on clean isolated GuitarSet takes Basic
Pitch itself scores 0.75 note F1, so transcription is now the ceiling. Slowing the audio down
before Basic Pitch made it worse (0.750 at 1×, 0.728 at 0.5×, 0.679 at 0.25× with pitch kept,
0.704 at 0.5× tape-style; 20 GuitarSet takes). The phase vocoder smears note attacks.

Candidates with downloadable weights: YourMT3+ (Chang et al. 2024, arXiv 2407.04822, 88–92
GuitarSet onset F1 in-domain vs 79 cited for Basic Pitch, code GPL-3.0) and a small
GuitarSet-only tablature CNN (ErenReyhanlioglu/Guitar-Transcription, MIT). Riley et al. 2024
and FretNet release no weights; MuScriptor's are non-commercial.

**Held-out test: EGDB** (Chen et al. 2022, electric guitar, unseen by both models; 24 clips
per tone, every tenth track; dataset states no licence, used locally only). YourMT3's
GuitarSet split picks a random player per piece with no seed, so GuitarSet can't give it a
clean score. Note F1 (onset ±50 ms + pitch), both models without the 50 ms grid snap, as the
app's pipeline transcribes:

| Tone | Basic Pitch | YourMT3+ | YourMT3+ wins |
|---|---|---|---|
| DI (clean) | 0.687 | **0.812** | 23 / 24 |
| Marshall (crunch) | 0.712 | **0.765** | 18 / 24 |
| Mesa (high gain) | **0.695** | 0.659 | 10 / 24 |
| EGDB real recordings (4 clips) | 0.718 | **0.882** | 4 / 4 |

On the 30 band-mix stems (GuitarSet, which YourMT3 partly trained on, so flattering): guitar
stem 0.696 → 0.782, lead stem 0.359 → 0.411, rhythm stem 0.520 → 0.511. YourMT3 on the full
mix, guitar programs only, scored 0.656, below either model on the separated stem. Speed on
Apple MPS: 0.3× real time alone, ~1× with the GPU shared. Snapping onsets to the 50 ms grid
costs both models 2–3 points.

**What shipped:** `ATT_TRANSCRIBER=yourmt3` (default stays Basic Pitch). YourMT3's pinned
transformers 4.45 needs huggingface_hub < 1 (the app has 2.x) and transformers 5 can't import
its T5 code, so it runs out of process: `python -m audio_to_tab.yourmt3 setup` makes a
separate virtualenv under `~/.cache/audio_to_tab/yourmt3`, and `yourmt3_runner.py` runs there,
downloading code and checkpoint from a pinned Space revision on first use. GPL code never
ships with the app, and audio never leaves the machine. Any failure (no environment, crash,
timeout, bad output) logs a warning and falls back to Basic Pitch. Only the guitar parts use
it: bass, keys and other pass `allow_yourmt3=False` because they weren't measured. A
cancelled tab job kills the runner at once (`run_pipeline` passes its cancel token through
`yourmt3.abort_scope`) instead of falling back.

## Measured and not adopted

Each was measured on the material above or on the 30 GuitarSet clips from
`scripts/eval_lead_rhythm.py`. Don't retry these without new evidence.

- **Note-level role vote on the rhythm part.** Where the errors are (GuitarSet, current
  pipeline): 32% of solo notes are only in the rhythm tab, 27% of lead-tab notes are comp
  notes, and 34% of comp notes are missing entirely. A classifier on rhythm-tab notes
  (polyphony at onset, pitch, top voice, duration, velocity, whether lead is sounding, local
  median pitch and density) separated solo from comp notes at AUC 0.71 (logistic regression)
  and 0.73 (gradient boosting), 5-fold grouped by clip. At a confident 0.8 cut-off it would
  move 30 notes out of 4,362. Note texture doesn't separate the two roles when both play at
  once, which matches the earlier "per-note roles from split energy" result. The window vote
  (polyphony, median pitch, inter-onset regularity, centre/side share, hysteresis) assumes one
  role at a time, and GuitarSet has no such material to calibrate it on, so it wasn't built.
- **pYIN octave correction of lead notes.** Only 2.6% of lead notes are an octave off a solo
  note. Re-tracking the lead stem with `librosa.pyin` and moving notes to its octave changed
  lead F1 from 0.4607 to 0.4609. Of the 54 corrections, 39 didn't match the solo: they
  "corrected" rhythm notes that leaked into the lead stem. pYIN costs 0.2× real time.
- **Bend and vibrato marks from pYIN.** Against GuitarSet's annotated pitch contours (601
  matched lead notes, 60 with a real bend over 80 cents), bend detection on the lead stem had
  precision 0.33 and recall 0.07. Basic Pitch tends to split a bend into separate notes, and
  the lead stem is noisy. Wrong technique marks on a tab are worse than none, so bends and
  vibrato are still never emitted.
- **Separate rhythm cleanup (30 ms strum merge, drop notes below E2).** It already happens:
  `tab_generate` groups onsets within 30 ms into one chord event, and pitches below the
  tuning's lowest string have no fret position, so they never reach the tab. 0% of notes were
  out of range in every run above.

## MVSEP Lead/Rhythm backend (not built)

MVSEP's documented API (https://mvsep.com/en/full_api) has `POST /api/separation/create`
(`api_token`, `audiofile`, `sep_type=101` "MVSep Lead/Rhythm Guitar", `add_opt1` 0 = two-stage
SDR 9.21 / 1 = one-stage SDR 9.02, `output_format`) and
`GET /api/separation/get?hash=` (status `waiting` / `processing` / `done` / `failed` / …).
Neither that page nor the OpenAPI spec (`/misc/mvsep-openapi-spec.json`) documents the shape
of `data.files`, where a finished job's download links are. Non-premium accounts get one job
at a time. A client written against a guessed response shape, which uploads people's audio,
would go untested here, so it waits for a real API token or a sample `done` response.
