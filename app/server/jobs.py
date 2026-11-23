"""Background job manager for tab conversions."""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from audio_to_tab.progress_checklist import apply_progress, new_checklist
from audio_to_tab.user_errors import failure_kind, user_facing_message

from .store import write_run_metadata

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, float | None], None]

# PipelineConfig is only needed as a type for start(); import lazily in _run
# to avoid pulling numpy/torch at FastAPI import time (macOS numpy crash).
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audio_to_tab.pipeline import PipelineConfig


@dataclass
class JobRecord:
    id: str
    state: str = "queued"  # queued | running | done | failed
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    title: str = "Guitar Tab"
    rows: list[dict[str, str]] = field(default_factory=new_checklist)
    message: str = ""
    fraction: float = 0.0
    run_id: str | None = None
    error: dict | None = None
    source: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)


class JobManager:
    def __init__(
        self,
        data_dir: Path,
        *,
        runner: Callable[..., dict[str, Path]] | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}
        self._runner = runner

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return None if job is None else self._copy(job)

    def snapshot(self, job_id: str) -> dict | None:
        job = self.get(job_id)
        if job is None:
            return None
        return {
            "id": job.id,
            "state": job.state,
            "title": job.title,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "rows": job.rows,
            "message": job.message,
            "fraction": job.fraction,
            "run_id": job.run_id,
            "error": job.error,
            "source": job.source,
            "config": job.config,
        }

    def start(
        self,
        *,
        title: str,
        audio_path: Path | None,
        youtube_url: str | None,
        config: Any,
        source: dict,
        config_meta: dict,
    ) -> JobRecord:
        job_id = str(uuid.uuid4())
        job = JobRecord(
            id=job_id,
            title=title,
            source=source,
            config=config_meta,
        )
        with self._lock:
            self._jobs[job_id] = job
        thread = threading.Thread(
            target=self._run,
            args=(job_id, audio_path, youtube_url, config),
            name=f"tab-job-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return self.get(job_id)  # type: ignore[return-value]

    def _update(self, job_id: str, **kwargs: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in kwargs.items():
                setattr(job, key, value)
            job.updated_at = time.time()

    def _on_progress(self, job_id: str, stage: str, message: str, fraction: float | None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.rows = apply_progress(job.rows, stage, message, fraction=fraction)
            job.message = message
            if fraction is not None:
                job.fraction = max(0.0, min(1.0, float(fraction)))
            job.updated_at = time.time()

    def _run(
        self,
        job_id: str,
        audio_path: Path | None,
        youtube_url: str | None,
        config: Any,
    ) -> None:
        self._update(job_id, state="running")
        output_dir = self.data_dir / str(uuid.uuid4())
        output_dir.mkdir(parents=True, exist_ok=True)

        def progress(stage: str, message: str, fraction: float | None = None) -> None:
            self._on_progress(job_id, stage, message, fraction)

        try:
            runner = self._runner
            pipeline_config = config
            if runner is None:
                from audio_to_tab.pipeline import PipelineConfig, run_pipeline

                if not isinstance(config, PipelineConfig):
                    pipeline_config = PipelineConfig(
                        separate_stems=bool(getattr(config, "separate_stems", True)),
                        mix_aware_filtering=bool(getattr(config, "mix_aware_filtering", True)),
                        title=str(getattr(config, "title", "Guitar Tab")),
                        tuning_name=str(getattr(config, "tuning_name", "Standard (EADGBE)")),
                        capo=int(getattr(config, "capo", 0) or 0),
                        fingering_preference=str(
                            getattr(config, "fingering_preference", "playable")
                        ),
                        max_duration_sec=getattr(config, "max_duration_sec", None),
                        onset_threshold=float(getattr(config, "onset_threshold", 0.5)),
                        frame_threshold=float(getattr(config, "frame_threshold", 0.3)),
                        tempo_bpm_override=getattr(config, "tempo_bpm_override", None),
                        model=str(getattr(config, "model", "htdemucs_6s")),
                        demucs_device=str(getattr(config, "demucs_device", "cpu") or "cpu"),
                        guitar_refine=bool(getattr(config, "guitar_refine", False)),
                        guitar_checkpoint=getattr(config, "guitar_checkpoint", None),
                        low_end_restore_db=float(getattr(config, "low_end_restore_db", 0.0)),
                        sub_bass_debleed=bool(getattr(config, "sub_bass_debleed", False)),
                        bleed_gate=bool(getattr(config, "bleed_gate", False)),
                        adaptive_fold_gain=bool(getattr(config, "adaptive_fold_gain", False)),
                        guitar_ensemble=bool(getattr(config, "guitar_ensemble", False)),
                        export_gp5=True,
                        lead_rhythm_split=bool(getattr(config, "lead_rhythm_split", False)),
                        transpose=int(getattr(config, "transpose", 0) or 0),
                        bars_per_line=int(getattr(config, "bars_per_line", 4) or 4),
                    )
                runner = run_pipeline
            artifacts = runner(
                audio_path=audio_path,
                youtube_url=youtube_url,
                output_dir=output_dir,
                config=pipeline_config,
                on_progress=progress,
            )
            with self._lock:
                job = self._jobs[job_id]
                title = job.title
                source = dict(job.source)
                config_meta = dict(job.config)
            details = {
                "onset": config.onset_threshold,
                "frame": config.frame_threshold,
                "mix_aware": config.mix_aware_filtering,
                "separate": config.separate_stems,
                "lead_rhythm_split": config.lead_rhythm_split,
            }
            fallback_art = artifacts.get("lead_rhythm_fallback") if isinstance(artifacts, dict) else None
            if fallback_art is not None:
                fb_path = Path(fallback_art)
                if fb_path.is_file():
                    try:
                        payload = json.loads(fb_path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        payload = {}
                    details["lead_rhythm_fallback"] = True
                    reason = payload.get("reason") if isinstance(payload, dict) else None
                    if reason:
                        details["lead_rhythm_fallback_reason"] = str(reason)
            write_run_metadata(
                output_dir,
                page="tab_pdf",
                title=title,
                artifacts=artifacts,
                details=details,
                source=source,
                config=config_meta,
            )
            with self._lock:
                job = self._jobs[job_id]
                job.rows = apply_progress(job.rows, "done", "Pipeline complete")
                job.state = "done"
                job.run_id = output_dir.name
                job.message = "Done"
                job.fraction = 1.0
                job.updated_at = time.time()
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            message, detail = user_facing_message(exc)
            kind = failure_kind(exc)
            self._update(
                job_id,
                state="failed",
                error={
                    "code": kind,
                    "message": message,
                    "hint": detail,
                },
                message=message,
            )
            if output_dir.is_dir() and not (output_dir / "meta.json").is_file():
                shutil.rmtree(output_dir, ignore_errors=True)

    @staticmethod
    def _copy(job: JobRecord) -> JobRecord:
        return JobRecord(
            id=job.id,
            state=job.state,
            created_at=job.created_at,
            updated_at=job.updated_at,
            title=job.title,
            rows=[dict(r) for r in job.rows],
            message=job.message,
            fraction=job.fraction,
            run_id=job.run_id,
            error=None if job.error is None else dict(job.error),
            source=dict(job.source),
            config=dict(job.config),
        )
