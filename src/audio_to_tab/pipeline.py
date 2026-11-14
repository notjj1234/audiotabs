"""End-to-end audio to tab PDF pipeline."""

from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from audio_to_tab.ingest import download_youtube_audio, normalize_audio
from audio_to_tab.isolate import analyze_guitar_stem_quality
from audio_to_tab.lyrics import lyrics_skip_reason, transcribe_lyrics
from audio_to_tab.midi_cleanup import (
    CleanupConfig,
    cleanup_midi,
    mix_aware_cleanup_config,
    solo_guitar_cleanup_config,
)
from audio_to_tab.separate import separate_guitar_stem
from audio_to_tab.tab_bundle import (
    audio_duration_seconds,
    bundle_chords,
    key_for_midi,
    tab_document_for,
    write_tab_exports,
)
from audio_to_tab.tempo import resolve_tempo
from audio_to_tab.transcribe import transcribe_audio

logger = logging.getLogger(__name__)

YOUTUBE_DISCLAIMER = (
    "FYI: public YouTube links only. No Private or Unlisted YouTube links"
)

DEMUCS_INSTALL_HINT = (
    "Demucs is required for stem separation. Install with: make install-demucs "
    "or pip install -e \".[demucs]\""
)


MIN_USABLE_TAB_NOTES = 3

EMPTY_TRANSCRIPTION_MESSAGE = (
    "Too few notes detected for a usable tab. "
    "A cleaner solo-guitar clip is needed. "
    "Next: try the Solo / fingerstyle preset, turn off mix-aware filtering, "
    "lower the onset threshold in Expert options, or use a shorter clean section."
)


class EmptyTranscriptionError(RuntimeError):
    """Raised when transcription has fewer than MIN_USABLE_TAB_NOTES notes."""


@dataclass
class PipelineConfig:
    separate_stems: bool = True
    demucs_quality: str = "balanced"
    demucs_device: str = "cpu"
    model: str = "auto"
    guitar_checkpoint: str | None = None
    guitar_refine: bool = False
    demucs_segment: int | None = 8
    demucs_jobs: int = 1
    fold_other_mode: str | None = None
    low_end_restore_db: float = 0.0
    sub_bass_debleed: bool = False
    bleed_gate: bool = False
    adaptive_fold_gain: bool = False
    guitar_ensemble: bool = False
    mix_aware_filtering: bool = True
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    minimum_note_length_ms: float = 58.0
    min_velocity: int = 40
    min_duration_sec: float = 0.05
    quantize_sec: float | None = 0.05
    max_notes_per_onset: int = 6
    max_duration_sec: float | None = None
    title: str = "Guitar Tab"
    tempo_bpm_override: float | None = None
    beats_per_measure: int = 4
    tuning_name: str = "Standard (EADGBE)"
    capo: int = 0
    transpose: int = 0
    bars_per_line: int = 4
    beat_model: str = "beat_this"
    auto_meter: bool = True
    fingering_preference: str = "playable"
    export_gp5: bool = False

    def __post_init__(self) -> None:
        if self.demucs_quality not in ("fast", "balanced", "best"):
            raise ValueError(f"Invalid demucs_quality: {self.demucs_quality!r}")
        if self.beats_per_measure <= 0:
            raise ValueError(f"beats_per_measure must be positive, got {self.beats_per_measure}")
        if self.beat_model not in ("beat_this", "librosa"):
            raise ValueError(f"Invalid beat_model: {self.beat_model!r}")
        if self.fingering_preference not in ("playable", "low_fret", "position"):
            raise ValueError(
                f"Invalid fingering_preference: {self.fingering_preference!r}"
            )
        if not (0.0 <= self.onset_threshold <= 1.0):
            raise ValueError(f"onset_threshold must be 0..1, got {self.onset_threshold}")
        if not (0.0 <= self.frame_threshold <= 1.0):
            raise ValueError(f"frame_threshold must be 0..1, got {self.frame_threshold}")
        from audio_to_tab.tuning import TUNING_PRESETS

        if self.tuning_name not in TUNING_PRESETS:
            raise ValueError(f"Unknown tuning: {self.tuning_name!r}")
        if not 0 <= int(self.capo) <= 12:
            raise ValueError(f"capo must be 0..12, got {self.capo}")
        if not -12 <= int(self.transpose) <= 12:
            raise ValueError(f"transpose must be -12..12, got {self.transpose}")
        if not 1 <= int(self.bars_per_line) <= 8:
            raise ValueError(f"bars_per_line must be 1..8, got {self.bars_per_line}")


