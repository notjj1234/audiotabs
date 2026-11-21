"""Source selection chip helpers."""

from __future__ import annotations

import pytest


def test_source_chip_requires_name():
    from audio_to_tab.source_chip import source_chip

    with pytest.raises(ValueError):
        source_chip(name="  ")


def test_source_chip_formats_size_and_duration():
    from audio_to_tab.source_chip import format_source_chip_caption, source_chip

    chip = source_chip(name="riff.mp3", size_bytes=1536, duration_sec=65)
    assert chip["name"] == "riff.mp3"
    caption = format_source_chip_caption(chip)
    assert "1.5 KB" in caption
    assert "1:05" in caption


def test_cached_upload_preview_reuses_path(tmp_path, monkeypatch):
    from ui import common

    calls = {"n": 0}

    def fake_save(uploaded):
        calls["n"] += 1
        dest = tmp_path / f"run{calls['n']}" / "riff.mp3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"abc")
        return dest

    monkeypatch.setattr(common, "save_upload", fake_save)

    class Uploaded:
        name = "riff.mp3"
        size = 3

        def getvalue(self):
            return b"abc"

    state: dict = {}
    first = common.cached_upload_preview(state, Uploaded())
    second = common.cached_upload_preview(state, Uploaded())
    assert first == second
    assert calls["n"] == 1
