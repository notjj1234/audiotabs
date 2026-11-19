"""Launcher support for serving the web UI (plan Task 4)."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_LAUNCHER_PATH = Path(__file__).resolve().parents[1] / "packaging" / "launcher.py"


def _load_launcher():
    spec = importlib.util.spec_from_file_location("tabpdf_launcher", _LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = _load_launcher()


def test_build_web_url_shape():
    assert launcher.build_web_url(8533, "tok123") == "http://127.0.0.1:8533/#token=tok123"


def test_start_web_server_command_and_env(monkeypatch):
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    launcher.start_web_server(8533, "tok123")

    assert captured["cmd"] == [sys.executable, "-m", "app.server", "--port", "8533"]
    assert captured["cwd"] == str(launcher.REPO_ROOT)
    assert captured["stdin"] == subprocess.DEVNULL

    env = captured["env"]
    assert env["TABPDF_TOKEN"] == "tok123"
    parts = env["PYTHONPATH"].split(os.pathsep)
    assert str(launcher.REPO_ROOT / "src") in parts
    assert str(launcher.REPO_ROOT) in parts


def test_start_web_server_uses_module_entry(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        subprocess, "Popen", lambda cmd, **kwargs: captured.setdefault("cmd", cmd) or object()
    )
    launcher.start_web_server(8501, "t")
    cmd = captured["cmd"]
    assert cmd[1:3] == ["-m", "app.server"]


def test_ui_flag_defaults_to_streamlit():
    assert launcher.parse_ui([]) == "streamlit"


def test_ui_flag_accepts_web():
    assert launcher.parse_ui(["--ui", "web"]) == "web"
    assert launcher.parse_ui(["--ui", "streamlit"]) == "streamlit"


def test_ui_flag_rejects_unknown():
    with pytest.raises(SystemExit):
        launcher.parse_ui(["--ui", "native"])
