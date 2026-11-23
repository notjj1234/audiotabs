"""Desktop launcher must not treat an occupied Windows port as free."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packaging"))

import launcher  # noqa: E402


def test_web_server_command_uses_app_server_module():
    assert launcher.web_server_command(8533) == [
        sys.executable,
        "-m",
        "app.server",
        "--port",
        "8533",
    ]


def test_port_free_is_false_when_something_is_listening():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        assert launcher.port_free(port) is False
    finally:
        server.close()


def test_port_free_is_true_for_unused_ephemeral_port():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    assert launcher.port_free(port) is True


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows reuse bug")
def test_port_free_detects_listener_even_with_so_reuseaddr_on_windows():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                pass
        assert launcher.port_free(port) is False
    finally:
        server.close()
