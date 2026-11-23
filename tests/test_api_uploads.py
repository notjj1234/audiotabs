"""Upload and capabilities API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.main import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, token="t"))


def _headers():
    return {"X-Tab-Token": "t"}


def test_capabilities_shape(client):
    r = client.get("/api/capabilities", headers=_headers())
    assert r.status_code == 200
    body = r.json()
    assert "ffmpeg" in body
    assert body["max_upload_mb"] == 200
    assert "lead_rhythm" in body
    assert isinstance(body["lead_rhythm"], bool)


def test_capabilities_lead_rhythm_reflects_availability(client, monkeypatch):
    monkeypatch.setattr("app.server.routes_sources._lead_rhythm_available", lambda: True)
    r = client.get("/api/capabilities", headers=_headers())
    assert r.status_code == 200
    assert r.json()["lead_rhythm"] is True

    monkeypatch.setattr("app.server.routes_sources._lead_rhythm_available", lambda: False)
    r = client.get("/api/capabilities", headers=_headers())
    assert r.status_code == 200
    assert r.json()["lead_rhythm"] is False


def test_upload_stores_file(client, tmp_path):
    wav = tmp_path / "clip.wav"
    # Minimal RIFF header so the file exists; duration probe may return 0.
    wav.write_bytes(b"RIFF" + b"\x00" * 40)
    with wav.open("rb") as handle:
        r = client.post(
            "/api/uploads",
            headers=_headers(),
            files={"file": ("clip.wav", handle, "audio/wav")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["upload_id"]
    assert body["name"] == "clip.wav"
    assert body["bytes"] > 0
    stored = Path(body["path"])
    assert stored.is_file()


def test_upload_rejects_oversize(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.server.routes_sources.MAX_UPLOAD_MB", 0)
    wav = tmp_path / "big.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 100)
    with wav.open("rb") as handle:
        r = client.post(
            "/api/uploads",
            headers=_headers(),
            files={"file": ("big.wav", handle, "audio/wav")},
        )
    assert r.status_code == 413
