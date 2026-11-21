# Tab PDF — UI/UX and Visual Audit

**Date:** 2026-11-18
**Scope:** the entire desktop surface (`ui/`), shown through `packaging/launcher.py` (1280×860 default, 960×640 minimum)
**Method:** dual-agent design review + deterministic detector + live browser measurement at 1280×860 and 390×844
**Evidence:** `.superpowers/ui-audit/` (screenshots), `impeccable detect --json` (CLI + live URL)

---

## 1. The short version

The engine and the practice surface are good. The interface around them is not.

- The app is **Streamlit 1.67** and the computed font is literally `"Source Sans", sans-serif` — Streamlit's default, not a chosen typeface.
- The custom look is **1,101 lines of CSS overriding Streamlit internals**, with **15 font sizes, 8 font weights, and 5 radii**. There is no type scale and no font file in the repo.
- The tab — the product — begins **~820–900 px down the result screen**, is stretched **~3.4×** its natural size (a 228 px SVG blown up to ~790 px), has **no bar lines**, and prints its measure number below the staff where it reads as a fret.
- The result screen asks **"Accurate?" before the tab is visible**, then repeats three actions as a bullet list and again as three buttons.
- One CSS rule hides **every widget label inside the conversion card**, so the Quick setup and every Advanced control render nameless.
- The entry screen never says what the app makes. "Tab PDF" is a file extension, and the one non-form action ("Try sample tab") floats outside the centred card.

**Design Health Score: 22/40 (Acceptable, 55%).** No P0s — the core path completes. This is under-designed, not broken.

---

## 2. Design-specificity verdict

**A bespoke notation engine wearing Streamlit's default clothes.**

Generic tells:

- Stock Source Sans, no font-family token except monospace.
- Stock `st.audio` player on the intake screen (the grey bar with the three-dot menu).
- Stock BaseWeb select/radio/number-input chrome; `st.warning` / `st.info` boxes only recoloured.
- A structure any audio→file converter could use unchanged: centred card, upload/YouTube/URL, presets, Convert, recent list.

Authored tells:

- One deliberate palette (`#0f1115` / `#171a21` / `#e8a317`) used consistently.
- The three 88 px source tiles are a real reusable component with matching icon discs and hover/focus states.
- Weighted progress checklist with named domain stages, elapsed time, and stage tips; properly announced to assistive tech.
- Custom waveform player: drag-to-loop, 0.25–1× speeds, metronome from detected BPM, keyboard-seekable waveform.
- Hand-drawn tab staff, piano roll, chord diagrams, and a playhead synced to the audio.

Verdict: **partially authored (5.5/10)**. The identity lives in the artifact and the player, behind generic chrome — and the artifact is the worst-rendered thing on screen.

Detector: CLI scan returns `[]` because all HTML is emitted from Python; a sanity fixture confirms the detector works. Live URL scan at both widths returns **one true positive**: `nested-cards` on the file dropzone (`section[data-testid=stFileUploaderDropzone]` has the same background, border, and 10 px radius as its parent card). Everything else is clean.

---

## 3. Heuristic scores

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Strong weighted progress; result says "Playing the original audio" with no player; demo runs are not marked as demo |
| 2 | Match system / real world | 2 | Right vocabulary (capo, EADGBE, bars), but no bar lines and a stray measure number below the staff |
| 3 | User control and freedom | 2 | No cancel during conversion; no undo/reset except "Use defaults"; no note correction |
| 4 | Consistency and standards | 2 | Two visual worlds (640 px card vs 1180 px studio); same fields labelled in result, label-hidden in entry; two section-heading styles |
| 5 | Error prevention | 3 | Good guardrails (ffmpeg gate, full-track confirm, delete confirm); "Try stem separation" silently changes the next run |
| 6 | Recognition rather than recall | 2 | Advanced controls have no visible labels; sliders show bare `90` and `0.00` |
| 7 | Flexibility and efficiency | 2 | Practice player is excellent; zero keyboard shortcuts; no batch; no edit |
| 8 | Aesthetic and minimalist design | 2 | Entry ~55% empty; ~700 px of chrome before the tab; duplicated action list |
| 9 | Error recovery | 2 | Empty/failed states are dead ends ("No chords recognized", "MIDI for this run is gone") |
| 10 | Help and documentation | 2 | Good hover tooltips, but internals leak (Demucs, onset/frame threshold) and nothing explains the product |
| **Total** | | **22/40** | **Acceptable — significant improvement needed** |

Contrast is **not** a problem: muted `#9aa3b2` is 6.84:1 on panel and 7.43:1 on background; 52 sampled text nodes passed their WCAG thresholds. The legibility problem is size and placement.

---

## 4. Cognitive load

**7 of 8 checks fail → high load, critical fix needed.**

