"""Bundled sample-tab demo pack."""

from __future__ import annotations

from pathlib import Path


def test_ensure_demo_run_idempotent(tmp_path: Path):
    from audio_to_tab.demo_pack import DEMO_TITLE, ensure_demo_run

    first = ensure_demo_run(tmp_path)
    second = ensure_demo_run(tmp_path)
    assert first["title"] == DEMO_TITLE
    assert Path(first["run_dir"]) == Path(second["run_dir"])
    artifacts = first["artifacts"]
    for key in ("midi", "result", "tab", "pdf"):
        path = Path(artifacts[key])
        assert path.is_file(), key
        assert path.stat().st_size > 0, key
    assert Path(first["run_dir"], "meta.json").is_file()


def test_tab_pdf_wires_try_sample():
    source = (Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py").read_text(
        encoding="utf-8"
    )
    assert "ensure_demo_run" in source
    assert "tab_try_sample" in source
    assert "Try sample tab" in source
