"""Dark studio theme tokens and Streamlit CSS injection."""

from __future__ import annotations

import streamlit as st

STUDIO_TOKENS: dict[str, str] = {
    "bg": "#0f1115",
    "panel": "#171a21",
    "line": "#2a2f3a",
    "text": "#e8eaef",
    "muted": "#9aa3b2",
    "accent": "#e8a317",
}


def studio_css() -> str:
    t = STUDIO_TOKENS
    return f"""
<style>
:root {{
  --studio-bg: {t["bg"]};
  --studio-panel: {t["panel"]};
  --studio-line: {t["line"]};
  --studio-text: {t["text"]};
  --studio-muted: {t["muted"]};
  --studio-accent: {t["accent"]};
}}
.stApp, [data-testid="stAppViewContainer"] {{
  background: var(--studio-bg);
  color: var(--studio-text);
}}
[data-testid="stHeader"] {{
  background: transparent;
}}
[data-testid="stToolbar"] {{
  right: 0.75rem;
}}
.block-container {{
  padding-top: 1.25rem;
  padding-bottom: 4rem;
  max-width: 1180px;
}}
h1, h2, h3, .stMarkdown, .stCaption, label, p {{
  color: var(--studio-text) !important;
}}
[data-testid="stCaptionContainer"] p {{
  color: var(--studio-muted) !important;
}}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
.stTextInput input, .stNumberInput input {{
  background: var(--studio-panel) !important;
  color: var(--studio-text) !important;
  border-color: var(--studio-line) !important;
}}
.stButton > button {{
  border-radius: 8px;
  border: 1px solid var(--studio-line);
  background: var(--studio-panel);
  color: var(--studio-text);
}}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {{
  background: var(--studio-accent) !important;
  color: #111 !important;
  border-color: var(--studio-accent) !important;
  font-weight: 600;
}}
[data-testid="stFileUploaderDropzone"] {{
  background: var(--studio-panel) !important;
  border: 1px dashed var(--studio-line) !important;
  border-radius: 10px !important;
}}
[data-testid="stExpander"] {{
  background: var(--studio-panel);
  border: 1px solid var(--studio-line);
  border-radius: 10px;
}}
.studio-hero, .studio-progress, .studio-result-header {{
  background: var(--studio-panel);
  border: 1px solid var(--studio-line);
  border-radius: 10px;
  padding: 1.1rem 1.25rem;
  margin: 0 0 1rem 0;
}}
.studio-hero h1 {{
  margin: 0 0 0.35rem 0;
  font-size: 1.65rem;
  font-weight: 650;
  letter-spacing: -0.02em;
}}
.studio-hero p {{
  margin: 0;
  color: var(--studio-muted) !important;
  max-width: 42rem;
}}
.studio-progress h3 {{
  margin: 0 0 0.75rem 0;
  font-size: 0.95rem;
  font-weight: 600;
}}
.studio-progress ul {{
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.45rem;
}}
.studio-progress li {{
  display: flex;
  gap: 0.65rem;
  align-items: baseline;
  font-size: 0.92rem;
}}
.studio-progress .state {{
  min-width: 4.5rem;
  font-weight: 600;
  color: var(--studio-muted);
}}
.studio-progress .state.done {{ color: var(--studio-accent); }}
.studio-progress .state.active {{ color: var(--studio-text); }}
.studio-progress .state.skipped {{ color: var(--studio-muted); opacity: 0.85; }}
.studio-result-header h2 {{
  margin: 0 0 0.55rem 0;
  font-size: 1.35rem;
  font-weight: 650;
  letter-spacing: -0.02em;
}}
.studio-result-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  color: var(--studio-muted) !important;
  font-size: 0.88rem;
}}
.studio-result-meta strong {{
  color: var(--studio-text);
  font-weight: 600;
}}
.studio-note {{
  color: var(--studio-muted) !important;
  font-size: 0.88rem;
  margin: 0 0 1rem 0;
}}
.studio-score {{
  background: #f4f5f7;
  color: #111;
  border: 1px solid var(--studio-line);
  border-radius: 10px;
  padding: 1rem 1.1rem;
  overflow-x: auto;
  margin: 0 0 1rem 0;
}}
.studio-score pre, .studio-score code {{
  color: #111 !important;
  background: transparent !important;
}}
.studio-rail {{
  background: var(--studio-panel);
  border: 1px solid var(--studio-line);
  border-radius: 10px;
  padding: 0.85rem 0.9rem;
}}
.studio-rail h4 {{
  margin: 0 0 0.65rem 0;
  font-size: 0.8rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--studio-muted) !important;
}}
.studio-rail .diagram {{
  background: #f4f5f7;
  border-radius: 8px;
  padding: 0.45rem;
  margin: 0 0 0.55rem 0;
}}
</style>
"""


def inject_studio_theme() -> None:
    st.markdown(studio_css(), unsafe_allow_html=True)
