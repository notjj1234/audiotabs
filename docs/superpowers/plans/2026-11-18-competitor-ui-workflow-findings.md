# Competitor UI / Functionality / Workflow Findings

> **Purpose:** Planning synthesis of every REA handoff under `rea-md-files/`. Use this when deciding what AudioTabs should steal, skip, or adapt.  
> **Sources:** `/Users/JJ/Documents/- PERSONAL PROJECTS GITHUB -/rea-md-files/` — five product folders + `INDEX.md`.  
> **Date:** 2026-11-18  
> **Method:** Full read of each product’s README, 01–09 docs, and evidence markdown (parallel deep-reads, then synthesis). Claims below are from those docs only — not invented features.

**Products covered**

| Product | Folder | What was reached in REA |
| --- | --- | --- |
| [audio2guitar.com](https://audio2guitar.com/) | `audio2guitar/` | Homepage, pricing, Google gate, one signed-in free song; on-screen tabs/chords/lyrics; Pro exports not downloaded |
| [klang.io/guitar2tabs](https://klang.io/guitar2tabs/) | `klang-guitar2tabs/` | Anonymous 30s demo → hosted editor; PDF/MIDI observed; editing gated |
| [songscription.ai](https://www.songscription.ai/mp3-to-guitar-tab-converter) | `songscription-mp3-to-guitar-tab/` | Anonymous upload → wizard → 30s score editor; downloads unlock-gated |
| [Songsterr AI](https://www.songsterr.com/new) | `songsterr-ai-tabs/` | Free account upload → 20s preview; My Tabs async; multi-track draft editor |
| [tab-gener8or](https://github.com/mgd1984/tab-gener8or) | `tab-gener8or/` | Local Streamlit/CLI source at `7526add…`; **app not run** — source-traced only |

**AudioTabs context (for recommendations):** Local/desktop Streamlit studio that already has progress checklist, Tab/Chords/Text/Piano-roll views, chord rail, stem backends, YouTube ingest, and multi-format downloads (`ANALYSIS.md`). Recommendations below prioritize gaps vs polish, not blind copies of cloud SaaS paywalls.

---

## 1. Executive verdict

Across all five products, the **winning experience pattern** is the same:

1. **Prove the destination early** (hero demo tab, public example scores, or on-page sample).
2. **Collect source with low friction** (file first; optional link / mic / photo as secondary).
3. **Ask only the musical questions that change quality** (instrument, solo vs multi, style, tuning/capo) — often in a short wizard — then start.
4. **Replace anxiety during wait** with named stages + elapsed time (and optionally tips or a micro-survey).
5. **Land in a practice-ready result shell** (notation/tab + chords + player + alternate views) before monetizing.
6. **Monetize after aha** (exports, full length, edit tools, stems) — soft banners and disabled tools beat hard walls before first result.

For AudioTabs specifically: you already own (4) and parts of (5). Biggest steal opportunities are **(1) destination proof**, **(3) pre-convert musical wizard**, **practice-player polish**, **export menu with audience subtitles**, **actionable failure classes**, and **dual original/synth (or stem) listen**.

---

## 2. Cross-product comparison matrix

### 2.1 Monetization / free taste

| Product | Auth to try | Free taste | What free gets | What is gated |
| --- | --- | --- | --- | --- |
| Audio2Guitar | Google required before upload | 3 full songs | On-screen tab + chords + lyrics + player | Edit, MIDI, PDF/print, stems, larger formats |
| Klang Guitar2Tabs | Anonymous OK | 30s demo | Editor + notation/TAB; PDF (+ observed MIDI) | Note Editor, full length ≤15 min, richer Pro exports |
| Songscription | Anonymous OK (silent auth) | Unlimited 30s jobs | Full score editor | Download bytes / account persistence |
| Songsterr AI | Account required | 20s preview per tab | Draft multi-track tab (rest-padded grid) | Full length, credits/Plus/Pro, track regen |
| Tab Gener8or | None | Everything | MIDI + tab text | N/A (local) |

**Planning takeaway:** Soft post-result gates outperform pre-result login walls for conversion *and* for learning what good UX feels like. AudioTabs (local, ungated) should copy the **taste → result → unlock depth** sequencing as *progressive disclosure of advanced features*, not as billing.

### 2.2 Input surfaces

| Input | A2G | Klang | Songscription | Songsterr | Tab Gener8or |
| --- | --- | --- | --- | --- | --- |
| Local file | ✓ (post-login) | ✓ | ✓ | ✓ | ✓ MP3 only |
| YouTube / social link | Marketing only | UI (not exercised) | UI (not exercised) | ✓ primary | — |
| Mic record | — | UI | UI | — | — |
| Photo / OMR | — | — | UI | — | — |
| Pre-submit settings | Capo/tuning on result | Full wizard | Full wizard | Rich settings panel | Theme only |

### 2.3 Result shell capabilities

| Capability | A2G | Klang | Songscription | Songsterr | Tab Gener8or |
| --- | --- | --- | --- | --- | --- |
| Graphical tab / notation | ✓ | ✓ notation+TAB | ✓ score | ✓ Songsterr viewer | ASCII only |
| ASCII / text tab | ✓ | — | — | — | ✓ |
| Chord diagrams rail | ✓ | Chord names on score | — | Chord detect | — |
| Synced lyrics | ✓ | Setting exists; not on free surface | Optional add | Vocals track | — |
| Piano roll | — | ✓ | ✓ | — | — |
| Speed / loop / metronome | ✓ | Speed + transport | Metronome + transport | Full player | — |
| Original vs synth listen | Full Audio only | ✓ Original / Synth | ✓ Transcribed / Original | Songsterr Engine + AI track switch | Preview = source only |
| Multi-track | Stems Pro | Multi mode (paid) | Multi mode (UI) | ✓ core | Track 1 only |
| Edit | Pro | Note Editor Pro | View/Edit | Full draft editor | — |
| Export menu richness | Pro menus listed | PDF/MIDI/MusicXML/LilyPond/GP5 | PDF/MusicXML/MIDI/GP + layout | MIDI / GP | MIDI + .txt |

---

## 3. Best UI elements (ranked steal list)

Each item is **concrete enough to rebuild**, tagged with best source(s). Priority is for AudioTabs studio UX.

### P0 — Highest leverage for AudioTabs

#### 3.1 Staged progress with named Done rows + elapsed + tip
- **Best sources:** Audio2Guitar (checklist: Separating stems → Detecting notes → Mapping tablature → Recognizing chords → Extracting lyrics; percent; “typically 3–6 minutes”; continues in background / email); Klang (modal: stage name e.g. “Isolating Your Instrument”, %, elapsed, estimate, tip); Songscription (processing page checklist + elapsed + optional wait survey).
- **Why:** Multi-minute ML jobs feel broken without narrative. AudioTabs already has a checklist — align labels to real pipeline stages, add elapsed/ETA, and optional tip line.
- **Avoid:** Songsterr’s “Transcribing … when it is done” with **no %** (honest but anxiety-heavy unless email + job list compensate).

#### 3.2 Practice result shell: Tab | Chords | Text + chord rail + player
- **Best source:** Audio2Guitar finished song page.
- **Controls to mirror:** Tuning / Capo / Transpose − 0 +; Accurate? Yes/No; waveform with loop tip; view switch Tab | Chords; Text view with `h`/`p`; right CHORDS diagrams; bottom player: play, speeds 0.25–1×, metronome, loop.
- **AudioTabs note:** Already close — polish player (speeds/loop/metronome), keep chord rail, ensure Text view technique glyphs match export.

#### 3.3 Pre-convert musical wizard (progressive disclosure)
- **Best sources:** Klang step rail (Mode → Instrument → Finger picking/Strumming + tuning/capo → Auto vs advanced → Title/Composer + rights); Songscription steps (Instrument → Contents one/multi/unsure → Only guitar? → Review + optional lyrics/key/time/tuning + rights).
- **Steal pattern:** 3–5 questions max; auto-advance on clear choices; review summary with Edit links; primary CTA disabled until rights/ready.
- **AudioTabs mapping:** Map wizard answers onto existing `PipelineConfig` (isolate on/off, instrument bias, capo, tuning, section detect) instead of burying everything in Advanced.

#### 3.4 Dual listen: Original vs Synth / Transcribed
- **Best sources:** Klang player (`Original Sound` | `Synth. Sound`); Songscription (`Transcribed` / `Original`, also “Score-derived” / “Raw performance”).
- **AudioTabs mapping:** Toggle between original upload (or YouTube audio) and MIDI/synth or guitar-stem playback — critical for trusting the tab.

#### 3.5 Export menu with audience subtitles + “Soon” stubs
- **Best sources:** Klang Download items (“Printable sheet music”, “For DAWs”, “For MuseScore / Dorico / Sibelius”); Songscription formats + PDF page-setup + Audio/Video **Soon** disabled.
- **Steal:** Don’t dump bare filenames — label *who it’s for*. Show unfinished formats as Soon rather than hiding roadmap.

### P1 — Strong differentiators

#### 3.6 Soft post-success upsell / depth banner (adapt as “go deeper”)
- **Sources:** A2G “SONG 1 OF 3 COMPLETE” + Not now / View plans / Upload song 2; Klang “Happy with the first 30 seconds?” + unlock list; Songscription “You’re hearing the first 30 seconds”.
- **AudioTabs adapt:** After first success, banner: “Try Guitar-FT isolation”, “Open piano roll”, “Export Guitar Pro” — feature discovery, not billing.

#### 3.7 Destination proof before commit
- **Sources:** A2G hero demo (“ROLLING STONES — START ME UP” with Tab/Chords); Songscription Example transcriptions → real editor; Songsterr three-step graphic.
- **AudioTabs adapt:** Ship 1–2 bundled demo conversions in Recent / hero that open the real result shell without running the pipeline.

#### 3.8 Multi-input converter card
- **Best source:** Songscription — Upload / Paste link / Start recording / Take a photo on one card; Klang — drop + link + Record; Songsterr — YouTube ↔ file toggle with filename chip.
- **AudioTabs:** YouTube already exists — unify file + YouTube (+ optional mic later) on one primary card with clear toggle-back.

#### 3.9 Settings-before-submit (Songsterr depth)
- Auto tempo / time-sig / anacrusis; Triplet feel; Fingerstyle arrangement; per-track instrument/tuning/capo switches.
- **Steal selectively:** Fingerstyle toggle + triplet feel + capo/tuning before run are high value; full multi-track instrument matrix is Songsterr-scale, not MVP.

#### 3.10 Play Mode vs Note Editor shell
- **Source:** Klang — header Play Mode | Note Editor | Download; left rail Sheet / Pianoroll / bars-per-line; gated editor tools disabled with Upgrade.
- **AudioTabs adapt:** Explicit **Play** vs **Inspect** modes (piano roll + part markers) without implying a full notation editor on day one.

#### 3.11 File chip + audio preview + large-file caption before Convert
- **Source:** Tab Gener8or Screen D — name + size KB, `st.audio`, “Processing large audio files may take longer”, then Convert.
- **Steal:** Confirm selection and set time expectation before committing GPU/CPU.

#### 3.12 Actionable failure classes
- **Source:** Tab Gener8or — empty/complex audio vs corrupt exception, each with next-step copy; empty path blocks bad downloads.
- **Also:** Songsterr typed errors (upload sign empty, credits quote invalid, duplicate check).
- **Steal:** Classify “no distinct notes”, “separation failed”, “YouTube blocked”, “file corrupt” with distinct recovery CTAs.

### P2 — Nice-to-have / contextual

| Element | Source | Notes |
| --- | --- | --- |
| Wait-time micro-survey | Songscription | Fun while waiting; optional analytics |
| Bars-per-line popover (1–8) | Klang | Notation density control |
| Accurate? Yes/No feedback | A2G | Cheap quality signal |
| Try Capo N suggestion | A2G | Helpful when key is awkward |
| Rest-padded free preview | Songsterr | Clever for SaaS; less relevant locally |
| Draft-first private AI framing | Songsterr | Good copy: “starting point, edit before share” |
| Education sidebar + how-it-works tooltips | Tab Gener8or | Fits Streamlit well |
| Display-only tab wrapping vs raw download | Tab Gener8or | Keep exports machine-faithful |
| Google-only auth wall with capability strip | A2G | SaaS pattern; skip for local |
| Rights checkbox before Start | Klang / Songscription | Relevant if cloud/share; optional locally |
| 30-day expiry notice | Klang | Cloud artifact hygiene |
| Difficulty / Make easier versions | Songscription | Ambitious; later |
| Professional transcription upsell | Songscription | Human fallback marketplace |

---

## 4. Functionality inventory (union of all products)

### 4.1 Intake
- Local audio: MP3 common; WAV/FLAC/M4A/OGG/AAC/etc. on paid or wider products
- Video containers (MP4/MOV/WebM) accepted by some drop zones
- YouTube / Instagram / TikTok link paste
- Microphone recording
- Photo / PDF / MusicXML OMR (Songscription)
- MIDI as input (Klang accept list; Songscription)
- Duplicate-upload detection (Songsterr)
- Silent anonymous session vs hard Google gate vs fully local

### 4.2 Pre-job musical intent
- Mode: single-instrument / multi-instrument / arrangement / fingerstyle
- Instrument: acoustic/electric/distorted guitar, bass, ukulele, double bass, full band tracks
- Style: finger picking vs strumming
- Tuning + capo
- Auto-detect vs advanced (tempo, time signature, key, quantization, triplets, sections, lyrics)
- Title / composer / artist metadata
- Rights / terms confirmation
- Quality mode marketing: Rapid vs Accurate (Songsterr — wiring unknown)

### 4.3 Processing UX
- Blocking modal with % + stage + ETA
- Full-page processing with checklist + survey
- Redirect to job list with status text + poll + email
- Artificial staged progress (Tab Gener8or 10/30/70/100)
- Background continue + email when ready

### 4.4 Result viewing
- Graphical tab / standard notation / ASCII text
- Chord symbols over lyrics + chord diagram rail
- Piano roll / pianoroll rotate
- Section labels (intro/verse)
- Waveform + custom loop region
- Multi-track mixer, solo/mute, AI track autoswitch
- Key, tempo, duration, transpose, pitch shift
- Count-in, metronome, speed presets
- Tab vs Sheet display mode
- Zoom / bars-per-line / score layout
- Empty-note states (“There are no notes to show yet”)

### 4.5 Editing & regeneration
- Edit tab / lyrics (often paid)
- Full Note Editor toolbelt (paid)
- Per-track Transcribe / Regenerate (credits)
- Retranscribe from settings drawer
- Difficulty / easier versions
- Capo / transpose non-destructive transforms

### 4.6 Export & share
- PDF / print + page setup
- MIDI (quantized + unquantized)
- MusicXML, LilyPond, Guitar Pro (GP5)
- Lyrics & chords PDF/.txt
- Stems zip (vocals/guitar/bass/drums) + stem MIDI
- Backing track / guitar-only
- Share token / private until publish
- “Soon” audio/video export stubs

### 4.7 Account / library
- Library / My Tabs / Recents / Projects
- Heart / trash / fullscreen
- Tuner (A2G free)
- Credits / Plus / Pro / one-time packs
- Cookie consent

### 4.8 Local-only (Tab Gener8or / AudioTabs-adjacent)
- Streamlit theme toggle
- CLI parity
- Self-host Docker/Procfile
- No quota

---

## 5. End-to-end workflows (canonical patterns)

### Pattern A — Soft anonymous demo (Klang / Songscription)
1. Land on marketing + converter (cookie banner optional).
2. Attach file → preparing upload indicator.
3. Wizard: instrument / mode / settings → review → rights → Start.
4. Progress UI (modal or page) with stages.
5. Open editor with 30s crop; soft banner for full unlock.
6. Explore Play / views / Download menu.
7. Gate only edit tools and/or download bytes.

**AudioTabs parallel:** Wizard → progress → studio result; “unlock” = advanced engines / exports already on disk.

### Pattern B — Auth-gated full song with soft Pro ladder (Audio2Guitar)
1. Marketing hero with live sample tab.
2. Try Free → Google wall (capability strip + free promise).
3. Upload within free limits → song page while processing (checklist + stem tease).
4. Full on-screen result + quota banner.
5. Print/Download menus list Pro items → upgrade dialog.

**Lesson:** Show Pro value *inside* the free result chrome without hiding the free deliverable.

### Pattern C — Account + short preview + job list (Songsterr)
1. `/new` dual source (YouTube | file) + Show settings.
2. Anonymous Transcribe is a dead end (anti-pattern — no visible login prompt).
3. Signed-in → 20s modal: Cancel / Transcribe preview / Upgrade.
4. Redirect My Tabs “Transcribing…”; poll; email.
5. Open private draft in full player/editor; rest-padded measures after preview window.
6. Publish only after human review.

**Lesson:** Draft-first framing + async jobs; fix anonymous dead-ends with an explicit sign-in modal.

### Pattern D — Local convert loop (Tab Gener8or)
1. Sidebar education + theme.
2. Choose MP3 → chip + preview → Convert.
3. Staged progress + nested spinners.
4. Success: dual downloads + wrapped on-screen tab.
5. Fail: class-specific recovery; no bad downloads.

**AudioTabs parallel:** Closest structural cousin — elevate education, preview, and failure copy.

### Failure paths worth designing for
| Failure | Observed / documented | UX expectation |
| --- | --- | --- |
| Fair-use / quota | A2G `FAIR_USE_LIMIT_REACHED` | Show next available / upgrade |
| Active upload conflict | A2G `409 activeUploadId` | Block double submit |
| Upload could not finish | A2G upload-failed | Retry + support path |
| Empty / complex audio | Tab Gener8or | “Try cleaner single-instrument” |
| Corrupt file | Tab Gener8or | “Different file” |
| S3 / upload sign failure | Songsterr fallback to proxy | Silent retry then error |
| Credits quote invalid | Songsterr | Reset quote + refresh |
| Duplicate song | Songsterr check-duplicate | Offer open existing |
| YouTube longer wait | Songscription copy | Set expectation on processing page |
| Anonymous submit no-op | Songsterr | **Anti-pattern** — always show next step |

---

## 6. Ideal AudioTabs workflow (synthesized)

Proposed canonical flow blending the best of all five, adapted for local desktop:

```
[Home / Studio]
  ├─ Destination proof: open bundled demo result (no wait)
  └─ Converter card
        ├─ File drop / picker  ↔  YouTube search (existing)
        └─ Optional later: mic

[File selected]
  ├─ Chip: name, size, duration
  ├─ Audio preview
  └─ Caption: large files / stems take longer

[Quick setup wizard — collapsible “Use defaults”]
  1. Content: Solo guitar | Full mix (isolate) | Not sure → isolate
  2. Style: Picking | Strumming (bias tab density)
  3. Tuning + Capo (or Detect)
  4. Review summary → Convert

[Processing]
  ├─ Named stages mapped to real pipeline callbacks
  ├─ % or indeterminate + elapsed (+ ETA if known)
  ├─ Tip of the day / “best results” line
  └─ Never a silent dead-end

[Result studio]
  ├─ Header: title, Accurate?, Tuning/Capo/Transpose
  ├─ Views: Tab | Chords | Text | Piano roll
  ├─ Chord rail
  ├─ Player: play, speed, loop, metronome, Original | Stem/Synth
  ├─ Export menu: PDF, MIDI, Tab text, Guitar stem — with subtitles
  └─ Depth banner: try better separator / open advanced / recent runs

[Failure]
  └─ Typed message + one primary recovery CTA
```

---

## 7. Per-product steal rankings (from deep-reads)

### Audio2Guitar — top 5
1. Staged progress checklist + early waveform + background/email promise  
2. Tab | Chords | Text + CHORDS rail + practice player  
3. Soft free-quota banner after success  
4. Export menus listing Pro items + inline upgrade dialog  
5. Minimal Google gate + capability strip (layout/copy only)

### Klang Guitar2Tabs — top 5
1. Step-rail upload wizard  
2. Named-stage progress modal (% + elapsed + estimate + tip)  
3. Play Mode | Note Editor | Download + Sheet/Pianoroll/bars + Original/Synth  
4. Soft paywall: UI visible, edit disabled + 30s banner with unlock list  
5. Export menu with audience subtitles  

### Songscription — top 5
1. Guided post-upload wizard with auto-advance + rights-gated Start  
2. Processing page checklist + elapsed + wait survey  
3. Anonymous full aha path; gate only export/persistence  
4. Four-input converter card + public example scores  
5. Download dialog with formats + layout + Soon stubs  

### Songsterr AI — top 5
1. Clear free-preview CTA triad + server `maxDuration`  
2. Settings-before-submit musical hints (incl. fingerstyle)  
3. Async My Tabs job row (+ email) for long jobs  
4. Dual YouTube ↔ file input on one card  
5. Draft-first private AI result in full player/editor  

### Tab Gener8or — top 5
1. Layered conversion progress (bar + status + stage spinners)  
2. Dual MIDI + tab downloads; wrap on screen only  
3. Actionable failure copy by class  
4. File chip + preview + expectation caption  
5. Persistent education sidebar + how-it-works tooltips  

---

## 8. What AudioTabs already has vs gaps

| Pattern | AudioTabs today (from ANALYSIS) | Competitor bar | Gap |
| --- | --- | --- | --- |
| Progress checklist | ✓ | A2G / Klang / Songscription | Add elapsed/ETA/tips; ensure stage names = real work |
| Tab / Chords / Text / Piano roll | ✓ | A2G + Klang/Songscription roll | Polish player speeds/loop/metronome; Original vs stem toggle |
| Chord diagrams rail | ✓ | A2G | Keep; add Accurate? / Try Capo N |
| Stem backends | ✓ strong | A2G Pro stems | Surface during progress as “isolating guitar” narrative |
| YouTube ingest | ✓ | Songsterr / others | Unify with file on one converter card |
| Downloads PDF/MIDI/tab/stem | ✓ | Rich menus elsewhere | Add subtitle labels; optional MusicXML/GP later |
| Pre-convert wizard | Advanced expander only | Klang / Songscription / Songsterr | **Major gap** |
| Destination demo | Unclear / weak | A2G / Songscription | **Major gap** |
| Typed failures | Partial | Tab Gener8or / Songsterr | Strengthen |
| Async job list + email | N/A (local sync) | Songsterr | Optional for very long jobs; Recent runs already help |
| Notation editor | No | Klang / Songsterr | Out of scope unless intentional |
| Multi-track band tab | No | Songsterr | Future / different product |

---

## 9. Recommended planning priorities (ordered)

### Phase A — Result & wait polish (highest ROI)
1. Align progress stages to pipeline; elapsed time; tip line.  
2. Practice player: speeds, loop, metronome.  
3. Original vs guitar-stem (or synth) listen toggle.  
4. Export menu labels with audience subtitles.  
5. Failure class copy + recovery CTAs.

### Phase B — Intake & intent
6. Unified converter card (file ↔ YouTube).  
7. File chip + preview + duration/size caption.  
8. Short pre-convert wizard (solo vs mix, style, tuning/capo) with “Use defaults”.  
9. Bundled demo result(s) for destination proof.

### Phase C — Depth & differentiation
10. Post-success “go deeper” banner (better separator, piano roll, exports).  
11. Accurate? feedback + Try Capo N.  
12. Bars-per-line / text wrap part markers (display-only).  
13. Education tooltips for Basic Pitch / Demucs / Guitar-FT.  
14. Explore MusicXML / Guitar Pro if engine allows.  
15. Optional mic input; optional wait tips/survey for long runs.

### Explicit non-goals (for now)
- Cloud auth / Stripe-style Pro ladders  
- Full Note Editor / MuseScore-class engraving  
- Rest-padded 20s SaaS preview mechanics  
- OMR / photo sheet music  
- Songsterr-scale multi-instrument band AI  

---

## 10. Open questions / doc unknowns (carry forward)

These are unresolved in the REA folders — do not treat as facts:

- Klang: free vs Pro MIDI gating contradicts marketing vs observed 200.  
- Songscription: `download_rights.pdf=true` vs Unlock-downloads UI.  
- Songsterr: Rapid vs Accurate request wiring; technique schema.  
- Audio2Guitar: Pro export bytes never captured; Whisper/lyric JSON shapes.  
- Tab Gener8or: never launched; `maxUploadSize` unit unknown.  
- Model names / server inference for cloud products remain black boxes.

---

## 11. Source index (where to re-read)

| Concern | Primary files |
| --- | --- |
| UI regions / controls | `*/07-ui-surface.md` + `*/evidence/captures/*` |
| Flows | `*/03-user-flows.md` |
| Feature lists | `*/02-feature-inventory.md` |
| Product positioning | `*/01-product-brief.md` |
| Pipeline timing / formats | `*/06-pipeline.md` |
| APIs / accept lists | `*/05-interfaces.md` |
| Rebuild slices | `*/08-rebuild-map.md` |
| Unknowns | `*/09-unknowns.md` |
| Folder map | `rea-md-files/INDEX.md` (note: Songscription folder exists; not listed in INDEX table) |

---

## 12. One-page “best of” checklist for design review

When reviewing any AudioTabs UI change, ask:

- [ ] Does the first screen prove the destination (demo or example)?  
- [ ] Can the user pick a source in one card without hunting?  
- [ ] Are musical choices asked *before* convert, or buried?  
- [ ] Does wait time show **named stages** + elapsed?  
- [ ] Does the result support **read + practice** (views + player + chords)?  
- [ ] Can the user A/B **original vs derived** audio?  
- [ ] Are exports labeled by audience, not just format?  
- [ ] Do failures say what happened and what to try next?  
- [ ] Is advanced depth offered *after* first success, not before?

---

*End of findings. Next step when ready: turn Phase A/B into an implementation plan under `docs/superpowers/plans/` (task-sized, TDD) or a UI-SPEC if entering a formal UI phase.*
