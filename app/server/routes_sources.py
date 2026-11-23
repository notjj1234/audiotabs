"""Uploads, capabilities, and YouTube search."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from audio_to_tab.ingest import (
    YouTubeSearchError,
    format_youtube_duration,
    search_youtube_videos,
)
from .auth import require_token
from .errors import error_body, http_error
from .schemas import YoutubeSearchRequest

router = APIRouter(dependencies=[Depends(require_token)])

MAX_UPLOAD_MB = 200
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}


def _data_dir(request: Request) -> Path:
    return Path(request.app.state.data_dir)


def _safe_name(name: str | None) -> str:
    base = Path(name or "").name.replace("\x00", "").strip()
    if not base or base in {".", ".."}:
        raise http_error(400, code="invalid_upload", message="Invalid upload filename")
    return base


@router.get("/api/capabilities")
def api_capabilities() -> dict:
    # Use find_spec only — importing demucs/roformer can segfault on some macOS
    # numpy builds during test collection / light API probes.
    import importlib.util

    demucs = importlib.util.find_spec("demucs") is not None
    roformer = importlib.util.find_spec("bs_roformer_infer") is not None or (
        importlib.util.find_spec("audio_separator") is not None
    )
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "demucs": demucs,
        "roformer": roformer,
        "guitar_ft": demucs,
        "max_upload_mb": MAX_UPLOAD_MB,
    }


@router.post("/api/uploads")
async def api_upload(request: Request, file: UploadFile = File(...)) -> dict:
    name = _safe_name(file.filename)
    suffix = Path(name).suffix.lower()
    if suffix and suffix not in AUDIO_SUFFIXES:
        raise http_error(
            400,
            code="invalid_upload",
            message=f"Unsupported audio type: {suffix}",
            hint="Use MP3, WAV, M4A, or FLAC.",
        )
    uploads_root = _data_dir(request) / "uploads"
    uploads_root.mkdir(parents=True, exist_ok=True)
    upload_id = str(uuid.uuid4())
    dest_dir = uploads_root / upload_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name

    size = 0
    limit = MAX_UPLOAD_MB * 1024 * 1024
    with dest.open("wb") as handle:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                handle.close()
                shutil.rmtree(dest_dir, ignore_errors=True)
                raise http_error(
                    413,
                    code="upload_too_large",
                    message=f"File exceeds {MAX_UPLOAD_MB} MB.",
                )
            handle.write(chunk)

    return {
        "upload_id": upload_id,
        "name": name,
        "bytes": size,
        "duration_sec": 0.0,
        "path": str(dest),
    }


@router.post("/api/youtube/search", response_model=None)
def api_youtube_search(body: YoutubeSearchRequest):
    query = (body.query or "").strip()
    if not query:
        raise http_error(400, code="empty_query", message="Enter a search query.")
    page = max(1, int(body.page or 1))
    page_size = 5
    offset = (page - 1) * page_size
    try:
        hits = search_youtube_videos(query, max_results=page_size, offset=offset)
    except YouTubeSearchError as exc:
        return JSONResponse(status_code=400, content=error_body(exc))
    except Exception as exc:
        return JSONResponse(status_code=400, content=error_body(exc))
    return {
        "page": page,
        "hits": [
            {
                "video_id": hit.video_id,
                "title": hit.title,
                "channel": hit.channel,
                "duration_sec": hit.duration_sec,
                "duration_label": format_youtube_duration(hit.duration_sec),
                "url": hit.url,
                "thumbnail_url": hit.thumbnail_url,
            }
            for hit in hits
        ],
    }
