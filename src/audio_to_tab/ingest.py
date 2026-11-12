"""Audio ingestion and normalization."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from audio_to_tab.subprocess_util import subprocess_run_kwargs

logger = logging.getLogger(__name__)

_YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)

# yt-dlp extractor-args retry ladder for public videos (YouTube 403 / SABR).
# Attempt 1: skip android_sdkless (often 403). Attempt 2: web_safari HLS + tv_embedded.
# Attempt 3–4: alternate clients when YouTube keeps rejecting the first pair.
_YOUTUBE_PLAYER_CLIENTS = (
    "default,-android_sdkless",
    "web_safari,tv_embedded,-android_sdkless",
    "ios,tv_embedded",
    "web",
)

# Mixer slot is ~280px wide. 480p is enough for the picture and stays small on disk.
_PREVIEW_MAX_HEIGHT = 480


class YouTubeDownloadError(RuntimeError):
    """User-facing failure downloading public YouTube audio."""


class YouTubeSearchError(RuntimeError):
    """User-facing failure searching public YouTube videos (no API key)."""


class FFmpegMissingError(RuntimeError):
    """User-facing failure when ffmpeg is not on PATH."""


def ffmpeg_install_hint(*, platform: str | None = None) -> str:
    """Platform-specific install guidance for ffmpeg."""
    plat = (platform or sys.platform).lower()
    if plat.startswith("darwin"):
        return "Install ffmpeg with Homebrew: brew install ffmpeg"
    if plat.startswith("win"):
        return "Install ffmpeg with winget: winget install ffmpeg (or choco install ffmpeg)"
    return "Install ffmpeg with your package manager: sudo apt install ffmpeg"


class _YoutubeFileLogger:
    """Router all yt-dlp output to a per-download log file (any platform)."""

    def __init__(self, path: Path):
        self._path = path

    def _write(self, level: str, msg: str) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as log:
                log.write(f"[{level}] {msg}\n")
        except OSError:
            import sys

            sys.stderr.write(f"[yt-dlp] could not write log to {self._path}\n")

    def debug(self, msg: str) -> None:
        self._write("debug", str(msg))

    def info(self, msg: str) -> None:
        self._write("info", str(msg))

    def warning(self, msg: str) -> None:
        self._write("warning", str(msg))

    def error(self, msg: str) -> None:
        self._write("error", str(msg))


@dataclass(frozen=True)
class YouTubeSearchHit:
    """One public video from a no-API yt-dlp search."""

    video_id: str
    title: str
    channel: str
    duration_sec: int | None
    url: str
    thumbnail_url: str


def _youtube_host_ok(host: str) -> bool:
    if host in _YOUTUBE_HOSTS:
        return True
    return host.endswith(".youtube.com")


def _youtube_video_id(url: str) -> str | None:
    """Extract a watch/shorts/live/youtu.be video id, or None."""
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if not _youtube_host_ok(host):
        return None
    path = (parsed.path or "").rstrip("/")
    parts = [p for p in path.split("/") if p]
    if host in {"youtu.be", "www.youtu.be"} and parts:
        candidate = parts[0]
        return candidate if _looks_like_video_id(candidate) else None
    qs = parse_qs(parsed.query or "")
    if qs.get("v"):
        candidate = qs["v"][0]
        return candidate if _looks_like_video_id(candidate) else None
    if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed", "v"}:
        candidate = parts[1]
        return candidate if _looks_like_video_id(candidate) else None
    return None


def _looks_like_video_id(value: str) -> bool:
    text = (value or "").strip()
    # Real YouTube ids are usually 11 chars; allow short ids for tests/fixtures.
    if not (3 <= len(text) <= 64):
        return False
    return all(ch.isalnum() or ch in {"-", "_"} for ch in text)


def is_youtube_url(url: str) -> bool:
    """Return True if ``url`` is an http(s) YouTube link with a video id."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not _youtube_host_ok(host):
        return False
    return _youtube_video_id(url) is not None


def validate_youtube_url_shape(url: str) -> bool:
    """True when the URL looks like a specific public YouTube video."""
    return is_youtube_url(url)


def probe_youtube_availability(url: str) -> None:
    """Lightweight playability check (no download). Raises YouTubeDownloadError."""
    if not is_youtube_url(url):
        raise ValueError("Only YouTube URLs are allowed")
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise _user_facing_youtube_error(exc, attempts=1) from exc
    if not info:
        raise YouTubeDownloadError(
            "Could not verify this YouTube video. Only public videos work. "
            "Upload the audio file instead."
        )


