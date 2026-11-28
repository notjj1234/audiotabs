"""Analysis phase: ingest once, separate the full stem set once, split guitar, detect presence.

Everything lands in one cache folder so the tab phase can reuse it without
downloading or separating again::

    <analysis_dir>/source.wav            normalised + trimmed work audio
    <analysis_dir>/stems/<name>.wav      every stem the 6-stem model wrote
    <analysis_dir>/lead_guitar.wav       when the Lead/Rhythm split succeeded
    <analysis_dir>/rhythm_guitar.wav
    <analysis_dir>/lead_rhythm_fallback.json   when it did not
    <analysis_dir>/stem_presence.json, inventory.json, analysis.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audio_to_tab import lead_rhythm_sep
from audio_to_tab.cancel import CancelToken
from audio_to_tab.ingest import download_youtube_audio, normalize_audio
from audio_to_tab.inventory import LeadRhythmOutcome, PartCandidate, build_inventory
from audio_to_tab.isolate import StemPresence, detect_present_stems
from audio_to_tab.lead_rhythm_sep import LEAD_RHYTHM_SPLIT_ID
from audio_to_tab.roformer import BS_ROFORMER_SW_ID, split_stage1_skip_reason
from audio_to_tab.separate import (
    GUITAR_FT_CHECKPOINT_ID,
    guitar_ft_weights_cached,
    run_full_separation,
)
from audio_to_tab.subprocess_util import JobAborted
from audio_to_tab.vocal_debleed import guitar_for_split

ProgressCallback = Callable[..., None]
logger = logging.getLogger(__name__)

ANALYSIS_FILE = "analysis.json"
INVENTORY_FILE = "inventory.json"
PRESENCE_FILE = "stem_presence.json"
FALLBACK_FILE = "lead_rhythm_fallback.json"

SPLIT_OFF_REASON = "Lead and Rhythm splitting wasn't requested."
SPLIT_GENERIC_REASON = "the split model couldn't process this recording."


@dataclass
class AnalysisBundle:
    dir: Path
    work_audio: Path
    stems: dict[str, Path]
    lead_rhythm: LeadRhythmOutcome
    lead_rhythm_paths: dict[str, Path]
    inventory: list[PartCandidate]
    model: str
    fingerprint: str
    source: dict[str, Any] = field(default_factory=dict)


def _source_identity(source: dict[str, Any]) -> dict[str, Any]:
    kind = source.get("kind")
    key = {"upload": "upload_id", "youtube": "youtube_url", "media_url": "media_url"}.get(
        str(kind), ""
    )
    return {"kind": kind, "id": source.get(key)}


def analysis_fingerprint(source: dict[str, Any], config: Any, trim_start_sec: float) -> str:
    """Hash of the source plus every setting that changes the separated stems."""
    payload = {
        "source": _source_identity(source),
        "model": getattr(config, "model", None),
        "guitar_checkpoint": getattr(config, "guitar_checkpoint", None),
        "demucs_quality": getattr(config, "demucs_quality", None),
        "max_duration_sec": getattr(config, "max_duration_sec", None),
        "trim_start_sec": float(trim_start_sec or 0.0),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _device(config: Any) -> str:
    return str(getattr(config, "demucs_device", "cpu") or "cpu")


def _demucs_separation_model(config: Any) -> tuple[str, str | None]:
    model = str(getattr(config, "model", "") or "")
    checkpoint = getattr(config, "guitar_checkpoint", None)
    if model == "lead_rhythm_split" and checkpoint is None and guitar_ft_weights_cached():
        checkpoint = GUITAR_FT_CHECKPOINT_ID
    return "htdemucs_6s", checkpoint


def _split_stage1_skip_reason(config: Any) -> str | None:
    """Why the Lead/Rhythm split doesn't get BS-RoFormer SW's guitar stem (None = it does)."""
    if getattr(config, "guitar_checkpoint", None) is not None:
        return "a Demucs guitar checkpoint was chosen"
    return split_stage1_skip_reason(_device(config))


def analysis_separation_model(config: Any) -> tuple[str, str | None]:
    """The analysis always runs a 6-stem separator so every instrument is kept."""
    model = str(getattr(config, "model", "") or "")
    if model == BS_ROFORMER_SW_ID:
        return model, None
    if model == LEAD_RHYTHM_SPLIT_ID and _split_stage1_skip_reason(config) is None:
        return BS_ROFORMER_SW_ID, None
    return _demucs_separation_model(config)


def _trim(raw: Path, start_sec: float, max_duration_sec: float | None) -> Path:
    from audio_to_tab.pipeline import _trim_audio

    if not start_sec or start_sec <= 0:
        return _trim_audio(raw, max_duration_sec)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return _trim_audio(raw, max_duration_sec)
    out = raw.parent / f"{raw.stem}_from{int(start_sec * 1000)}.wav"
    cmd = [ffmpeg, "-y", "-ss", str(float(start_sec)), "-i", str(raw)]
    if max_duration_sec and max_duration_sec > 0:
        cmd += ["-t", str(float(max_duration_sec))]
    cmd.append(str(out))
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError("Could not trim the audio.")
    return out


SPLIT_TOO_LONG_REASON = "this recording is too long for the Lead/Rhythm split."
SPLIT_MISSING_REASON = "the Lead/Rhythm split model isn't installed."


def _split_reason(exc: BaseException) -> str:
    """Fixed user copy for a failed split; raw exception text stays in diagnostics."""
    from audio_to_tab.roformer import RoFormerTooLongError

    if isinstance(exc, RoFormerTooLongError):
        return SPLIT_TOO_LONG_REASON
    if isinstance(exc, lead_rhythm_sep.LeadRhythmSplitError) and "not available" in str(exc):
        return SPLIT_MISSING_REASON
    return SPLIT_GENERIC_REASON


def _rel(path: Path, root: Path) -> str:
    return str(Path(path).relative_to(root))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_analysis(
    *,
    audio_path: Path | None,
    youtube_url: str | None,
    analysis_dir: Path,
    config: Any,
    source: dict[str, Any],
    on_progress: ProgressCallback | None,
    cancel: CancelToken,
    trim_start_sec: float = 0.0,
) -> AnalysisBundle:
    """Run the analysis once; on cancel the whole folder is removed and JobAborted re-raised."""
    root = Path(analysis_dir)
    root.mkdir(parents=True, exist_ok=True)

    def progress(stage: str, message: str, fraction: float | None = None) -> None:
        cancel.check()
        if on_progress is not None:
            on_progress(stage, message, fraction)

    try:
        return _run(
            root=root,
            audio_path=audio_path,
            youtube_url=youtube_url,
            config=config,
            source=source,
            progress=progress,
            cancel=cancel,
            trim_start_sec=trim_start_sec,
        )
    except JobAborted:
        shutil.rmtree(root, ignore_errors=True)
        raise


def _run(
    *,
    root: Path,
    audio_path: Path | None,
    youtube_url: str | None,
    config: Any,
    source: dict[str, Any],
    progress: Callable[..., None],
    cancel: CancelToken,
    trim_start_sec: float,
) -> AnalysisBundle:
    progress("ingest", "Loading audio", 0.05)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if youtube_url:
            raw = download_youtube_audio(youtube_url, tmp_path)
        elif audio_path:
            raw = normalize_audio(audio_path, tmp_path / "normalized.wav")
        else:
            raise ValueError("Provide audio_path or youtube_url")
        work = _trim(Path(raw), trim_start_sec, getattr(config, "max_duration_sec", None))
        work_audio = root / "source.wav"
        shutil.copy2(work, work_audio)

    def separate(model: str, checkpoint: str | None) -> dict[str, Path]:
        return run_full_separation(
            work_audio,
            root / "stems",
            model=model,
            guitar_checkpoint=checkpoint,
            device=_device(config),
            quality=str(getattr(config, "demucs_quality", "balanced") or "balanced"),
            demucs_segment=getattr(config, "demucs_segment", 8),
            demucs_jobs=int(getattr(config, "demucs_jobs", 1) or 1),
            should_abort=cancel.is_cancelled,
            on_progress=lambda message, fraction: progress("separate", message, fraction),
        )

    model, checkpoint = analysis_separation_model(config)
    separation: dict[str, Any] = {"model": model}
    split_requested = str(getattr(config, "model", "") or "") == LEAD_RHYTHM_SPLIT_ID
    if split_requested and model != BS_ROFORMER_SW_ID:
        separation["roformer_skipped"] = _split_stage1_skip_reason(config)
    progress("separate", "Separating instruments", 0.1)
    try:
        stems = separate(model, checkpoint)
    except JobAborted:
        raise
    except Exception as exc:
        # Only the automatic RoFormer upgrade falls back; a chosen engine fails as before.
        if not (split_requested and model == BS_ROFORMER_SW_ID):
            raise
        logger.warning("BS-RoFormer SW failed; separating with Demucs instead: %s", exc)
        shutil.rmtree(root / "stems", ignore_errors=True)
        model, checkpoint = _demucs_separation_model(config)
        separation = {
            "model": model,
            "fallback_from": BS_ROFORMER_SW_ID,
            "fallback_reason": str(exc)[:500],
        }
        stems = separate(model, checkpoint)

    progress("split", "Splitting lead and rhythm guitar", 0.05)
    lead_rhythm_paths: dict[str, Path] = {}
    if not bool(getattr(config, "lead_rhythm_split", False)):
        outcome = LeadRhythmOutcome(ok=False, reason=SPLIT_OFF_REASON, skipped=True)
        progress("split", "skipped: Lead/Rhythm split is off")
    else:
        # The splitter files singing as Lead: it gets the guitar stem without the vocal copy.
        split_input, suppression = guitar_for_split(
            config, stems["guitar"], stems.get("vocals"), root / "_split" / "guitar_for_split.wav"
        )
        try:
            split, split_diag = lead_rhythm_sep.run_lead_rhythm_split(
                split_input,
                root / "_split",
                device=str(getattr(config, "demucs_device", "cpu") or "cpu"),
                on_progress=lambda message, fraction: progress("split", message, fraction),
            )
        except JobAborted:
            raise
        except Exception as exc:  # soft fallback: never fails the analysis
            reason = _split_reason(exc)
            logger.warning("Lead/Rhythm split failed during analysis: %s", exc)
            outcome = LeadRhythmOutcome(ok=False, reason=reason)
            _write_json(
                root / FALLBACK_FILE,
                {"fallback": True, "reason": reason, "detail": str(exc)[:500]},
            )
        else:
            for part in ("lead", "rhythm"):
                dest = root / f"{part}_guitar.wav"
                shutil.move(str(split[f"{part}_guitar"]), dest)
                lead_rhythm_paths[part] = dest
            split_diag.vocal_suppression = suppression
            split_diag.write_json(root / "lead_rhythm_split_diagnostics.json")
            outcome = LeadRhythmOutcome(
                ok=True, reason=None, presence=detect_present_stems(lead_rhythm_paths)
            )
        shutil.rmtree(root / "_split", ignore_errors=True)

    progress("detect", "Checking which instruments play", 0.5)
    presence = detect_present_stems(stems)
    _write_json(root / PRESENCE_FILE, {name: p.to_dict() for name, p in presence.items()})
    inventory = build_inventory(presence, lead_rhythm=outcome)
    _write_json(root / INVENTORY_FILE, [row.to_dict() for row in inventory])

    bundle = AnalysisBundle(
        dir=root,
        work_audio=work_audio,
        stems=stems,
        lead_rhythm=outcome,
        lead_rhythm_paths=lead_rhythm_paths,
        inventory=inventory,
        model=model,
        fingerprint=analysis_fingerprint(source, config, trim_start_sec),
        source=dict(source),
    )
    _write_json(
        root / ANALYSIS_FILE,
        {
            "created_at": time.time(),
            "fingerprint": bundle.fingerprint,
            "model": model,
            "separation": separation,
            "source": bundle.source,
            "work_audio": _rel(work_audio, root),
            "stems": {name: _rel(path, root) for name, path in stems.items()},
            "lead_rhythm": {
                "ok": outcome.ok,
                "reason": outcome.reason,
                "skipped": outcome.skipped,
                "presence": {k: v.to_dict() for k, v in outcome.presence.items()},
            },
            "lead_rhythm_paths": {k: _rel(v, root) for k, v in lead_rhythm_paths.items()},
        },
    )
    progress("detect", "Instruments ready", 1.0)
    return bundle


def load_analysis(analysis_dir: Path) -> AnalysisBundle:
    root = Path(analysis_dir)
    meta = json.loads((root / ANALYSIS_FILE).read_text(encoding="utf-8"))
    inventory_raw = json.loads((root / INVENTORY_FILE).read_text(encoding="utf-8"))
    lr = meta.get("lead_rhythm") or {}
    return AnalysisBundle(
        dir=root,
        work_audio=root / meta["work_audio"],
        stems={name: root / rel for name, rel in (meta.get("stems") or {}).items()},
        lead_rhythm=LeadRhythmOutcome(
            ok=bool(lr.get("ok")),
            reason=lr.get("reason"),
            skipped=bool(lr.get("skipped")),
            presence={k: StemPresence(**v) for k, v in (lr.get("presence") or {}).items()},
        ),
        lead_rhythm_paths={
            k: root / rel for k, rel in (meta.get("lead_rhythm_paths") or {}).items()
        },
        inventory=[PartCandidate.from_dict(row) for row in inventory_raw],
        model=str(meta.get("model") or ""),
        fingerprint=str(meta.get("fingerprint") or ""),
        source=dict(meta.get("source") or {}),
    )
