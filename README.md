# audiotabs

<p align="center">
  <strong>⚠️ EXTREME WORK IN PROGRESS ⚠️</strong><br>
  <span style="color:#e8a317; font-size:1.1rem;">This app is under active development. Countless bugs exist. 99.9% of features do not work. Unless you are a developer yourself, I would not waste your time here.</span>
</p>

<h1 align="center">
  <!-- Mac/UI use assets/app-icon.png (rounded). Windows desktop uses assets/app-icon.ico (square). -->
  <img src="assets/app-icon.png" alt="Tab PDF" width="160" style="border-radius: 22.37%;">
</h1>

<p align="center">
  Convert audio to guitar tab PDF (standalone Tab PDF app).
</p>

<p align="center">
  Seeded from the standalone Tab PDF app (`jj_audio_to_tab`), which was copied from the Tab PDF surface of `jj_audio_website`. Both of those stay unchanged; this repo evolves on its own.
</p>

<p align="center">
  <a href="DESKTOP.md"><img src="https://img.shields.io/badge/Desktop-🖥️-6f42c1" alt="Desktop"></a>
  <a href="DEPLOY.md"><img src="https://img.shields.io/badge/Deploy-🌐-6f42c1" alt="Deploy"></a>
  <a href="#quickstart"><img src="https://img.shields.io/badge/Quickstart-⚡-6f42c1" alt="Quickstart"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/Contribute-🤝-6f42c1" alt="Contribute"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT">
  <img src="https://img.shields.io/badge/python-3.10–3.12-blue" alt="Python 3.10–3.12">
  <img src="https://img.shields.io/badge/platform-macOS%20|%20Windows-lightgrey" alt="Platform: macOS and Windows">
</p>

---

## Quickstart

From a clone:

```bash
make install
make test
```

On Windows:

```powershell
.\scripts\dev.ps1 install
.\scripts\dev.ps1 test
```

---

## Tester

**Windows CPU** (once: `py -3.11 -m venv .venv311; .\.venv311\Scripts\python.exe -m pip install -U pip -e ".[demucs,desktop]"`)
```powershell
$env:AUDIO_TOOLS_EDITION = "cpu"
.\.venv311\Scripts\python.exe packaging/launcher.py
```

**Windows GPU** (once: `py -3.11 -m venv .venv-desktop; .\.venv-desktop\Scripts\python.exe -m pip install -U pip -e ".[demucs,desktop,roformer]"`)
```powershell
$env:AUDIO_TOOLS_EDITION = "cuda"
.\.venv-desktop\Scripts\python.exe packaging/launcher.py
```

**macOS (Apple Silicon / Intel)**
```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install --upgrade pip
pip install -e ".[demucs,desktop,roformer,separator]"

.venv311/bin/python packaging/launcher.py
```

---

## About

- **Desktop** runs on this computer: FastAPI + Svelte in `app/`, started by `packaging/launcher.py` (pywebview). No Docker.
- **Shared engine** lives in `src/audio_to_tab/` (import as `audio_to_tab`).
- Build the front end with `make ui-build` before `make desktop` if `app/web/dist` is missing.

### How a conversion runs

1. **Entry** — pick a file, YouTube link or media URL, plus settings (Advanced included).
2. **Instruments** (full mix with stem separation) — the app downloads and trims once,
   separates all six stems once, splits Lead/Rhythm guitar when that engine is selected,
   and lists every instrument with whether it was detected and how sure it is. With the
   Lead + Rhythm engine on a GPU (CUDA/MPS) and the `[roformer]` extra installed, the six
   stems come from **BS-RoFormer SW**, whose guitar stem is much cleaner than htdemucs_6s's
   (see [guitar separation eval](docs/guitar-separation-eval.md)); otherwise, or if it fails
   or the clip is too long, htdemucs_6s (guitar-ft when cached) as before. It is several
   times slower. `ATT_SPLIT_STAGE1=demucs` turns it off, `=bs_roformer_sw` forces it on CPU.
   **The BS-RoFormer SW weights (`enerjazzer/BS-ROFO-SW-Fixed`, downloaded on first use,
   never committed) state no license** — check that before any non-personal use.
   Pick the parts to tab; *Change settings* goes back with your upload intact. Solo guitar,
   separation off, or no separator installed skip this screen (the last one says why).
3. **Tab** — reuses the cached stems (nothing is separated twice). Guitar and bass become
   tab, vocals / piano / other become staff notation, drums become rough kick/snare/hi-hat
   hits. Singing that leaked into the guitar stem is removed by default on full mixes
   (*Advanced → Remove singing that leaks into guitar*).
   **Opt-in YourMT3+ note detection:** run `python -m audio_to_tab.yourmt3 setup` once
   (a separate environment, ~2 GB with weights, under `~/.cache/audio_to_tab/yourmt3`), then
   set `ATT_TRANSCRIBER=yourmt3`. It finds more correct notes than Basic Pitch on clean and
   crunch electric guitar, not on high-gain, and is slower; any failure falls back to Basic
   Pitch. Its code is GPL-3.0 and is downloaded on setup, not bundled
   ([eval](docs/guitar-separation-eval.md)).
4. **Result** — show **One part** or **Together** (stacked staves on shared bars, one
   playhead and loop; `T` toggles). The choice is saved with the run. Export the current
   part, or all shown parts as MIDI / MusicXML.

Design and plan: [spec](docs/superpowers/specs/2026-11-25-instrument-parts-design.md) ·
[plan](docs/superpowers/plans/2026-11-25-instrument-parts.md).

Python **3.11** (3.10–3.12 only). Desktop installers and the tester app: [DESKTOP.md](DESKTOP.md). Hosted deploy: [DEPLOY.md](DEPLOY.md).

## Table of contents

- [Quickstart](#quickstart)
- [Tester](#tester)
- [About](#about)

## Quickstart

From a clone:

```bash
make install
make test
```

On Windows:

```powershell
.\scripts\dev.ps1 install
.\scripts\dev.ps1 test
```

---

## Tester

**Windows CPU** (once: `py -3.11 -m venv .venv311; .\.venv311\Scripts\python.exe -m pip install -U pip -e ".[demucs,desktop]"`)
```powershell
$env:AUDIO_TOOLS_EDITION = "cpu"
.\.venv311\Scripts\python.exe packaging/launcher.py
```

**Windows GPU** (once: `py -3.11 -m venv .venv-desktop; .\.venv-desktop\Scripts\python.exe -m pip install -U pip -e ".[demucs,desktop,roformer]"`)
```powershell
$env:AUDIO_TOOLS_EDITION = "cuda"
.\.venv-desktop\Scripts\python.exe packaging/launcher.py
```

**macOS (Apple Silicon / Intel)**
```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install --upgrade pip
pip install -e ".[demucs,desktop,roformer,separator]"

.venv311/bin/python packaging/launcher.py
```