_DIRECT_MEDIA_SUFFIXES = frozenset({".mp3", ".wav", ".flac", ".m4a", ".mp4", ".mov", ".webm", ".mkv"})
_DIRECT_MEDIA_MAX_BYTES = 500 * 1024 * 1024
_DIRECT_MEDIA_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})


def is_direct_media_url(url: str) -> bool:
    """True for an http(s) link whose path ends in a local audio or video type."""
    text = (url or "").strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return False
    if is_youtube_url(text):
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host in _DIRECT_MEDIA_BLOCKED_HOSTS or host.endswith(".localhost"):
        return False
    return Path(parsed.path).suffix.lower() in _DIRECT_MEDIA_SUFFIXES


def download_direct_media(url: str, output_dir: str | Path) -> Path:
    """Save a direct media link into ``output_dir``. No YouTube, no HTML page."""
    if not is_direct_media_url(url):
        raise ValueError("Only a direct audio or video link is allowed")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = Path(urlparse(url.strip()).path).name
    dest = out_dir / name
    request = urllib.request.Request(url.strip(), headers={"User-Agent": "AudioTools"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(_DIRECT_MEDIA_MAX_BYTES + 1)
    if len(data) > _DIRECT_MEDIA_MAX_BYTES:
        raise ValueError("That file is larger than 500 MB")
    if not data:
        raise ValueError("The link returned an empty file")
    dest.write_bytes(data)
    return dest


def _require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FFmpegMissingError(
            "ffmpeg is required but not found on PATH. " + ffmpeg_install_hint()
        )
    return ffmpeg


def ffmpeg_available() -> bool:
    """True when ffmpeg is on PATH (no raise)."""
    return shutil.which("ffmpeg") is not None


def _youtube_debug_enabled() -> bool:
    return os.environ.get("AUDIO_TOOLS_DEBUG", "").strip() in {"1", "true", "TRUE", "yes"}


def _youtube_log_path() -> Path | None:
    """Write verbose yt-dlp output when debugging or a desktop log dir exists."""
    if not _youtube_debug_enabled():
        return None
    override = os.environ.get("AUDIO_TOOLS_LOG_DIR", "").strip()
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(base) / "AudioTools" / "logs"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "AudioTools" / "logs"
    else:
        base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
        path = Path(base) / "audiotools" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path / "yt-dlp.log"


def _youtube_ydl_opts(
    *,
    template: str,
    player_client: str,
    verbose: bool = False,
    log_path: Path | None = None,
) -> dict:
    """yt-dlp options for one public-video download attempt."""
    ffmpeg = shutil.which("ffmpeg")
    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "extractor_args": {
            "youtube": {
                "player_client": [part.strip() for part in player_client.split(",") if part.strip()],
            }
        },
        "quiet": not verbose,
        "no_warnings": not verbose,
        "verbose": verbose,
    }
    if verbose and log_path is not None:
        opts["logger"] = _YoutubeFileLogger(log_path)
    if ffmpeg:
        opts["ffmpeg_location"] = str(Path(ffmpeg).resolve().parent)
    return opts


def _youtube_preview_ydl_opts(
    *,
    template: str,
    player_client: str,
    verbose: bool = False,
    log_path: Path | None = None,
) -> dict:
    """yt-dlp options for a short muted-preview mp4. No wav extract."""
    opts = _youtube_ydl_opts(
        template=template,
        player_client=player_client,
        verbose=verbose,
        log_path=log_path,
    )
    height = _PREVIEW_MAX_HEIGHT
    # H.264 + AAC first. The desktop webview cannot play the AV1 stream
    # YouTube often picks for "best" at this height.
    opts["format"] = (
        f"bv*[vcodec^=avc1][height<={height}]+ba[acodec^=mp4a]"
        f"/bv*[vcodec^=avc1][height<={height}]+ba"
        f"/b[vcodec^=avc1][height<={height}]"
        f"/bv*[height<={height}]+ba/b[height<={height}]/best[height<={height}]"
    )
    opts["merge_output_format"] = "mp4"
    opts["postprocessors"] = []
    return opts


def _is_403_error(exc: BaseException) -> bool:
    """True for HTTP 403 / forbidden download failures (walks the exception chain)."""
    cur: BaseException | None = exc
    for _ in range(8):
        if cur is None:
            break
        text = str(cur).lower()
        if "403" in text or "unable to download video data" in text or "forbidden" in text:
            return True
        code = getattr(cur, "code", None)
        if code is None:
            code = getattr(cur, "status", None)
        if code == 403:
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def _clear_ytdlp_cache() -> None:
    """Drop a stale player cache that often produces 403s after YouTube updates."""
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL({"rm_cachedir": True, "quiet": True}) as ydl:
            ydl.cache.remove()
    except Exception as exc:
        logger.debug("yt-dlp cache clear failed: %s", exc)


def _user_facing_youtube_error(
    last_exc: BaseException | None,
    *,
    attempts: int = 1,
    last_client: str | None = None,
) -> YouTubeDownloadError:
    detail = str(last_exc).strip() if last_exc else "unknown error"
    parts = [
        "Could not download this YouTube video.",
        "Only public videos work (no login).",
    ]
    if _is_403_error(last_exc or Exception("")):
        parts.append("YouTube rejected the download (HTTP 403).")
    parts.append(f"Tried {max(1, int(attempts))} download attempt(s)")
    if last_client:
        parts.append(f"(last player client: {last_client}).")
    else:
        parts.append(".")
    parts.extend(
        [
            "Try again in a few minutes.",
            "Paste a direct audio link if you have one.",
            "Upload the audio file instead.",
        ]
    )
    parts.append(f"Details: {detail}")
    return YouTubeDownloadError(" ".join(parts))


def _title_stem(name: str) -> str:
    """Canonical filename-stem form (case- and punctuation-insensitive)."""
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def _normalize_in_place(wav: Path) -> Path:
    """Normalize ``wav`` into a same-dir temp, then atomically move it back.

    Keeps the real file name (e.g. the YouTube video title) on the result so
    callers that use ``path.stem`` show the human title instead of the
    ``audio_norm_*`` temp name.
    """
    fd, name = tempfile.mkstemp(dir=str(wav.parent), prefix=".audio_norm_", suffix=".wav")
    os.close(fd)
    temp = Path(name)
    try:
        normalize_audio(wav, output_path=temp)
        try:
            temp.replace(wav)
        except OSError:
            shutil.move(str(temp), str(wav))
    finally:
        _unlink_quiet(temp)
    return wav


def _resolve_downloaded_wav(out_dir: Path, title: str, url: str) -> Path:
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in (title or "")).strip()[:80]
    if safe:
        want = _title_stem(safe)
        matches = [
            p for p in out_dir.glob("*.wav") if _title_stem(p.stem) == want
        ]
        if matches:
            return _normalize_in_place(max(matches, key=lambda p: p.stat().st_mtime))

    candidates = list(out_dir.glob("*.wav"))
    if candidates:
        return _normalize_in_place(max(candidates, key=lambda p: p.stat().st_mtime))
    raise FileNotFoundError(f"Downloaded audio not found for: {url}")