| Check | Result |
|---|---|
| Single focus | Fail — "Try sample tab" floats in dead space; intake shows chip + duplicate name + player + caution + 9 controls |
| Chunking (≤4 per group) | Fail — Advanced stacks 8 ungrouped controls |
| Grouping | Fail — "Length" and "Separation" are captions, not containers; a warning sits between a label and its slider |
| Visual hierarchy | Fail — the tab starts below the fold |
| One thing at a time | Fail — result asks for 6 decisions at once |
| Minimal choices | Fail — 13 affordances on result, 8 in Advanced |
| Working memory | Fail — a slider reads `90` with no unit or name; another reads `0.00` with no referent |
| Progressive disclosure | Pass — Advanced is collapsed by default; undermined by hidden labels |

---

## 5. What works

1. **The progress checklist is better than most shipping converters.** Weighted percentage from real stage weights, named stages, elapsed time, a teaching tip, `role="progressbar"` with `aria-valuenow`.
2. **The source tiles are a genuine component.** One 88 px shape with matching 2.5rem icon discs, title/subtitle hierarchy, hover and focus-within states, reused for all three sources.
3. **The practice player is the differentiator.** Drag-to-loop waveform, speed presets, metronome from detected BPM, pinned transport, keyboard seek — exactly what a guitarist needs to learn a part. The hand-drawn staff/roll/diagrams with a synced playhead are the right call over a charting dependency.

---

## 6. Priority issues

### [P1] Every label inside the entry card is hidden by one CSS rule

`.st-key-tab_source_entry [data-testid="stWidgetLabel"]` at `ui/studio_theme.py:119` clips **all** widget labels in the card. Quick setup becomes `sample-song` / `Standard` / `None` with no names. Advanced becomes a bare `90`, a bare `0.00`, an unnamed toggle, and two unlabeled checkboxes, one clipped by the card edge.

**Why it matters:** Advanced is unusable. A user who opens it to trim an intro cannot know that `0.00` is seconds, what its range is, or what it changes. Screen readers still get the names, so only sighted users are punished.

**Fix:** scope the rule to the segmented control and file uploader, or use `label_visibility="collapsed"` on just those two. Give every other field a visible label and group Length/Separation under real sub-headings.

### [P1] The tab is buried, then rendered wrong

(a) Order: header → four sentences of caveats → `Accurate?` → Go deeper → three buttons → Playback → Tab settings → Score view → **score below the fold**.
(b) Rendering: `tab_staff_svg` produces a 228 px-wide viewBox for a one-measure clip; `.studio-score-sync .studio-score-img { width: 100% }` (`src/audio_to_tab/notation_view.py:310`) stretches it to ~790 px. No vertical bar lines are drawn. Measure numbers are placed at `top + 78` in the same ink as frets, below the staff.

**Why it matters:** The product is the tab. A guitarist orients by bar lines; their absence makes correct output look non-functional. A 3.4× blow-up says "something broke," not "this clip is short."

**Fix:** score and view switch directly under the title; `Accurate?` after the score; collapse caveats into one "How to check this" disclosure. Cap the score at natural scale, draw bar lines, move measure numbers above the staff in muted 10 px.

### [P1] Three "go deeper" buttons that don't do what they say

`Try stem separation` sets a flag and tells you to start over. `Export Guitar Pro` prints "Guitar Pro 5 is in the Downloads menu" instead of downloading. The banner above lists the same three actions as bullets and then repeats them as buttons.

**Fix:** one row, three real actions. Queue and start the re-run, or label it "Re-run with stem separation". Make GP5 a direct download. Delete the bullet list.

### [P2] Entry never says what it makes; its best activation control is orphaned

The entire promise is the wordmark "Tab PDF". `Try sample tab` is a bare top-level button, so it left-aligns at x≈130 while the hero and card are centred. After a file is chosen, the hero margin is re-injected and the segmented control is clipped by the card's top border.

**Fix:** one subline — what goes in, what comes out, how long it takes. Move the sample action inside the card as a quiet third option. Remove the margin re-injection.

### [P2] Machine output is shown as user copy

- `4537.1 KB Duration about 4:50.` — raw KB, no separator, stray period; `format_size_kb` never switches to MB.
- `Playing the original audio. ran without stem separation — install Demucs…` — lowercase sentence after a join.
- `Onset threshold —, frame threshold —.` — dangling em dashes when values are absent.
- `MusicXML — Soon (for MuseScore / Dorico)` inside a menu of actionable items.
- File name appears twice; the uploader's own chip says 4.6 MB while the caption says 4537.1 KB.
- Empty states have no cause and no action.

**Fix:** one size formatter; real sentence joins; hide technical metadata unless Expert is on; move "Soon" out of the action menu; give every empty state a cause + one action.

### [P2] Target sizes, headings, and state

- 32 px buttons; 10/11 entry controls and 22/23 result controls are under 44 px in at least one dimension.
- No `<h1>` on any screen; result has exactly one heading (`h2`). Section labels are paragraphs.
- The tab is an `<img alt="Guitar tab">`; the only accessible rendering is the third view, Text.
- Score seeking is mouse-only, while the waveform is keyboard-seekable.
- Streamlit's invisible "Link to heading" anchor (16×16) is present on the result title.
- Server-side warning on Reopen: `widget with key "tab_result_transpose" was created with a default value but also had its value set via the Session State API`.

