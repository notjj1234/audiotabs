"""Regression: Streamlit puts ``ui/`` on sys.path ahead of the repo root.

That makes ``ui/app.py`` shadow the real ``app`` package, so
``from app.server.store import ...`` inside ``ui.common`` re-enters the
Streamlit entrypoint and raises a circular ImportError.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ui_common_imports_when_ui_dir_is_first_on_sys_path():
    """Fresh interpreter: ui/ before repo root must still import cleanly."""
    script = r"""
import importlib
import sys
from pathlib import Path

repo = Path(%r).resolve()
ui = repo / "ui"
# Streamlit adds the script directory first; repo may already be later on path.
sys.path = [str(ui), str(repo)] + [p for p in sys.path if p not in (str(ui), str(repo))]

# Drop any preloaded app/ui modules (none in a fresh process, but be explicit).
for name in list(sys.modules):
    if name == "app" or name.startswith("app.") or name == "ui" or name.startswith("ui."):
        del sys.modules[name]

from ui.common import app_icon_png, ensure_src_path

ensure_src_path()
path = app_icon_png()
assert path.name == "app-icon.png", path

import app
import app.server.store as store

assert Path(app.__file__).resolve() == (repo / "app" / "__init__.py").resolve(), app.__file__
assert hasattr(store, "default_data_dir")
assert callable(app_icon_png)
print("OK")
""" % str(REPO_ROOT)

    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "OK" in proc.stdout


def test_streamlit_entrypoint_filename_does_not_shadow_app_package():
    """Entrypoint must not be named app.py while living under a path-added ui/."""
    ui_dir = REPO_ROOT / "ui"
    assert not (ui_dir / "app.py").exists(), (
        "ui/app.py shadows the app/ package when Streamlit adds ui/ to sys.path"
    )
    entry = ui_dir / "streamlit_app.py"
    assert entry.is_file(), f"missing Streamlit entrypoint: {entry}"
