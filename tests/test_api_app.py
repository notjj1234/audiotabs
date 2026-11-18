"""Contract tests for the FastAPI skeleton (plan Task 1)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.main import create_app
from app.server.paths import web_dist_dir


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, token="t"))


def test_health_needs_no_token(client):
    assert client.get("/api/health").status_code == 200


def test_health_payload(client):
    assert client.get("/api/health").json() == {"ok": True, "version": "0.1.6"}


def test_api_requires_token(client):
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/runs", headers={"X-Tab-Token": "t"}).status_code == 200


def test_api_rejects_wrong_token(client):
    assert client.get("/api/runs", headers={"X-Tab-Token": "wrong"}).status_code == 401


def test_token_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TABPDF_TOKEN", "env-token")
    c = TestClient(create_app(data_dir=tmp_path))
    assert c.get("/api/runs").status_code == 401
    assert c.get("/api/runs", headers={"X-Tab-Token": "env-token"}).status_code == 200


def test_token_generated_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("TABPDF_TOKEN", raising=False)
    c = TestClient(create_app(data_dir=tmp_path))
    assert c.get("/api/runs").status_code == 401


def test_web_dist_dir_is_meipass_safe(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert web_dist_dir() == tmp_path / "app" / "web" / "dist"


def test_web_dist_dir_source_layout(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    expected = Path(__file__).resolve().parents[1] / "app" / "web" / "dist"
    assert web_dist_dir() == expected


def test_root_serves_placeholder_when_dist_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("app.server.main.web_dist_dir", lambda: tmp_path / "missing")
    c = TestClient(create_app(data_dir=tmp_path, token="t"))
    r = c.get("/")
    assert r.status_code == 200
    assert "make ui-build" in r.text


def test_root_serves_dist_when_present(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>hello</h1>")
    monkeypatch.setattr("app.server.main.web_dist_dir", lambda: dist)
    c = TestClient(create_app(data_dir=tmp_path, token="t"))
    r = c.get("/")
    assert r.status_code == 200
    assert "hello" in r.text
