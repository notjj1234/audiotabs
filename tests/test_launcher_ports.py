"""Desktop launcher must not treat an occupied Windows port as free."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packaging"))

import launcher  # noqa: E402


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
    # Bind briefly to learn a free port, then release it before probing.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    assert launcher.port_free(port) is True


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows reuse bug")
def test_port_free_detects_listener_even_with_so_reuseaddr_on_windows():
    """Regression: bind+SO_REUSEADDR falsely reported free while Streamlit listened."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        # Mimic the old probe: this bind often succeeds on Windows even though
        # ``server`` is already listening — the launcher must still say busy.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            reuse_bind_ok = True
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                reuse_bind_ok = False
        if reuse_bind_ok:
            assert launcher.port_free(port) is False
        else:
            assert launcher.port_free(port) is False
    finally:
        server.close()
