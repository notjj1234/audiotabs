"""Desktop launcher: native window over a local Streamlit server.

Dev-only entry point (`make desktop`). The Streamlit app runs in a child
process because Streamlit installs signal handlers that need the main thread;
the parent process owns the native pywebview window.
"""

from __future__ import annotations

import os
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
WINDOW_TITLE = "Audio to Tab"
HEALTH_TIMEOUT_SEC = 180.0
HEALTH_POLL_SEC = 0.3


def log(message: str) -> None:
    print(f"[desktop] {message}", file=sys.stderr, flush=True)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def pick_port() -> int:
    for port in PORTS:
        if port_free(port):
            return port
    raise RuntimeError(f"No free port in {PORTS[0]}-{PORTS[-1]}")


def health_ok(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/_stcore/health", timeout=1.5
        ) as resp:
            return 200 <= int(getattr(resp, "status", 0) or 0) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_until_healthy(port: int, server: subprocess.Popen) -> bool:
    deadline = time.monotonic() + HEALTH_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if health_ok(port):
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


def stop_server(server: subprocess.Popen | None) -> None:
    if server is None or server.poll() is not None:
        return
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


def main() -> int:
    if not APP.is_file():
        log(f"Missing Streamlit entrypoint: {APP}")
        return 1
    try:
        import webview
    except ImportError:
        log("pywebview is not installed. Run: pip install -e '.[desktop]'")
        return 1

    port = pick_port()
    log(f"Starting Streamlit on 127.0.0.1:{port}")
    server = start_server(port)
    try:
        if not wait_until_healthy(port, server):
            log("Streamlit never became healthy")
            return 1
        log(f"Opening native window -> http://127.0.0.1:{port}")
        window = webview.create_window(
            WINDOW_TITLE,
            f"http://127.0.0.1:{port}",
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
        webview.start()
        log(f"webview.start returned after {time.monotonic() - started:.1f}s")
        return 0
    finally:
        stop_server(server)


if __name__ == "__main__":
    raise SystemExit(main())
