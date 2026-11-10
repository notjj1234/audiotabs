# audiotabs

Dedicated app for **Tab PDF**: audio (or YouTube URL) → optional guitar stem separation → MIDI → ASCII tab / PDF.

Seeded from the standalone Tab PDF app (`jj_audio_to_tab`), which was copied from the Tab PDF surface of `jj_audio_website`. Both of those stay unchanged; this repo evolves on its own.

## Requirements

- Python **3.10–3.12** (3.11 recommended; Basic Pitch needs `<3.13`)
- Optional: Demucs / RoFormer extras for full-mix guitar separation

## Setup

```bash
cd audiotabs
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -U pip
pip install -e ".[dev]"
# Optional stem separation:
pip install -e ".[demucs]"
# Optional cleaner guitar engine:
pip install -e ".[roformer,separator]"
```

Or: `make install` (includes demucs).

## Run the UI

```bash
make ui
# or: PYTHONPATH=src:. streamlit run ui/app.py
```

Upload a short solo-guitar clip (or paste a public YouTube URL), then **Convert to tab PDF**.

## CLI

```bash
audio-pipeline --audio path/to/clip.wav -o ./output --no-separate
audio-mid2tab --midi path/to/notes.mid -o ./out.tab
audio-tab2pdf --tab path/to/out.tab -o ./out.pdf
```

## Tests

```bash
make test
```

## Layout

| Path | Role |
|---|---|
| `src/audio_to_tab/` | Engine (pipeline, transcribe, tab, PDF, separation) |
| `ui/` | Streamlit Tab PDF UI |
| `tests/` | Unit tests for included modules |

## License

MIT (same family as the source package).
