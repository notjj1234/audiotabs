"""Lyrics from a local Whisper-compatible transcriber, or an honest skip."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LyricLine:
    start: float
    end: float
    text: str


def _import_transcriber():
    try:
        import whisper

        return ("whisper", whisper)
    except ImportError:
        pass
    try:
        from faster_whisper import WhisperModel

        return ("faster_whisper", WhisperModel)
    except ImportError:
        return None


def lyrics_skip_reason(vocal_path: Path | None) -> str | None:
    """None when both a vocal stem and a local transcriber are available."""
    if vocal_path is None or not Path(vocal_path).is_file():
        return "Lyrics were not produced. Separation did not produce a vocal stem."
    if _import_transcriber() is None:
        return "Lyrics were not produced. No local Whisper-compatible transcriber is installed."
    return None


def _lines_from_segments(segments) -> list[LyricLine]:
    lines: list[LyricLine] = []
    for segment in segments:
        if isinstance(segment, dict):
            text = str(segment.get("text") or "").strip()
            start = segment.get("start")
            end = segment.get("end")
        else:
            text = str(getattr(segment, "text", "") or "").strip()
            start = getattr(segment, "start", None)
            end = getattr(segment, "end", None)
        if not text or start is None or end is None:
            continue
        lines.append(LyricLine(start=float(start), end=float(end), text=text))
    return lines


def transcribe_lyrics(vocal_path: Path) -> list[LyricLine]:
    """Return timestamped lines from the local model. Never invent text."""
    if lyrics_skip_reason(vocal_path) is not None:
        return []
    kind, module = _import_transcriber()
    if kind == "whisper":
        model = module.load_model("base")
        result = model.transcribe(str(vocal_path))
        return _lines_from_segments(result.get("segments") or [])
    model = module("base", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(vocal_path))
    return _lines_from_segments(segments)
