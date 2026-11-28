"""End-to-end audio to tab PDF pipeline."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from audio_to_tab import lead_rhythm_sep, lead_rhythm_tab, musicxml_export
from audio_to_tab.cancel import CancelToken
from audio_to_tab.ingest import download_youtube_audio, normalize_audio
from audio_to_tab.isolate import analyze_guitar_stem_quality
from audio_to_tab.lyrics import lyrics_skip_reason, transcribe_lyrics
from audio_to_tab.midi_cleanup import (
    CleanupConfig,
    cleanup_midi,
    mix_aware_cleanup_config,
    solo_guitar_cleanup_config,
)
from audio_to_tab.separate import (
    GUITAR_FT_CHECKPOINT_ID,
    postprocess_guitar_stem,
    separate_guitar_stem,
)
from audio_to_tab.tab_bundle import (
    audio_duration_seconds,
    bundle_chords,
    key_for_midi,
    tab_document_for,
    write_tab_exports,
)
from audio_to_tab.tempo import resolve_tempo
from audio_to_tab.transcribe import transcribe_audio
from audio_to_tab.yourmt3 import abort_scope as yourmt3_abort_scope

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
    # Opt-in lead/rhythm mode: guitar-ft pre-pass (or already-isolated input)
    # → Mel-Band RoFormer Lead/Rhythm split → per-stem transcription + tabs.
    # Also set when ``model == "lead_rhythm_split"``.
    lead_rhythm_split: bool = False
    # Drop guitar notes that are the singer bleeding into the guitar stem:
    # "auto" = on for separated full mixes with a vocals stem; "on" / "off".
    vocal_debleed: str = "auto"

    def __post_init__(self) -> None:
        if self.model == lead_rhythm_sep.LEAD_RHYTHM_SPLIT_ID:
            self.lead_rhythm_split = True
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


ProgressCallback = Callable[..., None]  # stage, message, optional fraction


def _noop_progress(stage: str, message: str, fraction: float | None = None) -> None:
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


@dataclass(frozen=True)
class StemFloors:
    """Minimum transcription settings for one Lead/Rhythm part on separated input."""

    onset: float
    frame: float
    min_note_ms: float
    min_velocity: int
    min_duration_sec: float


# Chosen on the GuitarSet comp+solo harness (scripts/eval_lead_rhythm.py). The general
# separated-input floors (frame 0.40, velocity 55, 80 ms) cut rhythm recall more than they
# gained precision; the lead keeps the strict velocity/duration cleanup, which suits its
# one-note-at-a-time path.
LEAD_STEM_FLOORS = StemFloors(onset=0.58, frame=0.30, min_note_ms=90.0, min_velocity=55, min_duration_sec=0.08)
RHYTHM_STEM_FLOORS = StemFloors(onset=0.58, frame=0.30, min_note_ms=90.0, min_velocity=40, min_duration_sec=0.05)


def _part_transcription_settings(
    cfg: PipelineConfig, floors: StemFloors
) -> tuple[float, float, float, CleanupConfig]:
    """(onset, frame, min note ms, cleanup) for one Lead/Rhythm part; floors only on separated input."""
    onset, frame, min_len = cfg.onset_threshold, cfg.frame_threshold, cfg.minimum_note_length_ms
    cleanup = _cleanup_config_for_pipeline(cfg)
    if not _apply_mix_aware_floors(cfg):
        return onset, frame, min_len, cleanup
    return (
        max(onset, floors.onset),
        max(frame, floors.frame),
        max(min_len, floors.min_note_ms),
        replace(
            cleanup,
            min_velocity=max(cfg.min_velocity, floors.min_velocity),
            min_duration_sec=max(cfg.min_duration_sec, floors.min_duration_sec),
        ),
    )


def count_midi_notes(midi_path: Path) -> int:
    """Total note events across all instruments in a MIDI file."""
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    return sum(len(inst.notes) for inst in pm.instruments)


def _require_usable_transcription(midi_path: Path) -> None:
    if count_midi_notes(midi_path) < MIN_USABLE_TAB_NOTES:
        raise EmptyTranscriptionError(EMPTY_TRANSCRIPTION_MESSAGE)


def _run_guitar_pipeline(
    *,
    audio_path: Path | None = None,
    youtube_url: str | None = None,
    output_dir: Path,
    config: PipelineConfig | None = None,
    on_progress: ProgressCallback | None = None,
    include_tab_source: bool = False,
    cancel: CancelToken | None = None,
    analysis: Any = None,
) -> dict[str, Path]:
    """
    Run full pipeline: ingest → [separate] → transcribe → tab → PDF.

    Returns paths to midi, tab txt, and pdf artifacts. When ``include_tab_source``
    is true, also returns the unquantized MIDI used to build the tab as ``tab_midi``.
    """
    cfg = config or PipelineConfig()
    base_progress = on_progress or _noop_progress

    def progress(stage: str, message: str, fraction: float | None = None) -> None:
        if cancel is not None:
            cancel.check()
        if fraction is None:
            base_progress(stage, message)
        else:
            base_progress(stage, message, fraction)

    should_abort = cancel.is_cancelled if cancel is not None else None
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # --- Ingest ---
        if analysis is not None:
            # The analysis already downloaded, normalised and trimmed the audio.
            progress("ingest", "Reusing the audio from the instrument check", 1.0)
            work_audio = Path(analysis.work_audio)
        else:
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
        if analysis is not None:
            progress("separate", "Reusing the separated instruments", 0.5)
            stem_path = output_dir / "guitar_stem.wav"
            postprocess_guitar_stem(
                analysis.stems,
                stem_path,
                model=analysis.model,
                device=cfg.demucs_device,
                guitar_refine=cfg.guitar_refine,
                fold_other_mode=cfg.fold_other_mode,
                bleed_gate=cfg.bleed_gate,
                sub_bass_debleed=cfg.sub_bass_debleed,
                low_end_restore_db=cfg.low_end_restore_db,
                adaptive_fold_gain=cfg.adaptive_fold_gain,
                recovery_diagnostics_path=(
                    output_dir / "low_end_recovery_diagnostics.json"
                    if cfg.sub_bass_debleed or cfg.low_end_restore_db
                    else None
                ),
                bleed_gate_diagnostics_path=(
                    output_dir / "bleed_gate_diagnostics.json" if cfg.bleed_gate else None
                ),
            )
            vocals = analysis.stems.get("vocals")
            if vocals is not None and Path(vocals).is_file():
                shutil.copy2(vocals, output_dir / "vocals.wav")
            quality_diag = analyze_guitar_stem_quality(stem_path)
            quality_diag.write_json(output_dir / "guitar_stem_quality.json")
            transcribe_input = stem_path
            tempo_audio_source = stem_path
            progress("separate", "Instruments reused", 1.0)
        elif cfg.separate_stems and cfg.lead_rhythm_split:
            # Lead/Rhythm pre-pass: reuse the guitar-ft path so the split
            # model receives a single clean guitar stem. Quality flows into
            # the existing QUALITY_SHIFTS / QUALITY_OVERLAP map.
            progress("separate", "Isolating guitar stem with guitar-ft Demucs", 0.05)
            stem_path = output_dir / "guitar_stem.wav"
            pre_pass_checkpoint = cfg.guitar_checkpoint or GUITAR_FT_CHECKPOINT_ID

            def _pre_pass_progress(message: str, fraction: float) -> None:
                progress("separate", message or "Isolating guitar stem", fraction)

            try:
                separate_guitar_stem(
                    work_audio,
                    stem_path,
                    **({"should_abort": should_abort} if should_abort else {}),
                    model="htdemucs_6s",
                    device=cfg.demucs_device,
                    quality=cfg.demucs_quality,
                    demucs_segment=cfg.demucs_segment,
                    demucs_jobs=cfg.demucs_jobs,
                    guitar_checkpoint=pre_pass_checkpoint,
                    on_progress=_pre_pass_progress,
                )
            except (RuntimeError, FileNotFoundError) as exc:
                raise RuntimeError(
                    f"Guitar stem separation failed: {exc}. "
                    f"For solo guitar, disable separation. {DEMUCS_INSTALL_HINT}"
                ) from exc
            quality_diag = analyze_guitar_stem_quality(stem_path)
            quality_diag.write_json(output_dir / "guitar_stem_quality.json")
            transcribe_input = stem_path
            tempo_audio_source = stem_path
        elif cfg.separate_stems:
            separation_model = resolve_guitar_model(cfg.model, duration_sec)
            separate_label = _separate_progress_label(
                replace(cfg, model=separation_model)
            )
            progress("separate", separate_label, 0.05)
            stem_path = output_dir / "guitar_stem.wav"
            try:
                recovery_diag_path = (
                    output_dir / "low_end_recovery_diagnostics.json"
                    if cfg.sub_bass_debleed or cfg.low_end_restore_db
                    else None
                )

                def _separate_progress(message: str, fraction: float) -> None:
                    progress("separate", message or separate_label, fraction)

                separate_guitar_stem(
                    work_audio,
                    stem_path,
                    **({"should_abort": should_abort} if should_abort else {}),
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
                    on_progress=_separate_progress,
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
            if cfg.lead_rhythm_split:
                # Input is already an isolated guitar file: skip the pre-pass.
                stem_path = output_dir / "guitar_stem.wav"
                shutil.copy2(work_audio, stem_path)
                transcribe_input = stem_path
                tempo_audio_source = stem_path
            progress("separate", "skipped: Separation is off")

        lead_rhythm_fallback_reason: str | None = None
        if cfg.lead_rhythm_split:
            try:
                return _run_lead_rhythm_stage(
                    cfg=cfg,
                    transcribe_input=transcribe_input,
                    tempo_audio_source=tempo_audio_source,
                    output_dir=output_dir,
                    tmp_path=tmp_path,
                    progress=progress,
                    duration_sec=duration_sec,
                    playback_path=playback_path,
                    split_paths=(analysis.lead_rhythm_paths if analysis is not None else None),
                    write_grid=analysis is not None,
                    analysis=analysis,
                )
            except lead_rhythm_sep.LeadRhythmSplitError as exc:
                lead_rhythm_fallback_reason = str(exc)
                logger.warning(
                    "Lead/rhythm split failed; falling back to single guitar tab: %s",
                    exc,
                )
                progress(
                    "separate",
                    "Lead/rhythm split failed; falling back to single guitar tab",
                    0.25,
                )

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
        debleed = _VocalDebleed.setup(cfg, output_dir, analysis)
        if debleed.enabled:
            progress("transcribe", "Removing singing that leaked into the guitar")
            _filter_midi_file(tab_midi_path, lambda notes: debleed.apply("combined", notes, transcribe_input))
        debleed_path = debleed.write(output_dir)
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
        grid_path = (
            write_grid_json(output_dir, tempo_est, beats_per_measure)
            if analysis is not None
            else None
        )
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
        if grid_path is not None:
            artifacts["grid"] = grid_path
        if debleed_path is not None:
            artifacts["vocal_debleed_diagnostics"] = debleed_path
        if cfg.separate_stems and (output_dir / "guitar_stem.wav").exists():
            artifacts["guitar_stem"] = output_dir / "guitar_stem.wav"
        if lead_rhythm_fallback_reason is not None:
            fallback_path = output_dir / "lead_rhythm_fallback.json"
            fallback_path.write_text(
                json.dumps(
                    {"fallback": True, "reason": lead_rhythm_fallback_reason},
                    indent=2,
                ),
                encoding="utf-8",
            )
            artifacts["lead_rhythm_fallback"] = fallback_path

        return artifacts


def _stem_payload(tx) -> dict:
    return {
        "notes": [
            {
                "pitch": n.pitch,
                "start": n.start,
                "end": n.end,
                "velocity": n.velocity,
                "confidence": n.confidence,
            }
            for n in tx.notes
        ],
        "techniques": [
            {
                "kind": m.kind,
                "start": m.start,
                "end": m.end,
                "confidence": m.confidence,
                "evidence": m.evidence,
            }
            for m in tx.techniques
        ],
        "low_confidence_regions": [list(r) for r in tx.low_confidence_regions],
    }


def _apply_role_check(
    lead_tx,
    rhythm_tx,
    *,
    downbeats,
    beats,
    tempo_bpm: float,
    beats_per_measure: int,
    output_dir: Path,
    warnings: list[str],
):
    """Move bars the audio split misfiled, rebuild technique hints, write the role report."""
    from audio_to_tab import guitar_roles

    lead_notes, rhythm_notes, report = guitar_roles.assign_roles(
        lead_tx.notes,
        rhythm_tx.notes,
        downbeats=tuple(downbeats or ()),
        beats=tuple(beats or ()),
        tempo_bpm=tempo_bpm,
        beats_per_measure=beats_per_measure,
        lead_chords=getattr(lead_tx, "chord_attacks", ()),
    )
    # The lead path stays one note at a time, as its transcription is.
    lead_notes = lead_rhythm_tab._lead_monophonic(lead_notes)
    kept_lead = {(round(n.start, 3), n.pitch) for n in lead_notes}
    report.notes = [
        d for d in report.notes if d["role"] != "lead" or (d["start"], d["pitch"]) in kept_lead
    ]
    roles_path = output_dir / "lead_rhythm_roles.json"
    roles_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    if report.moves or report.bleed_removed or report.chords_to_rhythm:
        warnings.append(
            f"Role check gave {report.chords_to_rhythm} chord(s) from the lead stem to rhythm, "
            f"moved {len(report.moves)} bar(s) between lead and rhythm and removed "
            f"{report.bleed_removed} lead note(s) heard again in the rhythm stem."
        )
    if lead_notes == lead_tx.notes and rhythm_notes == rhythm_tx.notes:
        return lead_tx, rhythm_tx, roles_path
    lead_tx = replace(
        lead_tx,
        notes=lead_notes,
        techniques=lead_rhythm_tab.technique_marks_for("lead", lead_notes),
    )
    rhythm_tx = replace(
        rhythm_tx,
        notes=rhythm_notes,
        techniques=lead_rhythm_tab.technique_marks_for("rhythm", rhythm_notes),
    )
    return lead_tx, rhythm_tx, roles_path


def _analysis_vocal_suppression(analysis: Any) -> dict | None:
    """What the analysis did to the splitter's input, from its saved split diagnostics."""
    saved = Path(analysis.dir) / "lead_rhythm_split_diagnostics.json" if analysis is not None else None
    if saved is None or not saved.is_file():
        return None
    try:
        return json.loads(saved.read_text(encoding="utf-8")).get("vocal_suppression")
    except (OSError, ValueError) as exc:
        logger.warning("Could not read the analysis split diagnostics at %s: %s", saved, exc)
        return None


