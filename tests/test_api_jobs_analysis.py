"""Tab jobs that reuse a finished analysis (analysis_id + parts)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.jobs import JobManager
from app.server.main import create_app
from tests.analysis_fakes import patch_analysis_engine
from tests.test_api_jobs import _fake_pipeline

H = {"X-Tab-Token": "t"}


def _recording_runner(seen: dict, *, fail: bool = False):
    def runner(*, audio_path, youtube_url, output_dir, config, on_progress, analysis=None, parts=None, cancel=None):
        seen["analysis"] = analysis
        seen["parts"] = parts
        seen["audio_path"] = audio_path
        if fail:
            raise RuntimeError("transcription crashed")
        artifacts = _fake_pipeline(
            audio_path=audio_path, youtube_url=youtube_url, output_dir=output_dir,
            config=config, on_progress=on_progress,
        )
        parts_path = Path(output_dir) / "parts.json"
        parts_path.write_text(json.dumps({"parts": parts, "empty": {"keys": "No notes found in this part."}}))
        artifacts["parts"] = parts_path
        return artifacts

    return runner


@pytest.fixture
def setup(tmp_path, monkeypatch):
    patch_analysis_engine(monkeypatch)
    seen: dict = {}
    app = create_app(data_dir=tmp_path, token="t")
    app.state.jobs = JobManager(tmp_path, runner=_recording_runner(seen))
    client = TestClient(app)
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 40)
    with wav.open("rb") as handle:
        upload_id = client.post(
            "/api/uploads", headers=H, files={"file": ("clip.wav", handle, "audio/wav")}
        ).json()["upload_id"]
    body = {
        "source": {"kind": "upload", "upload_id": upload_id},
        "title": "Song",
        "preset": "full_mix",
        "config": {"model": "lead_rhythm_split"},
    }
    analysis_id = client.post("/api/analyses", headers=H, json=body).json()["analysis_id"]
    for _ in range(300):
        if client.get(f"/api/analyses/{analysis_id}", headers=H).json()["state"] == "done":
            break
        time.sleep(0.01)
    return client, app, seen, body, analysis_id, tmp_path


def _poll(client, job_id):
    snap = None
    for _ in range(300):
        snap = client.get(f"/api/jobs/{job_id}", headers=H).json()
        if snap["state"] in {"done", "failed", "cancelled"}:
            break
        time.sleep(0.01)
    return snap


def test_job_reuses_analysis_and_records_parts(setup):
    client, _app, seen, body, analysis_id, tmp_path = setup
    r = client.post(
        "/api/jobs",
        headers=H,
        json={**body, "analysis_id": analysis_id, "parts": ["lead", "rhythm", "keys"]},
    )
    assert r.status_code == 202, r.text
    snap = _poll(client, r.json()["job_id"])
    assert snap["state"] == "done", snap
    assert seen["parts"] == ["lead", "rhythm", "keys"]
    assert seen["analysis"].fingerprint
    meta = client.get(f"/api/runs/{snap['run_id']}", headers=H).json()
    details = meta["details"]
    assert details["parts"] == ["lead", "rhythm", "keys"]
    assert details["empty_parts"] == {"keys": "No notes found in this part."}
    assert any(row["id"] == "lead" for row in details["inventory"])
    assert not (tmp_path / "analyses" / analysis_id).exists()


def test_settings_change_that_affects_separation_is_rejected(setup):
    client, _app, _seen, body, analysis_id, _ = setup
    changed = {**body, "config": {"model": "htdemucs_6s"}}
    r = client.post("/api/jobs", headers=H, json={**changed, "analysis_id": analysis_id, "parts": ["combined"]})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "analysis_mismatch"


def test_capo_change_reuses_analysis(setup):
    client, _app, _seen, body, analysis_id, _ = setup
    changed = {**body, "config": {"model": "lead_rhythm_split", "capo": 3}}
    r = client.post("/api/jobs", headers=H, json={**changed, "analysis_id": analysis_id, "parts": ["lead"]})
    assert r.status_code == 202, r.text


def test_empty_parts_rejected(setup):
    client, _app, _seen, body, analysis_id, _ = setup
    r = client.post("/api/jobs", headers=H, json={**body, "analysis_id": analysis_id, "parts": []})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "no_parts"


def test_unknown_part_rejected(setup):
    client, _app, _seen, body, analysis_id, _ = setup
    r = client.post("/api/jobs", headers=H, json={**body, "analysis_id": analysis_id, "parts": ["kazoo"]})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "bad_parts"


def test_missing_analysis_404(setup):
    client, _app, _seen, body, _analysis_id, _ = setup
    r = client.post("/api/jobs", headers=H, json={**body, "analysis_id": "nope", "parts": ["lead"]})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "analysis_missing"


def test_failed_job_keeps_analysis_for_retry(setup):
    client, app, seen, body, analysis_id, tmp_path = setup
    app.state.jobs = JobManager(tmp_path, runner=_recording_runner(seen, fail=True))
    r = client.post("/api/jobs", headers=H, json={**body, "analysis_id": analysis_id, "parts": ["lead"]})
    assert _poll(client, r.json()["job_id"])["state"] == "failed"
    assert (tmp_path / "analyses" / analysis_id / "analysis.json").is_file()


def _blocking_runner(gate, seen, *, fail=False):
    def runner(*, audio_path, youtube_url, output_dir, config, on_progress, analysis=None, parts=None, cancel=None):
        seen["started"] = True
        gate.wait(5)
        if fail:
            raise RuntimeError("transcription crashed")
        return _recording_runner({})(audio_path=audio_path, youtube_url=youtube_url, output_dir=output_dir,
                                     config=config, on_progress=on_progress, analysis=analysis, parts=parts)
    return runner


def _wait_started(seen):
    for _ in range(300):
        if seen.get("started"):
            return
        time.sleep(0.01)


def test_sweep_and_delete_spare_an_analysis_a_running_job_is_reading(setup):
    import threading

    client, app, _seen, body, analysis_id, tmp_path = setup
    gate, seen = threading.Event(), {}
    app.state.jobs = JobManager(tmp_path, runner=_blocking_runner(gate, seen, fail=True))
    job = client.post("/api/jobs", headers=H, json={**body, "analysis_id": analysis_id, "parts": ["lead"]}).json()
    _wait_started(seen)
    folder = tmp_path / "analyses" / analysis_id
    app.state.analyses.sweep(all_idle=True)
    assert folder.is_dir(), "sweep removed stems a running job is reading"
    assert client.delete(f"/api/analyses/{analysis_id}", headers=H).status_code == 204
    assert folder.is_dir(), "delete removed stems a running job is reading"
    gate.set()
    assert _poll(client, job["job_id"])["state"] == "failed"
    for _ in range(100):
        if not folder.exists():
            break
        time.sleep(0.01)
    assert not folder.exists(), "the deferred delete never happened"


def test_failed_job_without_delete_keeps_analysis_and_releases_it(setup):
    import threading

    client, app, _seen, body, analysis_id, tmp_path = setup
    gate, seen = threading.Event(), {}
    app.state.jobs = JobManager(tmp_path, runner=_blocking_runner(gate, seen, fail=True))
    job = client.post("/api/jobs", headers=H, json={**body, "analysis_id": analysis_id, "parts": ["lead"]}).json()
    _wait_started(seen)
    gate.set()
    assert _poll(client, job["job_id"])["state"] == "failed"
    folder = tmp_path / "analyses" / analysis_id
    assert folder.is_dir()
    app.state.analyses.sweep(all_idle=True)
    assert not folder.exists(), "released analysis should be sweepable again"
