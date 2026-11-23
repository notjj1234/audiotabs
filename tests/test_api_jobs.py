"""Job create/poll with an injected fake runner (no pipeline import)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.jobs import JobManager
from app.server.main import create_app


def _fake_pipeline(*, audio_path, youtube_url, output_dir, config, on_progress):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    on_progress("ingest", "Loading audio", 0.2)
    on_progress("transcribe", "Detecting notes", 0.6)
    midi = output_dir / "notes.mid"
    tab = output_dir / "transcription.tab"
    pdf = output_dir / "transcription.pdf"
    playback = output_dir / "playback.wav"
    result = output_dir / "result.json"
    midi.write_bytes(b"MThd")
    tab.write_text("e|--|\n")
    pdf.write_bytes(b"%PDF")
    playback.write_bytes(b"RIFF")
    result.write_text(
        '{"title":"Test","key":"C","tempo_bpm":120,"duration_sec":1,'
        '"tuning_name":"Standard (EADGBE)","capo":0,"transpose":0,'
        '"bars_per_line":4,"beats_per_measure":4,"chords":[],"lyrics":[],'
        '"lyrics_status":"","tempo_confidence":"high"}'
    )
    on_progress("pdf", "Finalizing PDF", 0.9)
    return {"midi": midi, "tab": tab, "pdf": pdf, "playback": playback, "result": result}


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path, token="t")
    app.state.jobs = JobManager(tmp_path, runner=_fake_pipeline)
    return TestClient(app)


def _headers():
    return {"X-Tab-Token": "t"}


def test_create_job_from_upload_and_poll_done(client, tmp_path):
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 40)
    with wav.open("rb") as handle:
        up = client.post(
            "/api/uploads",
            headers=_headers(),
            files={"file": ("clip.wav", handle, "audio/wav")},
        )
    assert up.status_code == 200
    upload_id = up.json()["upload_id"]

    created = client.post(
        "/api/jobs",
        headers=_headers(),
        json={
            "source": {"kind": "upload", "upload_id": upload_id},
            "title": "Test Song",
            "preset": "solo",
            "config": {"tuning_name": "Standard (EADGBE)", "capo": 0},
        },
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    import time

    snap = None
    for _ in range(50):
        r = client.get(f"/api/jobs/{job_id}", headers=_headers())
        assert r.status_code == 200
        snap = r.json()
        if snap["state"] in {"done", "failed"}:
            break
        time.sleep(0.05)
    assert snap is not None
    assert snap["state"] == "done", snap
    assert snap["run_id"]
    run = client.get(f"/api/runs/{snap['run_id']}", headers=_headers())
    assert run.status_code == 200
    assert run.json()["title"] == "Test Song"


def test_job_rejects_unknown_config(client, tmp_path):
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 8)
    with wav.open("rb") as handle:
        up = client.post(
            "/api/uploads",
            headers=_headers(),
            files={"file": ("clip.wav", handle, "audio/wav")},
        )
    upload_id = up.json()["upload_id"]
    r = client.post(
        "/api/jobs",
        headers=_headers(),
        json={
            "source": {"kind": "upload", "upload_id": upload_id},
            "config": {"demucs_device": "cuda"},
        },
    )
    assert r.status_code == 422
