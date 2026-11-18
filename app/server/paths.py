"""Filesystem locations for the served web app, safe for frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path


def web_dist_dir() -> Path:
    """Directory holding the built front end.

    Frozen builds unpack to ``sys._MEIPASS``; source checkouts serve from the
    repo layout. An external packaging step only has to copy this folder.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "app" / "web" / "dist"
    return Path(__file__).resolve().parents[1] / "web" / "dist"
