"""Pure helpers behind the YouTube search dialog (no Streamlit, no network)."""

from __future__ import annotations

from typing import Any

from audio_to_tab.ingest import YouTubeSearchHit, format_youtube_duration

PAGE_SIZE = 5


def normalize_page(value: Any) -> int:
    """Coerce a stored page number to a 1-based integer."""
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return page if page >= 1 else 1


def hit_meta(hit: dict) -> str:
    """One muted line: ``Channel · 3:05`` with missing parts dropped."""
    channel = str(hit.get("channel") or "").strip()
    duration = format_youtube_duration(hit.get("duration_sec"))
    return " · ".join(part for part in (channel, duration) if part)


def hit_state(hit: YouTubeSearchHit) -> dict:
    """Serialize a search hit into session state (plain dict)."""
    return {
        "video_id": hit.video_id,
        "title": hit.title,
        "channel": hit.channel,
        "duration_sec": hit.duration_sec,
        "url": hit.url,
        "thumbnail_url": hit.thumbnail_url,
    }
