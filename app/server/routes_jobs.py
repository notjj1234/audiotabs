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
    "demucs_device",
    "vocal_debleed",
}

_DEVICES = frozenset({"cpu", "cuda", "mps"})

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


def build_config(body: JobRequest) -> tuple[SimpleNamespace, dict]:
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

    # GPU-first when the host can run it (Apple MPS / NVIDIA CUDA); else CPU.
    from audio_to_tab.hardware import default_pipeline_device, resolve_safe_device

    requested = raw.get("demucs_device")
    if requested in (None, ""):
        demucs_device = default_pipeline_device()
    else:
        demucs_device = str(requested)
        if demucs_device not in _DEVICES:
            raise http_error(
                422,
                code="bad_config",
                message=f"demucs_device must be one of {sorted(_DEVICES)}, got {demucs_device!r}",
            )
        demucs_device = resolve_safe_device(demucs_device)

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
        vocal_debleed=str(raw.get("vocal_debleed") or "auto"),
        demucs_device=demucs_device,
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
        "demucs_device": config.demucs_device,
        "preset": body.preset,
    }
    return config, meta


def resolve_source(body: JobRequest, data_dir: Path) -> tuple[Path | None, str | None, dict]:
    """Turn the request source into (audio_path, youtube_url, source meta). Raises HTTP errors."""
    audio_path: Path | None = None
    youtube_url: str | None = None
    source = {"kind": body.source.kind}
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
    return audio_path, youtube_url, source


def resolve_source_or_response(body: JobRequest, data_dir: Path):
    """resolve_source, but non-HTTP failures (e.g. download errors) become a 400 JSON body."""
    try:
        return resolve_source(body, data_dir), None
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        return None, __import__("fastapi").responses.JSONResponse(
            status_code=400, content=error_body(exc)
        )


def _create_from_analysis(body: JobRequest, request: Request) -> dict:
    from audio_to_tab.analysis import analysis_fingerprint
    from audio_to_tab.pipeline import KNOWN_PARTS

    from .analyses import AnalysisManager
    from .jobs import pipeline_config_from

    manager = getattr(request.app.state, "analyses", None)
    if manager is None:
        manager = AnalysisManager(Path(request.app.state.data_dir))
        request.app.state.analyses = manager
    analysis_id = str(body.analysis_id)
    bundle = manager.bundle(analysis_id)
    if bundle is None:
        raise http_error(
            404,
            code="analysis_missing",
            message="The instrument check for this song is no longer available. Convert again.",
        )
    if body.parts is not None and not body.parts:
        raise http_error(422, code="no_parts", message="Choose at least one part to tab.")
    unknown = [p for p in (body.parts or []) if p not in KNOWN_PARTS]
    if unknown:
        raise http_error(422, code="bad_parts", message=f"Unknown part: {unknown[0]}")
    config, config_meta = build_config(body)
    pipeline_config = pipeline_config_from(config)
    fingerprint = analysis_fingerprint(
        bundle.source, pipeline_config, float(body.trim_start_sec or 0.0)
    )
    if fingerprint != bundle.fingerprint:
        raise http_error(
            409,
            code="analysis_mismatch",
            message="These settings change how instruments are separated. Check the instruments again.",
        )
    manager.mark_in_use(analysis_id)
    job = _jobs(request).start(
        title=config.title,
        audio_path=None,
        youtube_url=None,
        config=pipeline_config,
        source=dict(bundle.source),
        config_meta={**config_meta, "parts": list(body.parts or [])},
        analysis=bundle,
        parts=None if body.parts is None else list(body.parts),
        on_success=lambda: manager.consume(analysis_id),
        on_end=lambda: manager.release(analysis_id),
    )
    return {"job_id": job.id, "state": job.state}


@router.post("/api/jobs", status_code=202, response_model=None)
def api_create_job(body: JobRequest, request: Request):
    if body.analysis_id:
        return _create_from_analysis(body, request)
    data_dir = Path(request.app.state.data_dir)
    resolved, failure = resolve_source_or_response(body, data_dir)
    if failure is not None:
        return failure
    audio_path, youtube_url, source = resolved

    config, config_meta = build_config(body)
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


@router.post("/api/jobs/{job_id}/retry", status_code=202)
def api_retry_job(job_id: str, request: Request) -> dict:
    manager = _jobs(request)
    if manager.snapshot(job_id) is None:
        raise http_error(
            404,
            code="job_missing",
            message="This conversion is no longer available. Go back and start it again.",
        )
    job = manager.retry(job_id)
    if job is None:
        raise http_error(
            409,
            code="retry_unavailable",
            message="This conversion can't be retried. Go back and start it again.",
        )
    return {"job_id": job.id, "state": job.state}


@router.post("/api/jobs/{job_id}/cancel", status_code=202)
def api_cancel_job(job_id: str, request: Request) -> dict:
    job = _jobs(request).cancel(job_id)
    if job is None:
        raise http_error(404, code="job_missing", message="Job not found.")
    return {"job_id": job.id, "state": job.state}
