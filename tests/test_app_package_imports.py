"""app.server imports cleanly without a Streamlit ui/ package on the path."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_app_server_imports_without_ui_package():
    # Ensure a stale ui module is not required.
    sys.modules.pop("ui", None)
    for name in list(sys.modules):
        if name.startswith("ui."):
            sys.modules.pop(name, None)

    repo = Path(__file__).resolve().parents[1]
    assert not (repo / "ui" / "streamlit_app.py").exists()

    mod = importlib.import_module("app.server.main")
    assert hasattr(mod, "create_app")
