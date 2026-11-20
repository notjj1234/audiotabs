"""Run store and read/delete API tests (plan Task 2)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.main import create_app
from app.server.store import (
    RunRecord,
    delete_run,
    get_run,
    list_runs,
    write_run_metadata,
)

_TOKEN = {"X-Tab-Token": "t"}


def _seed_run(
    data_dir: Path,
    run_id: str,
    *,
    title: str = "Song",
    created_at: float = 1_700_000_000.0,
    extra: dict | None = None,
) -> Path:
    run_dir = data_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "out.mid").write_bytes(b"MThd")
    (run_dir / "out.pdf").write_bytes(b"%PDF")
    meta = {
        "page": "tab_pdf",
        "title": title,
        "created_at": created_at,
        "artifacts": {"midi": str(run_dir / "out.mid"), "pdf": str(run_dir / "out.pdf")},
    }
    if extra:
        meta.update(extra)
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return run_dir


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, token="t"))


def test_list_runs_newest_first(tmp_path):
    _seed_run(tmp_path, "older", created_at=100.0)
    _seed_run(tmp_path, "newer", created_at=200.0)
    runs = list_runs(tmp_path)
    assert [r.id for r in runs] == ["newer", "older"]
    assert all(isinstance(r, RunRecord) for r in runs)


def test_list_runs_skips_dirs_without_meta(tmp_path):
    (tmp_path / "empty").mkdir()
    assert list_runs(tmp_path) == []


def test_get_run_rejects_path_traversal(tmp_path):
    _seed_run(tmp_path, "run-1")
    assert get_run(tmp_path, "run-1").id == "run-1"
    assert get_run(tmp_path, "..") is None
    assert get_run(tmp_path, "nested/run") is None

    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    _seed_run(tmp_path.parent, outside.name)
    link = tmp_path / "link-out"
    link.symlink_to(outside, target_is_directory=True)
    assert get_run(tmp_path, "link-out") is None


def test_delete_run_removes_folder(tmp_path):
    run_dir = _seed_run(tmp_path, "run-1")
    assert delete_run(tmp_path, "run-1") is True
    assert not run_dir.exists()
    assert delete_run(tmp_path, "run-1") is False
    assert delete_run(tmp_path, "..") is False


def test_metadata_roundtrip_includes_source_and_config(tmp_path):
    run_dir = tmp_path / "run-1"
    write_run_metadata(
        run_dir,
        page="tab_pdf",
        title="Song",
        artifacts={"midi": run_dir / "out.mid"},
        details={"bpm": 92},
        source={"kind": "upload", "name": "song.mp3"},
        config={"tuning_name": "Standard (EADGBE)", "capo": 0},
    )
    rec = get_run(tmp_path, "run-1")
    assert rec.source == {"kind": "upload", "name": "song.mp3"}
    assert rec.config == {"tuning_name": "Standard (EADGBE)", "capo": 0}
    assert rec.details == {"bpm": 92}
    assert rec.artifacts["midi"] == run_dir / "out.mid"
    first_created = rec.created_at

    write_run_metadata(
        run_dir,
        page="tab_pdf",
        title="Song",
        artifacts={"midi": run_dir / "out.mid"},
        feedback={"answer": "yes"},
    )
    updated = get_run(tmp_path, "run-1")
    assert updated.feedback == {"answer": "yes"}
    assert updated.source == {"kind": "upload", "name": "song.mp3"}
    assert updated.config == {"tuning_name": "Standard (EADGBE)", "capo": 0}
    assert updated.created_at == first_created

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    meta["custom_legacy"] = "keep"
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    write_run_metadata(
        run_dir, page="tab_pdf", title="Song", artifacts={"midi": run_dir / "out.mid"}
    )
    assert json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))["custom_legacy"] == "keep"


def test_legacy_meta_without_source_still_reads(tmp_path):
    run_dir = _seed_run(tmp_path, "legacy")
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert "source" not in meta
    assert "config" not in meta
    rec = get_run(tmp_path, "legacy")
    assert rec.source is None
    assert rec.config is None
    assert rec.feedback is None
    assert [r.id for r in list_runs(tmp_path)] == ["legacy"]


def test_api_runs_lists_newest_first(client, tmp_path):
    _seed_run(tmp_path, "older", title="Old", created_at=100.0)
    _seed_run(tmp_path, "newer", title="New", created_at=200.0)
    r = client.get("/api/runs", headers=_TOKEN)
    assert r.status_code == 200
    body = r.json()
    assert [row["id"] for row in body] == ["newer", "older"]


def test_api_run_record_shape(client, tmp_path):
    run_dir = _seed_run(
        tmp_path, "run-1", extra={"source": {"kind": "youtube"}, "config": {"capo": 2}}
    )
    r = client.get("/api/runs/run-1", headers=_TOKEN)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "run-1"
    assert body["title"] == "Song"
    assert body["artifacts"] == {"midi": True, "pdf": True}
    assert body["source"] == {"kind": "youtube"}
    assert body["config"] == {"capo": 2}
    assert body["feedback"] is None
    assert "created_at" in body
    assert "details" in body

    (run_dir / "out.mid").unlink()
    body = client.get("/api/runs/run-1", headers=_TOKEN).json()
    assert body["artifacts"] == {"midi": False, "pdf": True}


def test_api_run_not_found_and_traversal(client, tmp_path):
    _seed_run(tmp_path, "run-1")
    assert client.get("/api/runs/nope", headers=_TOKEN).status_code == 404
    assert client.get("/api/runs/%2E%2E", headers=_TOKEN).status_code == 404


def test_api_delete_run(client, tmp_path):
    run_dir = _seed_run(tmp_path, "run-1")
    r = client.delete("/api/runs/run-1", headers=_TOKEN)
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert not run_dir.exists()
    assert client.delete("/api/runs/run-1", headers=_TOKEN).status_code == 404
    assert client.delete("/api/runs/%2E%2E", headers=_TOKEN).status_code == 404


def test_api_run_includes_lead_rhythm_diagnostics(client, tmp_path):
    run_dir = _seed_run(
        tmp_path,
        "lr-run",
        extra={"config": {"model": "lead_rhythm_split"}},
    )
    diag = {
        "warnings": ["Input is mono"],
        "envelope_correlation": 0.42,
        "lead": {"rms_dbfs": -21.0},
    }
    diag_path = run_dir / "lead_rhythm_split_diagnostics.json"
    diag_path.write_text(json.dumps(diag), encoding="utf-8")
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    meta["artifacts"]["lead_rhythm_split_diagnostics"] = str(diag_path)
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    body = client.get("/api/runs/lr-run", headers=_TOKEN).json()
    assert body["diagnostics"] == diag

    # Mode chip signal for the web UI.
    assert body["config"]["model"] == "lead_rhythm_split"


def test_api_run_diagnostics_none_when_absent(client, tmp_path):
    _seed_run(tmp_path, "plain-run")
    body = client.get("/api/runs/plain-run", headers=_TOKEN).json()
    assert body["diagnostics"] is None
