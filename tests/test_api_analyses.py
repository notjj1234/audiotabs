"""Analysis API: start, poll, inventory, cancel, delete, TTL sweep."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.analyses import AnalysisManager
from app.server.main import create_app
from tests.analysis_fakes import patch_analysis_engine

H = {"X-Tab-Token": "t"}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, token="t"))


def _upload(client, tmp_path) -> str:
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 40)
    with wav.open("rb") as handle:
        return client.post(
            "/api/uploads", headers=H, files={"file": ("clip.wav", handle, "audio/wav")}
        ).json()["upload_id"]


def _start(client, tmp_path, **config) -> str:
    r = client.post(
        "/api/analyses",
        headers=H,
        json={
            "source": {"kind": "upload", "upload_id": _upload(client, tmp_path)},
            "title": "Song",
            "preset": "full_mix",
            "config": {"model": "lead_rhythm_split", **config},
        },
    )
    assert r.status_code == 202, r.text
    return r.json()["analysis_id"]


def _poll(client, analysis_id, states=("done", "failed", "cancelled")):
    snap = None
    for _ in range(300):
        snap = client.get(f"/api/analyses/{analysis_id}", headers=H).json()
        if snap["state"] in states:
            break
        time.sleep(0.01)
    return snap


def test_start_poll_done_with_inventory(client, tmp_path, monkeypatch):
    patch_analysis_engine(monkeypatch)
    analysis_id = _start(client, tmp_path)
    snap = _poll(client, analysis_id)
    assert snap["state"] == "done", snap
    ids = [row["id"] for row in snap["inventory"]]
    assert ids[:3] == ["lead", "rhythm", "combined"]
    assert {row["id"] for row in snap["inventory"]} >= {"bass", "vocals", "keys", "drums"}
    assert snap["fingerprint"]
    row_ids = [r["id"] for r in snap["rows"]]
    assert row_ids == ["ingest", "separate", "split", "detect"]
    assert (tmp_path / "analyses" / analysis_id / "inventory.json").is_file()


def test_cancel_removes_folder(client, tmp_path, monkeypatch):
    gate = threading.Event()
    patch_analysis_engine(monkeypatch, gate=gate)
    analysis_id = _start(client, tmp_path)
    for _ in range(100):
        if (tmp_path / "analyses" / analysis_id / "source.wav").exists():
            break
        time.sleep(0.01)
    r = client.post(f"/api/analyses/{analysis_id}/cancel", headers=H)
    assert r.status_code == 202
    gate.set()
    snap = _poll(client, analysis_id)
    assert snap["state"] == "cancelled"
    assert not (tmp_path / "analyses" / analysis_id).exists()


def test_delete_removes_folder_and_record(client, tmp_path, monkeypatch):
    patch_analysis_engine(monkeypatch)
    analysis_id = _start(client, tmp_path)
    assert _poll(client, analysis_id)["state"] == "done"
    r = client.delete(f"/api/analyses/{analysis_id}", headers=H)
    assert r.status_code == 204
    assert not (tmp_path / "analyses" / analysis_id).exists()
    assert client.get(f"/api/analyses/{analysis_id}", headers=H).status_code == 404


def test_unknown_analysis_404(client):
    assert client.get("/api/analyses/nope", headers=H).status_code == 404
    assert client.post("/api/analyses/nope/cancel", headers=H).status_code == 404


def test_unknown_config_422(client, tmp_path):
    r = client.post(
        "/api/analyses",
        headers=H,
        json={
            "source": {"kind": "upload", "upload_id": _upload(client, tmp_path)},
            "config": {"bogus": 1},
        },
    )
    assert r.status_code == 422


def test_failure_copy_has_no_raw_exception(client, tmp_path, monkeypatch):
    import audio_to_tab.analysis as analysis

    def boom(*a, **k):
        raise RuntimeError("Traceback: torch exploded at 0xdeadbeef")

    patch_analysis_engine(monkeypatch)
    monkeypatch.setattr(analysis, "run_full_separation", boom)
    snap = _poll(client, _start(client, tmp_path))
    assert snap["state"] == "failed"
    assert "0xdeadbeef" not in snap["error"]["message"]


def test_sweep_removes_old_idle_and_keeps_fresh(tmp_path):
    root = tmp_path / "analyses"
    old = root / "old"
    fresh = root / "fresh"
    for d in (old, fresh):
        d.mkdir(parents=True)
        (d / "analysis.json").write_text(json.dumps({"created_at": time.time()}))
    past = time.time() - 3 * 3600
    os.utime(old, (past, past))
    manager = AnalysisManager(tmp_path)
    manager.sweep(max_age_sec=7200)
    assert not old.exists()
    assert fresh.exists()
    manager.sweep(all_idle=True)
    assert not fresh.exists()


def test_startup_sweeps_leftover_analyses(tmp_path):
    leftover = tmp_path / "analyses" / "x"
    leftover.mkdir(parents=True)
    create_app(data_dir=tmp_path, token="t")
    assert not leftover.exists()
