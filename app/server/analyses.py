"""Background analysis manager: separate once, detect instruments, cache for the tab job."""

from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audio_to_tab.cancel import CancelToken
from audio_to_tab.progress_checklist import apply_progress, new_analysis_checklist
from audio_to_tab.subprocess_util import JobAborted
from audio_to_tab.user_errors import failure_kind, user_facing_message

logger = logging.getLogger(__name__)

DEFAULT_TTL_SEC = 2 * 60 * 60
ANALYSES_DIRNAME = "analyses"


@dataclass
class AnalysisRecord:
    id: str
    dir: Path
    state: str = "queued"  # queued | running | cancelling | done | failed | cancelled
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    title: str = "Guitar Tab"
    rows: list[dict[str, str]] = field(default_factory=new_analysis_checklist)
    message: str = ""
    fraction: float = 0.0
    error: dict | None = None
    source: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    fingerprint: str = ""
    inventory: list[dict] | None = None
    lead_rhythm: dict | None = None


class AnalysisManager:
    def __init__(self, data_dir: Path, *, runner: Callable[..., Any] | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.root = self.data_dir / ANALYSES_DIRNAME
        self._lock = threading.Lock()
        self._records: dict[str, AnalysisRecord] = {}
        self._cancels: dict[str, CancelToken] = {}
        self._configs: dict[str, Any] = {}
        # Analyses a tab job is reading: never swept, and a DELETE waits for the job.
        self._in_use: set[str] = set()
        self._doomed: set[str] = set()
        self._runner = runner

    # --- queries -------------------------------------------------------
    def get(self, analysis_id: str) -> AnalysisRecord | None:
        with self._lock:
            rec = self._records.get(analysis_id)
            return None if rec is None else _copy(rec)

    def snapshot(self, analysis_id: str) -> dict | None:
        rec = self.get(analysis_id)
        if rec is None:
            return None
        return {
            "id": rec.id,
            "state": rec.state,
            "title": rec.title,
            "created_at": rec.created_at,
            "updated_at": rec.updated_at,
            "rows": rec.rows,
            "message": rec.message,
            "fraction": rec.fraction,
            "error": rec.error,
            "source": rec.source,
            "config": rec.config,
            "fingerprint": rec.fingerprint,
            "inventory": rec.inventory,
            "lead_rhythm": rec.lead_rhythm,
        }

    def bundle(self, analysis_id: str):
        """Load the cached AnalysisBundle for a finished analysis, else None."""
        from audio_to_tab.analysis import load_analysis

        rec = self.get(analysis_id)
        if rec is None or rec.state != "done":
            return None
        try:
            return load_analysis(rec.dir)
        except (OSError, ValueError, KeyError):
            return None

    def pipeline_config(self, analysis_id: str) -> Any:
        with self._lock:
            return self._configs.get(analysis_id)

    # --- lifecycle -----------------------------------------------------
    def start(
        self,
        *,
        title: str,
        audio_path: Path | None,
        youtube_url: str | None,
        config: Any,
        source: dict,
        config_meta: dict,
        trim_start_sec: float = 0.0,
    ) -> AnalysisRecord:
        self.sweep()
        analysis_id = str(uuid.uuid4())
        rec = AnalysisRecord(
            id=analysis_id,
            dir=self.root / analysis_id,
            title=title,
            source=dict(source),
            config=dict(config_meta),
        )
        with self._lock:
            self._records[analysis_id] = rec
            self._cancels[analysis_id] = CancelToken()
            self._configs[analysis_id] = config
        thread = threading.Thread(
            target=self._run,
            args=(analysis_id, audio_path, youtube_url, config, dict(source), trim_start_sec),
            name=f"analysis-{analysis_id[:8]}",
            daemon=True,
        )
        thread.start()
        return self.get(analysis_id)  # type: ignore[return-value]

    def cancel(self, analysis_id: str) -> AnalysisRecord | None:
        with self._lock:
            rec = self._records.get(analysis_id)
            token = self._cancels.get(analysis_id)
            if rec is None:
                return None
            if rec.state in {"queued", "running"} and token is not None:
                token.cancel()
                rec.state = "cancelling"
                rec.message = "Cancelling"
                rec.updated_at = time.time()
        return self.get(analysis_id)

    def mark_in_use(self, analysis_id: str) -> None:
        with self._lock:
            self._in_use.add(analysis_id)

    def release(self, analysis_id: str) -> None:
        """The tab job finished (any outcome); run a DELETE that arrived meanwhile."""
        with self._lock:
            self._in_use.discard(analysis_id)
            doomed = analysis_id in self._doomed
            self._doomed.discard(analysis_id)
            rec = self._records.get(analysis_id)
        if doomed:
            if rec is not None:
                shutil.rmtree(rec.dir, ignore_errors=True)
            else:
                shutil.rmtree(self.root / analysis_id, ignore_errors=True)
            with self._lock:
                self._records.pop(analysis_id, None)
                self._configs.pop(analysis_id, None)
                self._cancels.pop(analysis_id, None)

    def delete(self, analysis_id: str) -> bool:
        """Forget an analysis and remove its folder (cancels it first if running)."""
        with self._lock:
            rec = self._records.get(analysis_id)
            token = self._cancels.get(analysis_id)
            in_use = analysis_id in self._in_use
            if rec is not None and in_use:
                self._doomed.add(analysis_id)
        if rec is None:
            return False
        if in_use:
            return True
        if token is not None:
            token.cancel()
        if rec.state not in {"queued", "running", "cancelling"}:
            shutil.rmtree(rec.dir, ignore_errors=True)
        with self._lock:
            self._records.pop(analysis_id, None)
            self._configs.pop(analysis_id, None)
            self._cancels.pop(analysis_id, None)
        return True

    def consume(self, analysis_id: str) -> None:
        """The tab job finished with this analysis: drop the record and its folder."""
        with self._lock:
            self._in_use.discard(analysis_id)
            self._doomed.discard(analysis_id)
        self.delete(analysis_id)

    def sweep(self, *, max_age_sec: float = DEFAULT_TTL_SEC, all_idle: bool = False) -> None:
        """Remove idle analysis folders older than the TTL (or every idle one)."""
        if not self.root.is_dir():
            return
        with self._lock:
            busy = {
                rid
                for rid, rec in self._records.items()
                if rec.state in {"queued", "running", "cancelling"}
            } | set(self._in_use)
        now = time.time()
        for child in self.root.iterdir():
            if not child.is_dir() or child.name in busy:
                continue
            try:
                age = now - child.stat().st_mtime
            except OSError:
                continue
            if all_idle or age > max_age_sec:
                shutil.rmtree(child, ignore_errors=True)
                with self._lock:
                    self._records.pop(child.name, None)
                    self._configs.pop(child.name, None)

    # --- worker --------------------------------------------------------
    def _update(self, analysis_id: str, **kwargs: Any) -> None:
        with self._lock:
            rec = self._records.get(analysis_id)
            if rec is None:
                return
            for key, value in kwargs.items():
                setattr(rec, key, value)
            rec.updated_at = time.time()

    def _on_progress(self, analysis_id: str, stage: str, message: str, fraction: float | None) -> None:
        with self._lock:
            rec = self._records.get(analysis_id)
            if rec is None:
                return
            rec.rows = apply_progress(rec.rows, stage, message, fraction=fraction)
            rec.message = message
            if fraction is not None:
                rec.fraction = max(0.0, min(1.0, float(fraction)))
            rec.updated_at = time.time()

    def _run(
        self,
        analysis_id: str,
        audio_path: Path | None,
        youtube_url: str | None,
        config: Any,
        source: dict,
        trim_start_sec: float,
    ) -> None:
        with self._lock:
            token = self._cancels.get(analysis_id)
            rec = self._records.get(analysis_id)
            if token is None or rec is None:  # deleted before the thread started
                return
            folder = rec.dir
            if rec.state == "queued":
                rec.state = "running"
        try:
            runner = self._runner
            if runner is None:
                from audio_to_tab.analysis import run_analysis

                from .jobs import pipeline_config_from

                config = pipeline_config_from(config)
                with self._lock:
                    self._configs[analysis_id] = config
                runner = run_analysis
            bundle = runner(
                audio_path=audio_path,
                youtube_url=youtube_url,
                analysis_dir=folder,
                config=config,
                source=source,
                on_progress=lambda s, m, f=None: self._on_progress(analysis_id, s, m, f),
                cancel=token,
                trim_start_sec=trim_start_sec,
            )
            token.check()
            with self._lock:
                rec = self._records.get(analysis_id)
                if rec is None:  # deleted while finishing
                    shutil.rmtree(folder, ignore_errors=True)
                    return
                rec.rows = apply_progress(rec.rows, "done", "Instruments ready")
                rec.state = "done"
                rec.message = "Instruments ready"
                rec.fraction = 1.0
                rec.fingerprint = bundle.fingerprint
                rec.inventory = [row.to_dict() for row in bundle.inventory]
                rec.lead_rhythm = {
                    "ok": bundle.lead_rhythm.ok,
                    "reason": bundle.lead_rhythm.reason,
                }
                rec.updated_at = time.time()
        except JobAborted:
            shutil.rmtree(folder, ignore_errors=True)
            self._update(analysis_id, state="cancelled", message="Cancelled")
        except Exception as exc:
            if token.is_cancelled():
                shutil.rmtree(folder, ignore_errors=True)
                self._update(analysis_id, state="cancelled", message="Cancelled")
                return
            logger.exception("Analysis %s failed", analysis_id)
            message, detail = user_facing_message(exc)
            shutil.rmtree(folder, ignore_errors=True)
            self._update(
                analysis_id,
                state="failed",
                error={"code": failure_kind(exc), "message": message, "hint": detail},
                message=message,
            )


def _copy(rec: AnalysisRecord) -> AnalysisRecord:
    return AnalysisRecord(
        id=rec.id,
        dir=rec.dir,
        state=rec.state,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        title=rec.title,
        rows=[dict(r) for r in rec.rows],
        message=rec.message,
        fraction=rec.fraction,
        error=None if rec.error is None else dict(rec.error),
        source=dict(rec.source),
        config=dict(rec.config),
        fingerprint=rec.fingerprint,
        inventory=None if rec.inventory is None else [dict(r) for r in rec.inventory],
        lead_rhythm=None if rec.lead_rhythm is None else dict(rec.lead_rhythm),
    )

