# Tab rhythm visibility — design

**Intent:** Make the Result Tab pane readable on navy chrome, and show Songsterr-style rhythm (fret digit as notehead with stem/beam/flag).

**Goals:** High-contrast staff; whole–16th (+ dotted); keep Satoshi / navy / orange.

**Non-goals:** Multi-track editor; separate standard-notation staff; PDF/MusicXML/GP5 redesign; rest glyphs in v1.

**Approach:** Dark-theme SVG ink (`#f4f7fb` / `#8fa0b5`) plus rhythm layer derived from `TabEvent` start/end and tempo. One stem per event; beam ≤8th same-subdivision groups within a beat.

**Reference:** `rea-md-files/songsterr-ai-tabs/` beat `{duration, type, beamStart, beamStop}`.
