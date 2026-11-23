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


class ExportRequest(BaseModel):
    format: Literal["pdf", "midi", "tab", "gp5", "musicxml", "guitar_stem"]
    tuning: str = "Standard (EADGBE)"
    capo: int = 0
    transpose: int = 0
    bars: int = 4


class FeedbackRequest(BaseModel):
    answer: Literal["yes", "no"]


class YoutubeSearchRequest(BaseModel):
    query: str
    page: int = 1