def format_youtube_duration(seconds: int | None) -> str:
    """Compact ``m:ss`` / ``h:mm:ss`` label; empty when duration is unknown."""
    if seconds is None:
        return ""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    if total < 0:
        return ""
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _watch_url_from_entry(entry: dict) -> str | None:
    """Build a normal watch URL from a yt-dlp flat or full search entry."""
    webpage = (entry.get("webpage_url") or entry.get("original_url") or "").strip()
    if is_youtube_url(webpage):
        return webpage
    raw_url = (entry.get("url") or "").strip()
    if is_youtube_url(raw_url):
        return raw_url
    video_id = (entry.get("id") or "").strip()
    if not video_id and raw_url and not raw_url.startswith("http"):
        video_id = raw_url
    if video_id and all(c.isalnum() or c in "-_" for c in video_id):
        return f"https://www.youtube.com/watch?v={video_id}"
    return None


def _thumbnail_url_for_entry(entry: dict, video_id: str) -> str:
    """Prefer yt-dlp thumbnail fields; else public CDN hqdefault for the id."""
    direct = (entry.get("thumbnail") or "").strip()
    if direct.startswith(("http://", "https://")):
        return direct
    thumbs = entry.get("thumbnails")
    if isinstance(thumbs, list):
        for thumb in reversed(thumbs):
            if not isinstance(thumb, dict):
                continue
            url = (thumb.get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                return url
    vid = (video_id or "").strip()
    if vid and all(c.isalnum() or c in "-_" for c in vid):
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return ""


# yt-dlp ``ytsearchN`` returns the first N matches only. Paging fetches
# offset+page_size then slices; this caps how deep a search can go.
_SEARCH_MAX_FETCH = 50


def search_youtube_videos(
    query: str,
    *,
    max_results: int = 5,
    offset: int = 0,
) -> list[YouTubeSearchHit]:
    """Search public YouTube videos via yt-dlp (no API key).

    Uses ``ytsearchN:query`` where N is ``offset + max_results`` (clamped).
    Returns the page slice ``[offset:offset+max_results]`` of mapped hits.
    Watch URLs are compatible with ``download_youtube_audio``.
    """
    q = (query or "").strip()
    if not q:
        raise ValueError("Enter a search query")
    page_size = max(1, min(int(max_results), _SEARCH_MAX_FETCH))
    start = max(0, int(offset))
    if start >= _SEARCH_MAX_FETCH:
        return []
    fetch_n = min(_SEARCH_MAX_FETCH, start + page_size)
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{fetch_n}:{q}", download=False)
    except Exception as exc:
        detail = str(exc).strip() or "unknown error"
        raise YouTubeSearchError(
            "Could not search YouTube. Check your connection and try again. "
            f"Details: {detail}"
        ) from exc

    entries = (info or {}).get("entries") or []
    hits: list[YouTubeSearchHit] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = _watch_url_from_entry(entry)
        if not url:
            continue
        video_id = (entry.get("id") or "").strip()
        if not video_id:
            video_id = (parse_qs(urlparse(url).query).get("v") or [""])[0].strip()
        if not video_id:
            continue
        title = (entry.get("title") or "Untitled").strip() or "Untitled"
        channel = (
            entry.get("channel")
            or entry.get("uploader")
            or entry.get("creator")
            or ""
        )
        channel = str(channel).strip()
        duration_raw = entry.get("duration")
        try:
            duration_sec = int(duration_raw) if duration_raw is not None else None
        except (TypeError, ValueError):
            duration_sec = None
        hits.append(
            YouTubeSearchHit(
                video_id=video_id,
                title=title,
                channel=channel,
                duration_sec=duration_sec,
                url=url,
                thumbnail_url=_thumbnail_url_for_entry(entry, video_id),
            )
        )
        if len(hits) >= fetch_n:
            break
    return hits[start : start + page_size]


def _snapshot_dir(path: Path) -> set[Path]:
    if not path.is_dir():
        return set()
    return {p.resolve() for p in path.iterdir()}


def _cleanup_attempt_artifacts(new_paths: set[Path]) -> None:
    """Remove only files created by a failed download attempt."""
    for path in new_paths:
        if not path.exists():
            continue
        name = path.name
        if (
            path.suffix.lower() in {".wav", ".part", ".ytdl", ".temp"}
            or ".part" in name
            or name.endswith(".download.mp4")
        ):
            _unlink_quiet(path)


def download_youtube_audio(url: str, output_dir: str | Path) -> Path:
    """Download audio from a public YouTube URL via yt-dlp.

    Retries with alternate player clients and a cache clear after HTTP 403.
    """
    if not is_youtube_url(url):
        raise ValueError("Only YouTube URLs are allowed")
    import yt_dlp

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / "%(title).80s.%(ext)s")
    verbose = _youtube_debug_enabled()
    log_path = _youtube_log_path()
    last_exc: BaseException | None = None
    last_client: str | None = None

    for index, player_client in enumerate(_YOUTUBE_PLAYER_CLIENTS):
        last_client = player_client
        if index > 0:
            _clear_ytdlp_cache()
        before = _snapshot_dir(out_dir)
        opts = _youtube_ydl_opts(
            template=template,
            player_client=player_client,
            verbose=verbose,
            log_path=log_path,
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            title = (info or {}).get("title", "youtube_audio")
            return _resolve_downloaded_wav(out_dir, title, url)
        except ValueError:
            raise
        except Exception as exc:
            last_exc = exc
            created = _snapshot_dir(out_dir) - before
            _cleanup_attempt_artifacts(created)
            if log_path is not None:
                try:
                    with log_path.open("a", encoding="utf-8") as log:
                        log.write(f"{url}\n{player_client}\n{exc}\n\n")
                except OSError:
                    pass
            if not _is_403_error(exc) or index == len(_YOUTUBE_PLAYER_CLIENTS) - 1:
                raise _user_facing_youtube_error(
                    exc, attempts=index + 1, last_client=player_client
                ) from exc
            continue

    raise _user_facing_youtube_error(
        last_exc, attempts=len(_YOUTUBE_PLAYER_CLIENTS), last_client=last_client
    )


def download_youtube_preview_video(url: str, dest: str | Path) -> Path:
    """Download a height-capped mp4 for the mixer picture.

    The file is the full video so a trimmed stem region can seek with an offset.
    Raises ``ValueError`` or ``YouTubeDownloadError``. Callers that only need
    the picture may catch and continue without it.
    """
    if not is_youtube_url(url):
        raise ValueError("Only YouTube URLs are allowed")
    import yt_dlp

    target = Path(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    template = str(target.parent / f".{target.stem}.download.%(ext)s")
    verbose = _youtube_debug_enabled()
    log_path = _youtube_log_path()
    last_exc: BaseException | None = None
    last_client: str | None = None

    for index, player_client in enumerate(_YOUTUBE_PLAYER_CLIENTS):
        last_client = player_client
        if index > 0:
            _clear_ytdlp_cache()
        before = _snapshot_dir(target.parent)
        opts = _youtube_preview_ydl_opts(
            template=template,
            player_client=player_client,
            verbose=verbose,
            log_path=log_path,
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
            downloaded = _take_preview_download(target)
            return downloaded
        except ValueError:
            raise
        except Exception as exc:
            last_exc = exc
            created = _snapshot_dir(target.parent) - before
            _cleanup_attempt_artifacts(created)
            if log_path is not None:
                try:
                    with log_path.open("a", encoding="utf-8") as log:
                        log.write(f"{url}\npreview\n{player_client}\n{exc}\n\n")
                except OSError:
                    pass
            if not _is_403_error(exc) or index == len(_YOUTUBE_PLAYER_CLIENTS) - 1:
                raise _user_facing_youtube_error(
                    exc, attempts=index + 1, last_client=player_client
                ) from exc
            continue

    raise _user_facing_youtube_error(
        last_exc, attempts=len(_YOUTUBE_PLAYER_CLIENTS), last_client=last_client
    )


def _take_preview_download(target: Path) -> Path:
    """Move the yt-dlp preview file onto ``target`` (mp4)."""
    matches = [
        path
        for path in target.parent.glob(f".{target.stem}.download.*")
        if path.is_file() and not path.name.endswith(".part")
    ]
    mp4s = [path for path in matches if path.suffix.lower() == ".mp4"]
    picked = mp4s[0] if mp4s else (matches[0] if matches else None)
    if picked is None:
        raise FileNotFoundError(f"Preview video was not written for {target.name}")
    _unlink_quiet(target)
    picked.replace(target)
    for stale in matches:
        if stale != picked:
            _unlink_quiet(stale)
    return target


def _unlink_quiet(path: Path) -> None:
    with suppress(OSError):
        path.unlink()


def temporary_output_path(prefix: str, suffix: str) -> Path:
    """Create a caller-owned temp output path for audio writing tools.

    ``tempfile.mkstemp`` hands back an open FD that engine functions never read
    or write (they pass the path to ffmpeg instead); closing it right away is
    required on Windows — an open FD makes later ``unlink()`` calls fail with
    ``PermissionError`` and leaks the handle. The caller owns the file (and its
    deletion) once returned.
    """
    fd, name = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return Path(name)


def normalize_audio(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Convert audio to canonical WAV for ML models. Output format is fixed at 44.1kHz stereo 16-bit WAV (required by ML models)."""
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Audio file not found: {src}")

    temp_out = output_path is None
    if temp_out:
        out = temporary_output_path("audio_norm_", ".wav")
    else:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = _require_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-ar",
        "44100",
        "-ac",
        "2",
        "-sample_fmt",
        "s16",
        str(out),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, **subprocess_run_kwargs())
    except BaseException:
        if temp_out:
            _unlink_quiet(out)
        raise
    if result.returncode != 0:
        if temp_out:
            _unlink_quiet(out)
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return out
