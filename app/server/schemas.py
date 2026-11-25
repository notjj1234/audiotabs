"""Pydantic request bodies for jobs, exports, and feedback."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceIn(BaseModel):
    kind: Literal["upload", "youtube", "media_url"]
    upload_id: str | None = None
    youtube_url: str | None = None
    media_url: str | None = None


class JobRequest(BaseModel):
    source: SourceIn
    title: str = "Guitar Tab"
    trim_start_sec: float = 0.0
    preset: Literal["solo", "full_mix"] = "solo"
    config: dict[str, Any] = Field(default_factory=dict)
    # Reuse a finished instrument analysis instead of downloading/separating again.
    analysis_id: str | None = None
    parts: list[str] | None = None


class ExportRequest(BaseModel):
    format: Literal["pdf", "midi", "tab", "gp5", "musicxml", "guitar_stem"]
    tuning: str = "Standard (EADGBE)"
    capo: int = 0
    transpose: int = 0
    bars: int = 4
    # Omitted part = today's single-part export, unchanged.
    part: str | None = None
    # MIDI / MusicXML only: every part in ``shown`` in one file.
    all_shown: bool = False
    shown: list[str] | None = None


class ViewState(BaseModel):
    mode: Literal["single", "together"] = "single"
    part: str | None = None
    shown: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    answer: Literal["yes", "no"]


class YoutubeSearchRequest(BaseModel):
    query: str
    page: int = 1
