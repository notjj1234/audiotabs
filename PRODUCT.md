# Tab PDF — Product

Tab PDF is a desktop app that turns a recording into guitar tab. Drop an audio
file, paste a YouTube link, or give it a media URL; in about 90 seconds you get
tablature, chord diagrams, and a practice player — running entirely on your own
machine.

**Spec:** [docs/superpowers/specs/2026-11-18-ui-redesign-design.md](docs/superpowers/specs/2026-11-18-ui-redesign-design.md)

## What it is

- A guitarist's learning tool, not a notation editor. The engine transcribes
  audio to MIDI and renders tab; the practice player (waveform, loops, speeds,
  metronome) is the differentiator.
- A local desktop app. Processing happens on the user's machine; there are no
  accounts, no telemetry, no cloud. The window is owned by pywebview and the UI
  is a local FastAPI + web front end.
- One product surface: entry, waiting, result, and library share one shell, one
  type system, and one accent.
- Guitar first, every part available: after Convert the app shows which instruments
  are in the song. Guitar (Lead / Rhythm / Combined) and bass become tab; vocals,
  piano/keys and other become staff notation; drums become rough kick/snare/hi-hat
  hits. The result shows one part or several together on shared bars.
  ([instrument parts spec](docs/superpowers/specs/2026-11-25-instrument-parts-design.md))

## Who it serves

- **The learner (Jordan):** heard a song, wants to play it. Needs the app to say
  what it makes, to label every field, and to never make "go deeper" sound like
  losing their upload.
- **The power user (Alex):** learns parts by loop. Needs keyboard shortcuts,
  cancel that works, and exports that are real files.
- **The accessibility-first user (Sam):** navigates by headings, keyboard, and
  contrast. Needs one `h1` per screen, keyboard-operable score seeking, and
  200%-zoom-safe layouts.

## The promise

> Turn a recording into guitar tab.

Everything on screen is in service of that sentence: the tab is the first thing
on the result screen, at natural scale, with bar lines and measure numbers
where a guitarist expects them.

## Success metrics

Measured on the audit's own rubric ([docs/ui-audit/2026-11-18-ui-ux-audit.md](docs/ui-audit/2026-11-18-ui-ux-audit.md), §1):

| Metric | Baseline (2026-11-18) | Target |
|---|---|---|
| Design Health Score | 22/40 | ≥ 32/40 |
| Tab on the result screen | ~820–900 px down, ~3.4× upscaled | First row + playhead row above the fold at 1280×860, never scaled past 1× |
| Hidden labels | Every entry-card label hidden by one CSS rule | Zero hidden labels |
| Interactive targets under 44 px | 10/11 entry, 22/23 result | Zero |
| UI font families | Streamlit default stack | One (Instrument Sans) |
| Accent colours | one, kept | one, kept (`#e8a317`; the built token `--accent` in `app.css` is `#F6AD49` — always use the token) |

Behavioural success: cancel between stages ends `cancelled` with no partial
folder; every export downloads a real file rebuilt from the inspector settings;
a run with zero usable notes shows a cause and one action; a legacy run still
opens its score.

## Anti-goals

- Fake depth actions. "Re-run with stem separation" starts a real job; Guitar
  Pro downloads directly.
- Machine output as copy. File sizes read `4.6 MB`, never `4537.1 KB`; no raw
  exception ever reaches the user.
- Hiding labels to make a control "look clean".
- A second accent, glow, gradient text, or glass panels.
- Decorative cards, stat dashboards, or empty hero space.
- Accounts, sync, telemetry, cloud processing.
- Mobile layout below the 960 px window minimum; a light theme or theme switch.
- Frozen/packaged installers — the exit check is `make desktop` from source.
