"""Tests for recent-run listing and hard-delete helpers."""

from __future__ import annotations

from pathlib import Path

from app.helpers import recent as common


def _seed_run(data_dir: Path, *, title: str = "Guitar Tab") -> Path:
    run_dir = data_dir / "run-abc"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "out.pdf").write_bytes(b"%PDF")
    common.write_run_metadata(
        run_dir,
        page="tab_pdf",
        title=title,
        artifacts={"pdf": str(run_dir / "out.pdf")},
    )
    return run_dir


def test_delete_run_removes_folder(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    run_dir = _seed_run(tmp_path)
    assert run_dir.is_dir()

    assert common.delete_run(run_dir) is True
    assert not run_dir.exists()
    assert common.list_recent_runs("tab_pdf") == []


def test_delete_run_refuses_path_outside_data_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "safe")
    (tmp_path / "safe").mkdir()
    outsider = tmp_path / "other" / "run"
    outsider.mkdir(parents=True)
    (outsider / "meta.json").write_text("{}", encoding="utf-8")

    assert common.delete_run(outsider) is False
    assert outsider.is_dir()


def test_delete_run_missing_returns_false(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    assert common.delete_run(tmp_path / "missing") is False


def test_delete_runs_deletes_each_and_returns_count(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    a = tmp_path / "a"
    b = tmp_path / "b"
    for d, title in ((a, "A"), (b, "B")):
        d.mkdir()
        (d / "out.pdf").write_bytes(b"%PDF")
        common.write_run_metadata(
            d, page="tab_pdf", title=title, artifacts={"pdf": str(d / "out.pdf")}
        )

    deleted = common.delete_runs([a, b, tmp_path / "gone"])
    assert deleted == 2
    assert not a.exists()
    assert not b.exists()
    assert common.list_recent_runs("tab_pdf") == []
