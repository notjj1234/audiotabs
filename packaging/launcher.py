"""Desktop launcher: native window over a local app server.

Dev-only entry point (`make desktop`). The web UI runs ``app.server``
(FastAPI) or, behind ``--ui streamlit``, the legacy Streamlit app; either
way the child process serves 127.0.0.1 and the parent process owns the
native pywebview window.
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
APP = REPO_ROOT / "ui" / "app.py"
PORTS = tuple(range(8501, 8511))
WINDOW_SIZE = (1280, 860)
WINDOW_MIN_SIZE = (960, 640)
WINDOW_TITLE = "Tab PDF"
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
        # Full-bleed squircles look oversized next to system apps; use inset asset.
        path = dock if dock.is_file() else (png if png.is_file() else ico)
    else:
        path = png if png.is_file() else ico
    return str(path) if path.is_file() else None


def log(message: str) -> None:
    print(f"[desktop] {message}", file=sys.stderr, flush=True)


def port_free(port: int) -> bool:
    """Return False when something already accepts connections on 127.0.0.1:port.

    A bind()+SO_REUSEADDR probe is wrong on Windows: it can succeed while an
    older Streamlit is still listening, so the desktop window opens the stale
    server (cached imports / missing symbols) instead of the one we just started.

    Connect is the reliable signal: immediate accept => busy. Refused or a
    localhost timeout (common on some Windows stacks for closed ports) => free.
    """
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
        "Close the other Tab PDF / Streamlit window and try again."
    )


def health_ok(port: int, path: str = "/_stcore/health") -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}{path}", timeout=1.5
        ) as resp:
            return 200 <= int(getattr(resp, "status", 0) or 0) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_until_healthy(
    port: int, server: subprocess.Popen, path: str = "/_stcore/health"
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


def streamlit_command(port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--server.runOnSave=false",
        "--browser.gatherUsageStats=false",
        "--browser.serverAddress=127.0.0.1",
        "--client.toolbarMode=minimal",
    ]


def start_server(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), str(REPO_ROOT), env.get("PYTHONPATH", "")]
    )
    return subprocess.Popen(
        streamlit_command(port),
        cwd=str(REPO_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
    )


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
    parser = argparse.ArgumentParser(description="Tab PDF desktop launcher")
    parser.add_argument(
        "--ui",
        choices=("streamlit", "web"),
        default="streamlit",
        help="front end to serve (default: streamlit until M2)",
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
    """Non-fatal startup probe — UI also gates Convert when ffmpeg is missing."""
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
    use_web = parse_ui(argv) == "web"
    if not use_web and not APP.is_file():
        log(f"Missing Streamlit entrypoint: {APP}")
        return 1
    try:
        import webview
    except ImportError:
        log("pywebview is not installed. Run: pip install -e '.[desktop]'")
        return 1

    _warn_if_ffmpeg_missing()
    port = pick_port()
    if use_web:
        token = secrets.token_urlsafe(32)
        log(f"Starting web server on 127.0.0.1:{port}")
        server = start_web_server(port, token)
        health_path = "/api/health"
        window_url = build_web_url(port, token)
    else:
        log(f"Starting Streamlit on 127.0.0.1:{port}")
        server = start_server(port)
        health_path = "/_stcore/health"
        window_url = f"http://127.0.0.1:{port}"
    try:
        if not wait_until_healthy(port, server, health_path):
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
