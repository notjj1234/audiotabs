"""Pure helpers behind the YouTube search dialog (no Streamlit, no network)."""

from __future__ import annotations

from audio_to_tab.ingest import YouTubeSearchHit
from ui.youtube_search import (
    PAGE_SIZE,
    hit_meta,
    hit_state,
    normalize_page,
)


def test_page_size_is_five():
    assert PAGE_SIZE == 5


def test_normalize_page_accepts_int_and_numeric_string():
    assert normalize_page(2) == 2
    assert normalize_page("3") == 3


def test_normalize_page_rejects_missing_and_out_of_range():
    assert normalize_page(None) == 1
    assert normalize_page(0) == 1
    assert normalize_page(-4) == 1
    assert normalize_page("nope") == 1


def test_hit_meta_joins_channel_and_duration():
    assert hit_meta({"channel": "Some Channel", "duration_sec": 185}) == "Some Channel · 3:05"


def test_hit_meta_keeps_only_the_parts_that_exist():
    assert hit_meta({"channel": "Some Channel"}) == "Some Channel"
    assert hit_meta({"duration_sec": 65}) == "1:05"
    assert hit_meta({}) == ""


def test_hit_state_serializes_a_search_hit():
    hit = YouTubeSearchHit(
        video_id="abc123",
        title="Song",
        channel="Channel",
        duration_sec=200,
        url="https://www.youtube.com/watch?v=abc123",
        thumbnail_url="https://i.ytimg.com/vi/abc123/hqdefault.jpg",
    )
    assert hit_state(hit) == {
        "video_id": "abc123",
        "title": "Song",
        "channel": "Channel",
        "duration_sec": 200,
        "url": "https://www.youtube.com/watch?v=abc123",
        "thumbnail_url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
    }
