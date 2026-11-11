# audiotabs

<p align="center">
  <strong>⚠️ EXTREME WORK IN PROGRESS ⚠️</strong><br>
  <span style="color:#e8a317; font-size:1.1rem;">This app is under active development. Countless bugs exist. 99.9% of features do not work. Unless you are a developer yourself, I would not waste your time here.</span>
</p>

<h1 align="center">
  <img src="assets/app-icon.png" alt="Tab PDF" width="160">
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

**Windows CPU**
```powershell
$env:AUDIO_TOOLS_EDITOR = "cpu"
.\.venv311\Scripts\python.exe packaging/launcher.py
```

**Windows GPU**
```powershell
$env:AUDIO_TOOLS_EDITOR = "cuda"
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

- **Desktop** runs on this computer: Streamlit in `ui/`, started by `packaging/launcher.py`. No Docker.
- **Website** is the hosted app: FastAPI in `backend/` plus the React app in `web/`.
- **Shared engine** lives in `src/audio_to_tab/` (import as `audio_to_tab`).

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

**Windows CPU**
```powershell
$env:AUDIO_TOOLS_EDITOR = "cpu"
.\.venv311\Scripts\python.exe packaging/launcher.py
```

**Windows GPU**
```powershell
$env:AUDIO_TOOLS_EDITOR = "cuda"
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