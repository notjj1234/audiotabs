"""Streamlit entrypoint — Tab PDF only."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from ui.common import app_version, ensure_src_path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

ensure_src_path()

st.set_page_config(
    page_title=f"Tab PDF · Studio {app_version()}",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ui.pages.tab_pdf import main as tab_pdf_main  # noqa: E402

tab_pdf_main()
