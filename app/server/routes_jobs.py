"""Create and poll conversion jobs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Request

from audio_to_tab.ingest import download_direct_media
from audio_to_tab.tuning import TUNING_PRESETS

from .auth import require_token
from .errors import error_body, http_error
from .jobs import JobManager
from .schemas import JobRequest

router = APIRouter(dependencies=[Depends(require_token)])

_ALLOWED_CONFIG = {
    "tuning_name",
    "capo",
    "fingering_preference",
    "separate_stems",
    "mix_aware_filtering",
    "max_duration_sec",
    "onset_threshold",
    "frame_threshold",
    "tempo_bpm_override",
    "model",
    "guitar_refine",
    "guitar_checkpoint",
    "low_end_restore_db",
    "sub_bass_debleed",
    "bleed_gate",
    "adaptive_fold_gain",
    "guitar_ensemble",
}

_FINGERING = frozenset({"playable", "low_fret", "position"})


def _jobs(request: Request) -> JobManager:
    manager = getattr(request.app.state, "jobs", None)
    if manager is None:
        manager = JobManager(Path(request.app.state.data_dir))
        request.app.state.jobs = manager
    return manager


def _resolve_upload(data_dir: Path, upload_id: str) -> Path:
    if not upload_id or Path(upload_id).name != upload_id:
        raise http_error(400, code="invalid_upload", message="Invalid upload id.")
    root = (data_dir / "uploads" / upload_id).resolve()
    uploads = (data_dir / "uploads").resolve()
    if uploads not in root.parents and root != uploads:
        raise http_error(400, code="invalid_upload", message="Invalid upload id.")
    if not root.is_dir():
        raise http_error(404, code="upload_missing", message="Upload not found.")
    files = [p for p in root.iterdir() if p.is_file()]
    if not files:
        raise http_error(404, code="upload_missing", message="Upload not found.")
    return files[0]


def _build_config(body: JobRequest) -> tuple[SimpleNamespace, dict]:
    """Build a PipelineConfig-shaped namespace without importing the engine."""
    raw = dict(body.config or {})
    unknown = sorted(set(raw) - _ALLOWED_CONFIG)
    if unknown:
        raise http_error(
            422,
            code="unknown_config",
            message=f"Unknown config field: {unknown[0]}",
        )

    if "separate_stems" not in raw:
        separate = body.preset == "full_mix"
    else:
        separate = bool(raw.get("separate_stems"))
    if "mix_aware_filtering" not in raw:
        mix_aware = body.preset == "full_mix"
    else:
        mix_aware = bool(raw.get("mix_aware_filtering"))

    tuning = str(raw.get("tuning_name") or "Standard (EADGBE)")
    if tuning not in TUNING_PRESETS:
        raise http_error(422, code="bad_tuning", message=f"Unknown tuning: {tuning}")

    fingering = str(raw.get("fingering_preference") or "playable")
    if fingering not in _FINGERING:
        raise http_error(422, code="bad_config", message=f"Invalid fingering_preference: {fingering}")

    capo = int(raw.get("capo") or 0)
    if not 0 <= capo <= 12:
        raise http_error(422, code="bad_config", message=f"capo must be 0..12, got {capo}")

    onset = float(raw.get("onset_threshold") or 0.5)
    frame = float(raw.get("frame_threshold") or 0.3)
    if not 0.0 <= onset <= 1.0 or not 0.0 <= frame <= 1.0:
        raise http_error(422, code="bad_config", message="thresholds must be 0..1")

    max_duration = raw.get("max_duration_sec")
    tempo = raw.get("tempo_bpm_override")
    config = SimpleNamespace(
        separate_stems=separate,
        mix_aware_filtering=mix_aware,
        title=str(body.title or "Guitar Tab"),
        tuning_name=tuning,
        capo=capo,
        fingering_preference=fingering,
        max_duration_sec=None if max_duration in (None, "") else float(max_duration),
        onset_threshold=onset,
        frame_threshold=frame,
        tempo_bpm_override=None if not tempo else float(tempo),
        model=str(raw.get("model") or "htdemucs_6s"),
        guitar_refine=bool(raw.get("guitar_refine")),
        guitar_checkpoint=raw.get("guitar_checkpoint") or None,
        low_end_restore_db=float(raw.get("low_end_restore_db") or 0.0),
        sub_bass_debleed=bool(raw.get("sub_bass_debleed")),
        bleed_gate=bool(raw.get("bleed_gate")),
        adaptive_fold_gain=bool(raw.get("adaptive_fold_gain")),
        guitar_ensemble=bool(raw.get("guitar_ensemble")),
        export_gp5=True,
        lead_rhythm_split=str(raw.get("model") or "") == "lead_rhythm_split",
        transpose=0,
        bars_per_line=4,
    )
    meta = {
        "tuning_name": config.tuning_name,
        "capo": config.capo,
        "model": config.model,
        "separate_stems": config.separate_stems,
        "mix_aware_filtering": config.mix_aware_filtering,
        "fingering_preference": config.fingering_preference,
        "preset": body.preset,
    }
    return config, meta


@router.post("/api/jobs", status_code=202, response_model=None)
def api_create_job(body: JobRequest, request: Request):
    data_dir = Path(request.app.state.data_dir)
    audio_path: Path | None = None
    youtube_url: str | None = None
    source = {"kind": body.source.kind}

    try:
        if body.source.kind == "upload":
            if not body.source.upload_id:
                raise http_error(400, code="missing_source", message="Choose an audio file.")
            audio_path = _resolve_upload(data_dir, body.source.upload_id)
            source["upload_id"] = body.source.upload_id
            source["name"] = audio_path.name
        elif body.source.kind == "youtube":
            youtube_url = (body.source.youtube_url or "").strip()
            if not youtube_url:
                raise http_error(400, code="missing_source", message="Paste a YouTube link.")
            source["youtube_url"] = youtube_url
        elif body.source.kind == "media_url":
            media_url = (body.source.media_url or "").strip()
            if not media_url:
                raise http_error(400, code="missing_source", message="Paste a media URL.")
            dest = data_dir / "uploads" / str(__import__("uuid").uuid4())
            dest.mkdir(parents=True, exist_ok=True)
            audio_path = download_direct_media(media_url, dest)
            source["media_url"] = media_url
            source["name"] = audio_path.name
        else:
            raise http_error(400, code="missing_source", message="Choose a source.")
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        return __import__("fastapi").responses.JSONResponse(
            status_code=400, content=error_body(exc)
        )

    config, config_meta = _build_config(body)
    job = _jobs(request).start(
        title=config.title,
        audio_path=audio_path,
        youtube_url=youtube_url,
        config=config,
        source=source,
        config_meta=config_meta,
    )
    return {"job_id": job.id, "state": job.state}


@router.get("/api/jobs/{job_id}")
def api_get_job(job_id: str, request: Request) -> dict:
    snap = _jobs(request).snapshot(job_id)
    if snap is None:
        raise http_error(404, code="job_missing", message="Job not found.")
    return snap