def _run_lead_rhythm_stage(
    *,
    cfg: PipelineConfig,
    transcribe_input: Path,
    tempo_audio_source: Path,
    output_dir: Path,
    tmp_path: Path,
    progress: ProgressCallback,
    duration_sec: float,
    playback_path: Path,
    split_paths: dict[str, Path] | None = None,
    write_grid: bool = False,
    analysis: Any = None,
) -> dict[str, Path]:
    """Lead/rhythm mode: split → per-stem transcription → per-stem tab/export."""
    if split_paths:
        # The analysis already ran the split; reuse its stems.
        progress("separate", "Reusing the lead and rhythm split", 0.9)
        stems = {"lead_guitar": split_paths["lead"], "rhythm_guitar": split_paths["rhythm"]}
        split_diag = lead_rhythm_sep.analyze_lead_rhythm_stems(
            Path(stems["lead_guitar"]), Path(stems["rhythm_guitar"]), input_path=transcribe_input
        )
        split_diag.vocal_suppression = _analysis_vocal_suppression(analysis)
    else:
        from audio_to_tab.vocal_debleed import guitar_for_split

        progress("separate", "Splitting lead and rhythm guitars", 0.2)
        # The splitter files singing as Lead: it gets the guitar stem without the vocal copy.
        split_input, suppression = guitar_for_split(
            cfg, transcribe_input, output_dir / "vocals.wav", tmp_path / "guitar_for_split.wav"
        )
        try:
            stems, split_diag = lead_rhythm_sep.run_lead_rhythm_split(
                split_input,
                tmp_path / "lead_rhythm_split",
                device=cfg.demucs_device,
                on_progress=lambda message, fraction: progress("separate", message, fraction),
            )
        except lead_rhythm_sep.LeadRhythmSplitError:
            raise
        except Exception as exc:
            raise lead_rhythm_sep.LeadRhythmSplitError(
                f"Lead/rhythm split failed: {exc}"
            ) from exc
        split_diag.vocal_suppression = suppression
    lead_stem = output_dir / "lead_guitar.wav"
    rhythm_stem = output_dir / "rhythm_guitar.wav"
    shutil.copy2(stems["lead_guitar"], lead_stem)
    shutil.copy2(stems["rhythm_guitar"], rhythm_stem)
    diag_path = split_diag.write_json(output_dir / "lead_rhythm_split_diagnostics.json")

    progress("transcribe", "Detecting notes (lead + rhythm)")
    onset_th, frame_th, min_len_ms, cleanup_cfg = _part_transcription_settings(cfg, LEAD_STEM_FLOORS)
    lead_tx = lead_rhythm_tab.transcribe_lead_stem(
        lead_stem,
        tmp_path / "lead_transcription.mid",
        onset_threshold=onset_th,
        frame_threshold=frame_th,
        minimum_note_length_ms=min_len_ms,
        cleanup=cleanup_cfg,
    )
    # Rhythm notes come from the combined guitar stem: the rhythm stem is a residual with
    # subtraction holes and smear. The split only decides which of those notes the lead owns.
    onset_th, frame_th, min_len_ms, cleanup_cfg = _part_transcription_settings(cfg, RHYTHM_STEM_FLOORS)
    rhythm_tx = lead_rhythm_tab.transcribe_rhythm_stem(
        transcribe_input,
        tmp_path / "rhythm_transcription.mid",
        onset_threshold=onset_th,
        frame_threshold=frame_th,
        minimum_note_length_ms=min_len_ms,
        cleanup=cleanup_cfg,
    )
    rhythm_notes, lead_owned = lead_rhythm_tab.drop_lead_owned(
        rhythm_tx.notes, lead_tx.notes, lead_stem, rhythm_stem
    )
    rhythm_tx = replace(
        rhythm_tx,
        notes=rhythm_notes,
        techniques=lead_rhythm_tab.technique_marks_for("rhythm", rhythm_notes, audio_path=transcribe_input),
    )
    debleed = _VocalDebleed.setup(cfg, output_dir, analysis)
    if debleed.enabled:
        progress("transcribe", "Removing singing that leaked into the guitars")
        lead_tx = replace(lead_tx, notes=debleed.apply("lead", list(lead_tx.notes), lead_stem))
        rhythm_tx = replace(
            rhythm_tx, notes=debleed.apply("rhythm", list(rhythm_tx.notes), transcribe_input)
        )
    debleed_path = debleed.write(output_dir)

    warnings: list[str] = []
    if not lead_tx.notes:
        warnings.append("Lead stem transcription is empty; low-confidence regions were kept empty.")
    if not rhythm_tx.notes:
        warnings.append("Rhythm stem transcription is empty; low-confidence regions were kept empty.")
    if not lead_tx.notes and not rhythm_tx.notes:
        raise EmptyTranscriptionError(EMPTY_TRANSCRIPTION_MESSAGE)

    midis = lead_rhythm_tab.write_stem_midis(lead_tx, rhythm_tx, output_dir)

    tempo_est = resolve_tempo(
        audio_path=tempo_audio_source,
        midi_path=midis["stems_midi"],
        override_bpm=cfg.tempo_bpm_override,
        beat_model=cfg.beat_model,
    )
    beats_per_measure = cfg.beats_per_measure
    if cfg.auto_meter and tempo_est.downbeats:
        beats_per_measure = tempo_est.beats_per_measure
    quantization_beats = tempo_est.beats if cfg.tempo_bpm_override is None else ()
    grid_path = write_grid_json(output_dir, tempo_est, beats_per_measure) if write_grid else None

    # The audio split decides roles by sound; re-check them bar by bar from texture.
    progress("tab", "Checking lead and rhythm roles bar by bar")
    lead_tx, rhythm_tx, roles_path = _apply_role_check(
        lead_tx,
        rhythm_tx,
        downbeats=tempo_est.downbeats,
        beats=tempo_est.beats,
        tempo_bpm=tempo_est.bpm,
        beats_per_measure=beats_per_measure,
        output_dir=output_dir,
        warnings=warnings,
    )
    midis = lead_rhythm_tab.write_stem_midis(lead_tx, rhythm_tx, output_dir)
    notes_path = output_dir / "lead_rhythm_notes.json"
    notes_path.write_text(
        json.dumps(
            {
                "lead": _stem_payload(lead_tx),
                "rhythm": _stem_payload(rhythm_tx),
                "rhythm_source": {
                    "audio": "combined guitar stem",
                    "lead_owned_left_out": lead_owned,
                    "lead_owned_share": lead_rhythm_tab.LEAD_OWNED_SHARE,
                },
                "warnings": warnings,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    progress("tab", "Mapping tablature (lead + rhythm)")
    doc_kwargs = {
        "tempo_bpm": tempo_est.bpm,
        "tempo_confidence": tempo_est.confidence,
        "beats_per_measure": beats_per_measure,
        "tuning_name": cfg.tuning_name,
        "capo": cfg.capo,
        "transpose": cfg.transpose,
        "beats": quantization_beats,
        "fingering_preference": cfg.fingering_preference,
    }
    lead_doc = tab_document_for(midis["lead_midi"], **doc_kwargs)
    rhythm_doc = tab_document_for(midis["rhythm_midi"], **doc_kwargs)
    from audio_to_tab.chords import sounding_semitones as _sounding_semitones
    from audio_to_tab.tuning import tuning_preset as _tuning_preset

    opens, _tuning_names = _tuning_preset(cfg.tuning_name)
    capo_opens = tuple(min(127, note + int(cfg.capo)) for note in opens)
    display_shift = _sounding_semitones(transpose=cfg.transpose, capo=cfg.capo)
    voicing_map = lead_rhythm_tab._canonical_voicing_map(
        lead_rhythm_tab._rhythm_chord_events(rhythm_tx.notes),
        tuning=capo_opens,
        semitones=display_shift,
    )
    rhythm_doc = lead_rhythm_tab.apply_canonical_voicings(
        rhythm_doc, voicing_map, tuning=capo_opens
    )
    combined_doc = tab_document_for(midis["stems_midi"], **doc_kwargs)

    progress("chords", "Recognizing chords")
    chord_hits = bundle_chords(
        midis["stems_midi"],
        transpose=cfg.transpose,
        capo=cfg.capo,
        tuning_name=cfg.tuning_name,
    )
    song_key = key_for_midi(midis["stems_midi"], transpose=cfg.transpose, capo=cfg.capo)

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
        lyrics_status = lyrics_reason or (
            "Lyrics were not produced. The transcriber returned no text."
        )
        if lyric_lines:
            progress("lyrics", "Extracting lyrics")
            lyrics_status = lyrics_status or ""

    progress("pdf", "Finalizing PDF + MusicXML")
    export_kwargs = {
        "capo": cfg.capo,
        "transpose": cfg.transpose,
        "bars_per_line": cfg.bars_per_line,
        "duration_sec": duration_sec,
        "tempo_bpm": tempo_est.bpm,
        "tempo_confidence": tempo_est.confidence,
        "tuning_name": cfg.tuning_name,
        "lyrics": lyric_lines,
        "lyrics_status": lyrics_status,
        "beats_per_measure": beats_per_measure,
        "beats": quantization_beats,
        "downbeats": tempo_est.downbeats,
        "anacrusis_sec": tempo_est.anacrusis_sec,
        "fingering_preference": cfg.fingering_preference,
        "export_gp5": cfg.export_gp5,
    }
    lead_written = write_tab_exports(
        lead_doc,
        output_dir / "lead",
        title=f"{cfg.title} (Lead)",
        chords=[],
        key=song_key,
        **export_kwargs,
    )
    rhythm_written = write_tab_exports(
        rhythm_doc,
        output_dir / "rhythm",
        title=f"{cfg.title} (Rhythm)",
        chords=chord_hits,
        key=song_key,
        **export_kwargs,
    )
    combined_written = write_tab_exports(
        combined_doc,
        output_dir,
        title=cfg.title,
        chords=chord_hits,
        key=song_key,
        **export_kwargs,
    )
    musicxml_path = musicxml_export.write_musicxml(
        [("Lead", lead_doc), ("Rhythm", rhythm_doc)],
        output_dir / "transcription.musicxml",
        title=cfg.title,
        tempo_bpm=tempo_est.bpm,
    )

    progress("done", "Pipeline complete")
    artifacts: dict[str, Path] = {
        "midi": midis["stems_midi"],
        "tab": combined_written["tab"],
        "pdf": combined_written["pdf"],
        "result": combined_written["result"],
        "playback": playback_path,
        "guitar_stem": output_dir / "guitar_stem.wav",
        "lead_guitar": lead_stem,
        "rhythm_guitar": rhythm_stem,
        "lead_rhythm_split_diagnostics": diag_path,
        "lead_rhythm_notes": notes_path,
        "lead_rhythm_roles": roles_path,
        "lead_midi": midis["lead_midi"],
        "rhythm_midi": midis["rhythm_midi"],
        "stems_midi": midis["stems_midi"],
        "musicxml": musicxml_path,
        "lead_tab": lead_written["tab"],
        "lead_pdf": lead_written["pdf"],
        "lead_result": lead_written["result"],
        "rhythm_tab": rhythm_written["tab"],
        "rhythm_pdf": rhythm_written["pdf"],
        "rhythm_result": rhythm_written["result"],
    }
    if grid_path is not None:
        artifacts["grid"] = grid_path
    if debleed_path is not None:
        artifacts["vocal_debleed_diagnostics"] = debleed_path
    if "gp5" in combined_written:
        artifacts["gp5"] = combined_written["gp5"]
    if "gp5" in lead_written:
        artifacts["lead_gp5"] = lead_written["gp5"]
    if "gp5" in rhythm_written:
        artifacts["rhythm_gp5"] = rhythm_written["gp5"]
    return artifacts


GUITAR_PARTS = ("lead", "rhythm", "combined")
KNOWN_PARTS = (*GUITAR_PARTS, "bass", "vocals", "keys", "drums", "other")
# Inventory part id → analysis stem name.
PART_STEMS = {"bass": "bass", "vocals": "vocals", "keys": "piano", "drums": "drums", "other": "other"}


def write_grid_json(output_dir: Path, tempo_est: Any, beats_per_measure: int) -> Path:
    """One run-level beat grid shared by every part so Together mode lines up."""
    path = Path(output_dir) / "grid.json"
    path.write_text(
        json.dumps(
            {
                "bpm": float(tempo_est.bpm),
                "confidence": str(getattr(tempo_est, "confidence", "")),
                "beats_per_measure": int(beats_per_measure),
                "beats": [float(b) for b in (getattr(tempo_est, "beats", ()) or ())],
                "downbeats": [float(b) for b in (getattr(tempo_est, "downbeats", ()) or ())],
                "anacrusis_sec": float(getattr(tempo_est, "anacrusis_sec", 0.0) or 0.0),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _select_parts(analysis: Any, parts: list[str] | None) -> list[str]:
    if parts is None:
        parts = [row.id for row in analysis.inventory if row.default_selected]
    selected = list(dict.fromkeys(parts))
    unknown = [p for p in selected if p not in KNOWN_PARTS]
    if unknown:
        raise ValueError(f"Unknown part: {unknown[0]}")
    if not selected:
        raise ValueError("Choose at least one part to tab.")
    return selected


def run_pipeline(
    *,
    audio_path: Path | None = None,
    youtube_url: str | None = None,
    output_dir: Path,
    config: PipelineConfig | None = None,
    on_progress: ProgressCallback | None = None,
    include_tab_source: bool = False,
    cancel: CancelToken | None = None,
    analysis: Any = None,
    parts: list[str] | None = None,
) -> dict[str, Path]:
    """
    Run full pipeline: ingest → [separate] → transcribe → tab → PDF.

    Returns paths to midi, tab txt, and pdf artifacts. When ``include_tab_source``
    is true, also returns the unquantized MIDI used to build the tab as ``tab_midi``.

    With ``analysis`` (an ``AnalysisBundle``) the cached audio and stems are
    reused — nothing is downloaded or separated again — and only ``parts`` are
    tabbed. A ``parts.json`` artifact lists the parts the result shows.
    """
    with yourmt3_abort_scope(cancel.is_cancelled if cancel is not None else None):
        return _run_pipeline(
            audio_path=audio_path,
            youtube_url=youtube_url,
            output_dir=output_dir,
            config=config,
            on_progress=on_progress,
            include_tab_source=include_tab_source,
            cancel=cancel,
            analysis=analysis,
            parts=parts,
        )


def _run_pipeline(
    *,
    audio_path: Path | None,
    youtube_url: str | None,
    output_dir: Path,
    config: PipelineConfig | None,
    on_progress: ProgressCallback | None,
    include_tab_source: bool,
    cancel: CancelToken | None,
    analysis: Any,
    parts: list[str] | None,
) -> dict[str, Path]:
    if analysis is None:
        return _run_guitar_pipeline(
            audio_path=audio_path,
            youtube_url=youtube_url,
            output_dir=output_dir,
            config=config,
            on_progress=on_progress,
            include_tab_source=include_tab_source,
            cancel=cancel,
        )
    cfg = config or PipelineConfig()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = _select_parts(analysis, parts)
    guitar = [p for p in selected if p in GUITAR_PARTS]
    others = [p for p in selected if p not in GUITAR_PARTS]
    base_progress = on_progress or _noop_progress

    def progress(stage: str, message: str, fraction: float | None = None) -> None:
        if cancel is not None:
            cancel.check()
        if fraction is None:
            base_progress(stage, message)
        else:
            base_progress(stage, message, fraction)

    # Non-guitar parts first: the guitar core finishes with the "done" event.
    from audio_to_tab.part_transcribe import transcribe_part

    artifacts: dict[str, Path] = {}
    empty: dict[str, str] = {}
    labels = {row.id: row.label for row in analysis.inventory}
    for index, part in enumerate(others):
        stem = analysis.stems.get(PART_STEMS[part])
        progress(
            "transcribe",
            f"Detecting notes: {labels.get(part, part)}",
            index / max(1, len(others) + (1 if guitar else 0)),
        )
        if stem is None or not Path(stem).is_file():
            empty[part] = "This instrument's stem is missing."
            continue
        res = transcribe_part(part, Path(stem), output_dir / "parts", cfg=cfg)
        artifacts[f"{part}_midi"] = res.midi
        artifacts[f"{part}_result"] = res.result
        if res.empty_reason:
            empty[part] = res.empty_reason

    if guitar:
        use_split = bool(analysis.lead_rhythm.ok) and any(p in ("lead", "rhythm") for p in guitar)
        run_cfg = replace(
            cfg,
            separate_stems=True,
            lead_rhythm_split=use_split,
            model=cfg.model if use_split else "htdemucs_6s",
        )
        try:
            artifacts.update(
                _run_guitar_pipeline(
                    output_dir=output_dir,
                    config=run_cfg,
                    on_progress=on_progress,
                    include_tab_source=include_tab_source,
                    cancel=cancel,
                    analysis=analysis,
                )
            )
        except EmptyTranscriptionError:
            # Other parts have notes: keep them and report the guitar as empty.
            if not any(key.endswith("_result") for key in artifacts):
                raise
            from audio_to_tab.part_transcribe import EMPTY_PART_REASON

            for part in guitar:
                empty[part] = EMPTY_PART_REASON
            use_split = False
            artifacts.update(_no_guitar_frame(analysis, output_dir, cfg, artifacts, progress))
    else:
        use_split = False
        artifacts.update(_no_guitar_frame(analysis, output_dir, cfg, artifacts, progress))

    fallback = Path(analysis.dir) / "lead_rhythm_fallback.json"
    if not use_split and "combined" in guitar and fallback.is_file():
        dest = output_dir / "lead_rhythm_fallback.json"
        shutil.copy2(fallback, dest)
        artifacts["lead_rhythm_fallback"] = dest

    stems_dir = output_dir / "stems"
    stems_dir.mkdir(exist_ok=True)
    for name, path in analysis.stems.items():
        if name == "guitar" or not Path(path).is_file():
            continue
        dest = stems_dir / f"{name}.wav"
        shutil.copy2(path, dest)
        artifacts[f"{name}_stem"] = dest

    parts_path = output_dir / "parts.json"
    parts_path.write_text(
        json.dumps({"parts": selected, "empty": empty}, indent=2), encoding="utf-8"
    )
    artifacts["parts"] = parts_path
    return artifacts


def _no_guitar_frame(
    analysis: Any,
    output_dir: Path,
    cfg: PipelineConfig,
    part_artifacts: dict[str, Path],
    progress: ProgressCallback,
) -> dict[str, Path]:
    """Playback, beat grid and a minimal result.json for runs with no guitar part."""
    playback = output_dir / "playback.wav"
    shutil.copy2(analysis.work_audio, playback)
    progress("tab", "Building the shared beat grid")
    midi_for_tempo = next(
        (path for key, path in part_artifacts.items() if key.endswith("_midi")), None
    )
    tempo_est = resolve_tempo(
        audio_path=playback,
        midi_path=midi_for_tempo or playback,
        override_bpm=cfg.tempo_bpm_override,
        beat_model=cfg.beat_model,
    )
    beats_per_measure = cfg.beats_per_measure
    if cfg.auto_meter and tempo_est.downbeats:
        beats_per_measure = tempo_est.beats_per_measure
    grid = write_grid_json(output_dir, tempo_est, beats_per_measure)
    result = output_dir / "result.json"
    result.write_text(
        json.dumps(
            {
                "title": cfg.title,
                "key": "",
                "tempo_bpm": float(tempo_est.bpm),
                "tempo_confidence": str(getattr(tempo_est, "confidence", "")),
                "duration_sec": audio_duration_seconds(playback),
                "tuning_name": cfg.tuning_name,
                "capo": 0,
                "transpose": cfg.transpose,
                "bars_per_line": cfg.bars_per_line,
                "beats_per_measure": beats_per_measure,
                "beats": list(getattr(tempo_est, "beats", ()) or ()),
                "downbeats": list(getattr(tempo_est, "downbeats", ()) or ()),
                "chords": [],
                "lyrics": [],
                "lyrics_status": "",
                "events": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    progress("done", "Pipeline complete")
    return {"playback": playback, "grid": grid, "result": result}


class _VocalDebleed:
    """Runs vocal de-bleed per guitar part and collects one diagnostics file."""

    def __init__(self, enabled: bool, reason: str, vocals: Path | None) -> None:
        from audio_to_tab.vocal_debleed import VocalDebleedDiagnostics

        self.enabled = enabled
        self.vocals = vocals
        self.diag = VocalDebleedDiagnostics(
            attempted=enabled, reason=reason, enabled_by=str(reason.split(":")[0])
        )

    @classmethod
    def setup(cls, cfg: PipelineConfig, output_dir: Path, analysis: Any) -> _VocalDebleed:
        from audio_to_tab.vocal_debleed import resolve_vocal_debleed

        vocals = Path(output_dir) / "vocals.wav"
        vocals_path = vocals if vocals.is_file() else None
        present = None
        if analysis is not None:
            present = next((r.detected for r in analysis.inventory if r.id == "vocals"), None)
        enabled, reason = resolve_vocal_debleed(cfg, vocals_path, vocals_present=present)
        return cls(enabled, reason, vocals_path)

    def apply(self, part: str, notes: list, guitar_stem: Path) -> list:
        from audio_to_tab.vocal_debleed import DebleedFeatures, reject_vocal_bleed

        if not self.enabled or self.vocals is None:
            return notes
        features = DebleedFeatures.from_audio(Path(guitar_stem), self.vocals)
        self.diag.vocal_voiced_fraction = round(features.voiced_fraction, 4)
        self.diag.bleed_gain = None if features.bleed_gain is None else round(features.bleed_gain, 4)
        kept, report = reject_vocal_bleed(notes, features)
        self.diag.parts[part] = report.to_dict()
        return kept

    def write(self, output_dir: Path) -> Path | None:
        """Diagnostics only when there was a vocals stem to judge against (never on solo input)."""
        if self.vocals is None:
            return None
        return self.diag.write_json(Path(output_dir) / "vocal_debleed_diagnostics.json")


def _filter_midi_file(path: Path, keep: Any) -> None:
    import pretty_midi

    music = pretty_midi.PrettyMIDI(str(path))
    for inst in music.instruments:
        inst.notes = list(keep(list(inst.notes)))
    music.write(str(path))
