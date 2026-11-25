"""Cooperative cancel: token semantics, job cancel endpoint, pipeline early exit."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.jobs import JobManager
from app.server.main import create_app
from audio_to_tab.cancel import CancelToken
from audio_to_tab.subprocess_util import JobAborted

H = {"X-Tab-Token": "t"}


def test_cancel_token_check_raises_only_after_cancel():
    token = CancelToken()
    token.check()
    assert token.is_cancelled() is False
    token.cancel()
    assert token.is_cancelled() is True
    with pytest.raises(JobAborted):
        token.check()


def _upload(client, tmp_path) -> str:
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 40)
    with wav.open("rb") as handle:
        return client.post(
            "/api/uploads", headers=H, files={"file": ("clip.wav", handle, "audio/wav")}
        ).json()["upload_id"]


def test_cancel_between_stages_removes_folder(tmp_path):
    gate = threading.Event()
    seen_dirs: list[Path] = []

    def blocking(*, audio_path, youtube_url, output_dir, config, on_progress):
        seen_dirs.append(Path(output_dir))
        (Path(output_dir) / "partial.wav").write_bytes(b"x")
        on_progress("ingest", "Loading audio", 0.1)
        gate.wait(5)
        on_progress("transcribe", "Detecting notes", 0.5)
        raise AssertionError("runner should have been aborted at the progress call")

    app = create_app(data_dir=tmp_path, token="t")
    app.state.jobs = JobManager(tmp_path, runner=blocking)
    client = TestClient(app)
    job_id = client.post(
        "/api/jobs",
        headers=H,
        json={"source": {"kind": "upload", "upload_id": _upload(client, tmp_path)}},
    ).json()["job_id"]
    for _ in range(100):
        if seen_dirs:
            break
        time.sleep(0.01)

    r = client.post(f"/api/jobs/{job_id}/cancel", headers=H)
    assert r.status_code == 202
    assert r.json()["state"] in {"cancelling", "cancelled"}
    gate.set()

    snap = None
    for _ in range(200):
        snap = client.get(f"/api/jobs/{job_id}", headers=H).json()
        if snap["state"] == "cancelled":
            break
        time.sleep(0.01)
    assert snap["state"] == "cancelled", snap
    assert snap["run_id"] is None
    assert not seen_dirs[0].exists()


def test_cancel_unknown_job_404(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path, token="t"))
    r = client.post("/api/jobs/nope/cancel", headers=H)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "job_missing"


def test_run_pipeline_stops_before_ingest_when_cancelled(tmp_path, monkeypatch):
    import audio_to_tab.pipeline as pipeline

    called = []
    monkeypatch.setattr(pipeline, "normalize_audio", lambda *a, **k: called.append(a))
    token = CancelToken()
    token.cancel()
    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFF")
    with pytest.raises(JobAborted):
        pipeline.run_pipeline(audio_path=audio, output_dir=tmp_path / "out", cancel=token)
    assert called == []
