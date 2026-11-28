"""Audio transcription via Spotify Basic Pitch, or opt-in YourMT3+ (``ATT_TRANSCRIBER=yourmt3``)."""

from __future__ import annotations

import logging
import tempfile
from contextlib import suppress
from pathlib import Path

from audio_to_tab.ingest import normalize_audio
from audio_to_tab.midi_cleanup import CleanupConfig, cleanup_midi, merge_instruments_to_one
from audio_to_tab.yourmt3 import YourMT3Error, run_yourmt3, wants_yourmt3

logger = logging.getLogger(__name__)

# YourMT3 predicts no usable velocity, and ~2% of its notes are shorter than the cleanup's
# 50 ms floor; the EGDB comparison wrote notes this way before cleanup.
_YOURMT3_VELOCITY = 100
_YOURMT3_MIN_NOTE_SEC = 0.06


def _write_yourmt3_midi(audio_path: Path, dest: Path, *, allowed: bool) -> bool:
    """Raw YourMT3 notes as MIDI at ``dest``; False (Basic Pitch should run) when unavailable."""
    if not (allowed and wants_yourmt3()):
        return False
    try:
        notes = run_yourmt3(audio_path)
    except YourMT3Error as exc:
        logger.warning("YourMT3 unavailable, using Basic Pitch: %s", exc)
        return False
    import pretty_midi

    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=24)
    inst.notes = [
        pretty_midi.Note(
            _YOURMT3_VELOCITY, n["pitch"], n["start"], max(n["end"], n["start"] + _YOURMT3_MIN_NOTE_SEC)
        )
        for n in notes
    ]
    pm.instruments.append(inst)
    pm.write(str(dest))
    return True


def transcribe_audio(
    audio_path: str | Path,
    output_midi_path: str | Path,
    *,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length_ms: float = 58.0,
    cleanup: CleanupConfig | None = None,
    normalize: bool = True,
    allow_yourmt3: bool = True,
) -> Path:
    """Run Basic Pitch (or YourMT3+ when opted in) on audio and write cleaned MIDI.

    The Basic Pitch thresholds don't apply to YourMT3; ``cleanup`` applies to both.
    ``allow_yourmt3=False`` keeps Basic Pitch for audio YourMT3 wasn't measured on.
    """
    audio_path = Path(audio_path)
    output_path = Path(output_midi_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_audio = normalize_audio(audio_path) if normalize else audio_path

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = Path(tmp) / "raw.mid"
        if not _write_yourmt3_midi(work_audio, raw_path, allowed=allow_yourmt3):
            _basic_pitch_midi(
                work_audio,
                raw_path,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                minimum_note_length_ms=minimum_note_length_ms,
            )

        cleaned_tmp = Path(tmp) / "cleaned.mid"
        cleanup_midi(str(raw_path), str(cleaned_tmp), config=cleanup)

        pm = merge_instruments_to_one(__import__("pretty_midi").PrettyMIDI(str(cleaned_tmp)))
        pm.write(str(output_path))

    if normalize and work_audio != audio_path and work_audio.exists():
        with suppress(OSError):
            work_audio.unlink()

    return output_path


def _basic_pitch_midi(
    audio_path: Path,
    dest: Path,
    *,
    onset_threshold: float,
    frame_threshold: float,
    minimum_note_length_ms: float,
) -> None:
    try:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import predict
    except ModuleNotFoundError as exc:
        if exc.name in {"pkg_resources", "setuptools"}:
            raise RuntimeError(
                "Transcription needs setuptools<81 (provides pkg_resources for resampy). "
                'Reinstall with: python -m pip install "setuptools>=68,<81"'
            ) from exc
        raise

    _, midi_data, _ = predict(
        str(audio_path),
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=minimum_note_length_ms,
    )
    midi_data.write(str(dest))
