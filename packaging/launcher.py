"""Desktop launcher: native window over the local FastAPI + Svelte app.

Dev-only entry point (`make desktop`). Starts ``python -m app.server`` on
127.0.0.1 and opens a pywebview window with the launch token in the URL hash.
"""

from __future__ import annotations

import argparse
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PORTS = tuple(range(8501, 8511))
WINDOW_SIZE = (1280, 860)
WINDOW_MIN_SIZE = (960, 640)
WINDOW_TITLE = "Audio Tabs"
HEALTH_TIMEOUT_SEC = 180.0
HEALTH_POLL_SEC = 0.3


def window_icon() -> str | None:
    """Prefer .ico on Windows (WinForms); padded PNG on macOS for dock tile size."""
    ico = REPO_ROOT / "assets" / "app-icon.ico"
    png = REPO_ROOT / "assets" / "app-icon.png"
    dock = REPO_ROOT / "assets" / "app-icon-dock.png"
    if sys.platform.startswith("win"):
        path = ico if ico.is_file() else png
    elif sys.platform == "darwin":
        path = dock if dock.is_file() else (png if png.is_file() else ico)
    else:
        path = png if png.is_file() else ico
    return str(path) if path.is_file() else None


def log(message: str) -> None:
    print(f"[desktop] {message}", file=sys.stderr, flush=True)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        try:
            sock.connect(("127.0.0.1", port))
        except OSError:
            return True
    return False


def pick_port() -> int:
    busy: list[int] = []
    for port in PORTS:
        if port_free(port):
            if busy:
                log(f"Skipping in-use port(s) {busy}; using {port}")
            return port
        busy.append(port)
    raise RuntimeError(
        f"No free port in {PORTS[0]}-{PORTS[-1]} "
        f"(already accepting connections: {busy}). "
        "Close the other Audio Tabs window and try again."
    )


def health_ok(port: int, path: str = "/api/health") -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}{path}", timeout=1.5
        ) as resp:
            return 200 <= int(getattr(resp, "status", 0) or 0) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_until_healthy(
    port: int, server: subprocess.Popen, path: str = "/api/health"
) -> bool:
    deadline = time.monotonic() + HEALTH_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if health_ok(port, path):
            return True
        if server.poll() is not None:
            log("Server exited before becoming healthy")
            return False
        time.sleep(HEALTH_POLL_SEC)
    return False


def build_web_url(port: int, token: str) -> str:
    return f"http://127.0.0.1:{port}/#token={token}"


def web_server_command(port: int) -> list[str]:
    return [sys.executable, "-m", "app.server", "--port", str(port)]


def start_web_server(port: int, token: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["TABPDF_TOKEN"] = token
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), str(REPO_ROOT), env.get("PYTHONPATH", "")]
    )
    return subprocess.Popen(
        web_server_command(port),
        cwd=str(REPO_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
    )


def parse_ui(argv: list[str] | None = None) -> str:
    """Kept for tests/compat; web is the only front end."""
    parser = argparse.ArgumentParser(description="Audio Tabs desktop launcher")
    parser.add_argument(
        "--ui",
        choices=("web",),
        default="web",
        help="front end to serve (web only)",
    )
    return parser.parse_args(argv).ui


def stop_server(server: subprocess.Popen | None) -> None:
    if server is None or server.poll() is not None:
        return
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


def _warn_if_ffmpeg_missing() -> None:
    import shutil

    if shutil.which("ffmpeg"):
        return
    try:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from audio_to_tab.ingest import ffmpeg_install_hint

        hint = ffmpeg_install_hint()
    except Exception:
        hint = "Install ffmpeg and ensure it is on PATH"
    log(f"WARNING: ffmpeg not found on PATH. {hint}")


def main(argv: list[str] | None = None) -> int:
    parse_ui(argv)  # validate flags
    try:
        import webview
    except ImportError:
        log("pywebview is not installed. Run: pip install -e '.[desktop]'")
        return 1

    _warn_if_ffmpeg_missing()
    port = pick_port()
    token = secrets.token_urlsafe(32)
    log(f"Starting web server on 127.0.0.1:{port}")
    server = start_web_server(port, token)
    window_url = build_web_url(port, token)
    try:
        if not wait_until_healthy(port, server, "/api/health"):
            log("Server never became healthy")
            return 1
        log(f"Opening native window -> {window_url}")
        window = webview.create_window(
            WINDOW_TITLE,
            window_url,
            width=WINDOW_SIZE[0],
            height=WINDOW_SIZE[1],
            min_size=WINDOW_MIN_SIZE,
        )

        def on_shown() -> None:
            log("Window shown; close it to stop the app")

        def on_closed() -> None:
            log("Window closed by user")

        try:
            window.events.shown += on_shown
            window.events.closed += on_closed
        except (AttributeError, TypeError):
            log("pywebview window events unavailable")
        started = time.monotonic()
        icon = window_icon()
        if icon:
            log(f"Using window icon {icon}")
            webview.start(icon=icon)
        else:
            log("No assets/app-icon.(png|ico); starting without custom icon")
            webview.start()
        log(f"webview.start returned after {time.monotonic() - started:.1f}s")
        return 0
    finally:
        stop_server(server)


if __name__ == "__main__":
    raise SystemExit(main())