---

## 7. Persona red flags

**Alex (power user):** no keyboard shortcut for anything; `Use defaults` is the same size and directly above `Convert`, so a double-click resets then converts; no batch; no note editing despite "check every note"; no cancel during a 3-minute stem run.

**Jordan (first-timer):** "Tab PDF" means nothing; `Standard` / `None` have no labels; "Solo / fingerstyle vs Full mix" assumes stem knowledge that lives only in a hover tooltip; "Stay in position" doesn't say where; `Accurate?` before the tab; after "Try stem separation" they are told to start over, which reads as losing their upload.

**Sam (accessibility):** zero h1s, one h2, no heading structure for sections; tab is an image with a generic alt; score seeking is mouse-only; fixed-height tiles with injected `::before/::after` text can clip at 200% zoom; 11.5 px uppercase section labels at 6.63:1 are small on a laptop panel.

---

## 8. Minor observations

- `--studio-border` is used at `studio_theme.py:629` but never defined; the Go deeper banner silently loses its border.
- `.st-key-tab_source_entry` is declared twice (36 rem, then 40 rem); the second wins, so the "one column" comment is stale.
- The "full-width segmented switcher" CSS no longer matches Streamlit 1.67's DOM, so the control renders ~270 px inside a 640 px card.
- The upload dropzone is left-aligned with a 22 px left / 63 px right gap.
- Result header uses `st.columns([6, 1])`, so `Download` aligns to a fraction of the window, not the 1180 px content column.
- `Accurate?` label and its Yes/No buttons have no shared alignment contract; the label sits ~8 px higher.
- Playback claims to play audio while `_render_player` returns early when no playback file exists.
- Recent rows are not clickable; three affordances (checkbox, Delete, Reopen) for a list of 1–3 items.
- Progress is 640 px wide, result is 1180 px — a third layout width in one flow.
- A refresh mid-flow loses all in-progress state; only completed runs persist.

---

## 9. Why restyling Streamlit has a ceiling

Streamlit is a data-app renderer, not an app framework. The current surface already fights it:

- 1,101 lines of CSS keyed to `data-testid` and `.st-key-*`, which change between Streamlit releases.
- Widget labels hidden globally to make one control look right.
- The stock file uploader, audio player, select popovers, toasts, spinners, and sidebar remain Streamlit-shaped.
- Page state is a rerun loop; there is no cancel, no async job model, no client-side routing.
- Typography cannot be fully controlled because Streamlit injects its own font stack and sizes.

You can get a *better* Streamlit app. You cannot get a *designed* desktop app out of it without continuing to override internals.

---

## 10. Exit options

| Option | What it means | Effort | Ceiling |
|---|---|---|---|
| **A. Restyle Streamlit in place** | Load a real font, fix the label bug, reorder result, tame chrome | S (2–4 days) | Medium-low. Stock widgets and rerun model remain; CSS breaks on upgrades |
| **B. Custom front end, same Python engine** | FastAPI job API + React/Svelte UI in pywebview; SSE progress; custom player | L (2–3 weeks for parity) | High. Full type/layout/state control, no Streamlit |
| **C. Python-native desktop UI** | PySide6 (true native, L) or NiceGUI (web tech, all-Python, M) | M–L | Medium-high. No build step for NiceGUI; its component defaults still need a theme |

**Recommendation:** **B** if this is going to be a product. The engine is already Python, the shell is already pywebview, and everything the design needs — typography, layout, a real transport, async progress — is web-native. Keep A only as a stopgap if a release is imminent.

---

## 11. Target information architecture (proposal)

**Entry:** app bar (brand, Transcribe/Library) → one promise line → one card with three source modes, a labelled dropzone, a quiet "Try a sample" link, labelled Quick setup in two groups, one summary line ("First 90 s · no stem separation — change"), one primary Convert → Recent as a compact list with a real row action.

**Waiting:** the same card replaced by a stage list, elapsed time, one tip, and **Cancel**. No form remnants.

**Result:** title + key/tempo/duration + Export in a single app bar → **score first**, at natural scale, with bar lines → view switch → pinned transport (play, speeds, loop, metronome, Original/Stem) → right inspector for Tuning/Capo/Transpose/Bars → "How was this?" feedback after the score → a single "Go deeper" link, not a banner plus buttons.

**Visual system:** six type sizes (12/13/15/18/24/34), two weights (450/620), 4 px spacing base, three radii (6/10/14), one accent (brass `#e8a317`) reserved for active state and the primary action, body line length ≤68 ch, 120 ms state transitions. Suggested open-source pairing: Instrument Sans (UI), Instrument Serif (song title/brand), JetBrains Mono (tab text) — subject to approval.

---

## 12. Open decisions

1. Exit route: A, B, or C.
2. Does the result lead with the tab + transport, or with settings?
3. Keep the brass-on-charcoal identity, or replace the visual world?
4. First pass scope: labels + order only, full visual overhaul, or overhaul + migration.
