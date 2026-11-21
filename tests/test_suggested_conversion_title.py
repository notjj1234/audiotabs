"""Tests for conversion title auto-fill helpers."""

from __future__ import annotations

from ui.common import (
    DEFAULT_CONVERSION_TITLE,
    is_default_conversion_title,
    maybe_autofill_conversion_title,
    suggested_conversion_title,
)


def test_suggested_title_from_upload_stem_keeps_unicode():
    assert suggested_conversion_title(filename="フルスピード・ボーイ.mp3") == "フルスピード・ボーイ"


def test_suggested_title_from_youtube_title():
    assert (
        suggested_conversion_title(youtube_title="  My Cool Song (Official)  ")
        == "My Cool Song (Official)"
    )


def test_suggested_title_from_media_url_basename():
    assert (
        suggested_conversion_title(media_url="https://cdn.example.com/tracks/song%20name.wav")
        == "song name"
    )


def test_suggested_title_prefers_youtube_then_filename_then_url():
    assert (
        suggested_conversion_title(
            youtube_title="Video Title",
            filename="ignored.mp3",
            media_url="https://x.test/other.mp3",
        )
        == "Video Title"
    )
    assert suggested_conversion_title(filename="clip.flac", media_url="https://x.test/other.mp3") == "clip"
    assert suggested_conversion_title(media_url="https://x.test/path/track.m4a") == "track"


def test_suggested_title_empty_when_no_source():
    assert suggested_conversion_title() == ""


def test_is_default_conversion_title():
    assert is_default_conversion_title(None)
    assert is_default_conversion_title("")
    assert is_default_conversion_title(DEFAULT_CONVERSION_TITLE)
    assert is_default_conversion_title("  Guitar Tab  ")
    assert not is_default_conversion_title("My Song")


def test_maybe_autofill_only_when_default():
    state: dict = {"tab_pdf_title": DEFAULT_CONVERSION_TITLE}
    assert maybe_autofill_conversion_title(state, "フルスピード・ボーイ") is True
    assert state["tab_pdf_title"] == "フルスピード・ボーイ"

    assert maybe_autofill_conversion_title(state, "Other") is False
    assert state["tab_pdf_title"] == "フルスピード・ボーイ"

    state["tab_pdf_title"] = DEFAULT_CONVERSION_TITLE
    assert maybe_autofill_conversion_title(state, "") is False
    assert state["tab_pdf_title"] == DEFAULT_CONVERSION_TITLE