ProgressCallback = Callable[[str, str], None]  # stage, message


def _noop_progress(stage: str, message: str) -> None:
    pass


def resolve_guitar_model(model: str, duration_sec: float) -> str:
    """Select the guitar specialist only when its runtime and duration guard pass."""
    if model != "auto":
        return model
    from audio_to_tab.hardware import get_desktop_probe, roformer_max_audio_sec
    from audio_to_tab.roformer import MELBAND_GUITAR_ID, is_guitar_refine_available

    probe = get_desktop_probe()
    if (
        is_guitar_refine_available()
        and duration_sec > 0
        and duration_sec <= roformer_max_audio_sec(probe)
    ):
        return MELBAND_GUITAR_ID
    return "htdemucs_6s"


def _separate_progress_label(cfg: PipelineConfig) -> str:
    model = (cfg.model or "htdemucs_6s").lower()
    if model in {"bs_roformer_sw", "melband_roformer_guitar"}:
        return "Isolating guitar stem with BS-RoFormer"
    if model in {"guitar_scnet"}:
        return "Isolating guitar stem with SCNet"
    if cfg.guitar_checkpoint:
        return "Isolating guitar stem with guitar-ft Demucs"
    return "Isolating guitar stem"


def _trim_audio(input_path: Path, max_duration_sec: float | None) -> Path:
    if max_duration_sec is None or max_duration_sec <= 0:
        return input_path
    import subprocess

    from audio_to_tab.subprocess_util import subprocess_run_kwargs

    out = input_path.parent / f"{input_path.stem}_trim.wav"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg not found; returning un-trimmed audio")
        return input_path
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(input_path), "-t", str(max_duration_sec), str(out)],
        capture_output=True,
        check=False,
        **subprocess_run_kwargs(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed: {result.stderr or result.stdout}")
    return out


def _apply_mix_aware_floors(cfg: PipelineConfig) -> bool:
    """Strict floors only for separated full mixes (not solo paths)."""
    return bool(cfg.mix_aware_filtering and cfg.separate_stems)


def _cleanup_config_for_pipeline(cfg: PipelineConfig) -> CleanupConfig:
    use_mix = _apply_mix_aware_floors(cfg)
    base = mix_aware_cleanup_config() if use_mix else solo_guitar_cleanup_config()
    return CleanupConfig(
        min_velocity=cfg.min_velocity if not use_mix else max(cfg.min_velocity, base.min_velocity),
        min_duration_sec=(
            cfg.min_duration_sec if not use_mix else max(cfg.min_duration_sec, base.min_duration_sec)
        ),
        quantize_sec=cfg.quantize_sec,
        max_notes_per_onset=cfg.max_notes_per_onset,
    )


def _transcription_thresholds(cfg: PipelineConfig) -> tuple[float, float, float]:
    onset = cfg.onset_threshold
    frame = cfg.frame_threshold
    min_len = cfg.minimum_note_length_ms
    if _apply_mix_aware_floors(cfg):
        onset = max(onset, 0.58)
        frame = max(frame, 0.40)
        min_len = max(min_len, 90.0)
    return onset, frame, min_len


def count_midi_notes(midi_path: Path) -> int:
    """Total note events across all instruments in a MIDI file."""
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    return sum(len(inst.notes) for inst in pm.instruments)


def _require_usable_transcription(midi_path: Path) -> None:
    if count_midi_notes(midi_path) < MIN_USABLE_TAB_NOTES:
        raise EmptyTranscriptionError(EMPTY_TRANSCRIPTION_MESSAGE)


def run_pipeline(
    *,
    audio_path: Path | None = None,
    youtube_url: str | None = None,
    output_dir: Path,
    config: PipelineConfig | None = None,
    on_progress: ProgressCallback | None = None,
    include_tab_source: bool = False,
) -> dict[str, Path]:
    """
    Run full pipeline: ingest → [separate] → transcribe → tab → PDF.

    Returns paths to midi, tab txt, and pdf artifacts. When ``include_tab_source``
    is true, also returns the unquantized MIDI used to build the tab as ``tab_midi``.
    """
    cfg = config or PipelineConfig()
    progress = on_progress or _noop_progress
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # --- Ingest ---
        progress("ingest", "Loading audio")
        if youtube_url:
            progress("ingest", YOUTUBE_DISCLAIMER)
            raw_audio = download_youtube_audio(youtube_url, tmp_path)
        elif audio_path:
            raw_audio = normalize_audio(audio_path, tmp_path / "normalized.wav")
        else:
            raise ValueError("Provide audio_path or youtube_url")

        work_audio = _trim_audio(raw_audio, cfg.max_duration_sec)
        playback_path = output_dir / "playback.wav"
        shutil.copy2(work_audio, playback_path)
        duration_sec = audio_duration_seconds(playback_path)

        # --- Separate (optional) ---
        transcribe_input = work_audio
        tempo_audio_source = work_audio
        if cfg.separate_stems:
            separation_model = resolve_guitar_model(cfg.model, duration_sec)
            progress("separate", "Separating stems")
            stem_path = output_dir / "guitar_stem.wav"
            try:
                recovery_diag_path = (
                    output_dir / "low_end_recovery_diagnostics.json"
                    if cfg.sub_bass_debleed or cfg.low_end_restore_db
                    else None
                )
                separate_guitar_stem(
                    work_audio,
                    stem_path,
                    model=separation_model,
                    device=cfg.demucs_device,
                    quality=cfg.demucs_quality,
                    demucs_segment=cfg.demucs_segment,
                    demucs_jobs=cfg.demucs_jobs,
                    guitar_refine=cfg.guitar_refine,
                    guitar_checkpoint=cfg.guitar_checkpoint,
                    fold_other_mode=cfg.fold_other_mode,
                    sub_bass_debleed=cfg.sub_bass_debleed,
                    low_end_restore_db=cfg.low_end_restore_db,
                    bleed_gate=cfg.bleed_gate,
                    adaptive_fold_gain=cfg.adaptive_fold_gain,
                    guitar_ensemble=cfg.guitar_ensemble,
                    recovery_diagnostics_path=recovery_diag_path,
                    bleed_gate_diagnostics_path=(
                        output_dir / "bleed_gate_diagnostics.json"
                        if cfg.bleed_gate
                        else None
                    ),
                    vocal_output=output_dir / "vocals.wav",
                )
                quality_diag = analyze_guitar_stem_quality(stem_path)
                quality_diag.write_json(output_dir / "guitar_stem_quality.json")
                transcribe_input = stem_path
                tempo_audio_source = stem_path
            except (RuntimeError, FileNotFoundError) as exc:
                raise RuntimeError(
                    f"Guitar stem separation failed: {exc}. "
                    f"For solo guitar, disable separation. {DEMUCS_INSTALL_HINT}"
                ) from exc
        else:
            progress("separate", "skipped: Separation is off")

        # --- Transcribe ---
        progress("transcribe", "Detecting notes")
        midi_path = output_dir / "transcription.mid"
        tab_midi_path = tmp_path / "transcription_unquantized.mid"
        onset_th, frame_th, min_len_ms = _transcription_thresholds(cfg)
        cleanup_cfg = _cleanup_config_for_pipeline(cfg)
        transcribe_audio(
            transcribe_input,
            tab_midi_path,
            onset_threshold=onset_th,
            frame_threshold=frame_th,
            minimum_note_length_ms=min_len_ms,
            cleanup=replace(cleanup_cfg, quantize_sec=None),
            normalize=False,
        )
        cleanup_midi(str(tab_midi_path), str(midi_path), config=cleanup_cfg)
        _require_usable_transcription(midi_path)
        tab_source_path = None
        if include_tab_source:
            tab_source_path = output_dir / "transcription_unquantized.mid"
            shutil.copy2(tab_midi_path, tab_source_path)

        tempo_est = resolve_tempo(
            audio_path=tempo_audio_source,
            midi_path=midi_path,
            override_bpm=cfg.tempo_bpm_override,
            beat_model=cfg.beat_model,
        )

        beats_per_measure = cfg.beats_per_measure
        if cfg.auto_meter and tempo_est.downbeats:
            beats_per_measure = tempo_est.beats_per_measure

        quantization_beats = tempo_est.beats if cfg.tempo_bpm_override is None else ()
        progress("tab", "Mapping tablature")
        tab_doc = tab_document_for(
            tab_midi_path,
            tempo_bpm=tempo_est.bpm,
            tempo_confidence=tempo_est.confidence,
            beats_per_measure=beats_per_measure,
            tuning_name=cfg.tuning_name,
            capo=cfg.capo,
            transpose=cfg.transpose,
            beats=quantization_beats,
            fingering_preference=cfg.fingering_preference,
        )

        progress("chords", "Recognizing chords")
        chord_hits = bundle_chords(
            midi_path,
            transpose=cfg.transpose,
            capo=cfg.capo,
            tuning_name=cfg.tuning_name,
        )
        song_key = key_for_midi(midi_path, transpose=cfg.transpose, capo=cfg.capo)

        vocal_path = output_dir / "vocals.wav"
        vocal_file = vocal_path if vocal_path.is_file() else None
        lyric_lines: list = []
        lyrics_reason = lyrics_skip_reason(vocal_file)
        if lyrics_reason:
            progress("lyrics", f"skipped: {lyrics_reason}")
            lyrics_status = lyrics_reason
        else:
            try:
                lyric_lines = transcribe_lyrics(vocal_file)  # type: ignore[arg-type]
            except Exception as exc:
                logger.warning("Lyrics transcription failed: %s", exc)
                lyric_lines = []
                lyrics_reason = "Lyrics were not produced. The local transcriber failed."
            if lyrics_reason or not lyric_lines:
                lyrics_status = lyrics_reason or (
                    "Lyrics were not produced. The transcriber returned no text."
                )
                progress("lyrics", f"skipped: {lyrics_status}")
            else:
                lyrics_status = ""
                progress("lyrics", "Extracting lyrics")

        progress("pdf", "Finalizing PDF")
        written = write_tab_exports(
            tab_doc,
            output_dir,
            title=cfg.title,
            capo=cfg.capo,
            transpose=cfg.transpose,
            bars_per_line=cfg.bars_per_line,
            chords=chord_hits,
            key=song_key,
            duration_sec=duration_sec,
            tempo_bpm=tempo_est.bpm,
            tempo_confidence=tempo_est.confidence,
            tuning_name=cfg.tuning_name,
            lyrics=lyric_lines,
            lyrics_status=lyrics_status,
            beats_per_measure=beats_per_measure,
            beats=quantization_beats,
            downbeats=tempo_est.downbeats,
            anacrusis_sec=tempo_est.anacrusis_sec,
            fingering_preference=cfg.fingering_preference,
            export_gp5=cfg.export_gp5,
        )

        progress("done", "Pipeline complete")

        artifacts: dict[str, Path] = {
            "midi": midi_path,
            "tab": written["tab"],
            "pdf": written["pdf"],
            "result": written["result"],
            "playback": playback_path,
        }
        if "gp5" in written:
            artifacts["gp5"] = written["gp5"]
        if tab_source_path is not None:
            artifacts["tab_midi"] = tab_source_path
        if cfg.separate_stems and (output_dir / "guitar_stem.wav").exists():
            artifacts["guitar_stem"] = output_dir / "guitar_stem.wav"

        return artifacts
