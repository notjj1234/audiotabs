# Studio UI redesign

**Status:** Approved by partner opt-out (2026-11-10): proceed with hybrid approach; accept design calls.

## Intent

Make Tab PDF look like a clean, minimal music studio — dense where it matters, quiet everywhere else — inspired by the free cores in `rea-md-files` (audio2guitar song page + Klang editor restraint), without cloning their brands, paywalls, or marketing.

## Goals

- One dark studio shell for upload, progress, and result.
- Score / tab / chords as the hero after conversion.
- Compact meta controls (tuning, capo, transpose, bars, downloads).
- Sticky-feeling bottom player with waveform.
- Advanced pipeline knobs remain available behind Advanced.
- Keep the existing Python pipeline and result helpers.

## Non-goals

- Leaving Streamlit for a separate SPA.
- Login, pricing, cookies, upgrade banners, ratings.
- Copying logos, product names, or marketing sentences from REA targets.
- Adding MusicXML / LilyPond / GP5 / Synth unless already supported.

## Anti-goals

- Another wall of Streamlit expanders as the first impression.
- Decorative cards, purple gradients, or generic AI-dashboard chrome.
- Hiding power so the UI looks “pretty” but unusable.

## Constraints

- Python `>=3.10,<3.13`. Prefer no new runtime dependency.
- Local-only processing. Existing disclaimers stay (Experimental, YouTube public-only).
- Own visual tokens only — do not import competitor palettes or logos.
- Prior result-studio plan features stay: views, chord rail, downloads, checklist, player speeds including 0.25.

## Approaches

1. Streamlit restyle only — rejected: cannot get studio chrome fidelity.
2. **Hybrid Streamlit + custom HTML/CSS shells — chosen.** Session, upload, and pipeline stay in Streamlit; visible surfaces get self-contained HTML/CSS and restyled Streamlit theme.
3. Full web UI rewrite — deferred: too large for this pass.

## Design (builder)

**Mode:** Operate.

**Visual world:** charcoal ground `#0f1115`, panel `#171a21`, hairline `#2a2f3a`, text `#e8eaef`, muted `#9aa3b2`, accent amber `#e8a317` for primary / active only. No second accent. Rounded 8–10px panels, not pill-heavy.

**Upload:** short title, one-line experimental note, drop zone + YouTube field, title/tuning/capo + separate-stem toggle inline, Advanced expander for the rest, Convert as primary amber action.

**Progress:** single checklist card with Done / Working / Waiting / Skipped states; no settings wall.

**Result:** title + meta strip; horizontal view switch (Chords / Tab / Text / Piano roll); main notation; optional right chord rail; Download popover; player under the score using the same dark tokens.

**Left to builder:** exact CSS selectors against Streamlit DOM, how much of the form stays native widgets vs HTML labels, and whether the player gets a sticky `position` inside the Streamlit main block.

## Layout decisions (2026-11-11)

- The empty screen stays a title on the charcoal ground, then one centered column: local drop zone, then YouTube search. The public-YouTube disclaimer stays in the search dialog.
- Title, tuning, capo, and stem separation appear in that column after a file or video is chosen. Pipeline knobs stay in one collapsed Advanced section.
- The entry form is not shown while a conversion is running, or on the finished song screen. New song returns to the empty screen.
- The waveform sits in the song column. Play, time, speeds (including 0.25), loop, and metronome are fixed to the bottom of the window.
- Notation, lyrics, and chord diagrams use light ink on the charcoal panel. Tab, Chords, Text, and Piano roll stay in that order.
