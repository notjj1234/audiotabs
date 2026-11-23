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
