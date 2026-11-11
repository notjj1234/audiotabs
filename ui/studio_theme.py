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
/* Tab PDF entry: one card, two rows. Upload is primary; search is quieter. */
.st-key-tab_source_entry {{
  width: min(36rem, 100%);
  max-width: 36rem;
  margin: 2.5rem auto 1.25rem auto;
}}
.st-key-tab_source_entry [data-testid="stWidgetLabel"] {{
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] {{
  box-sizing: border-box !important;
  min-height: 5.5rem !important;
  border-radius: 10px !important;
  border: 1px solid color-mix(in srgb, var(--studio-accent) 55%, transparent) !important;
  background: color-mix(in srgb, var(--studio-accent) 6%, var(--studio-panel)) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 1rem !important;
  padding: 1rem 1.5rem !important;
  cursor: pointer;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] > :not(input):not([data-testid="stFileUploaderDropzoneInstructions"]) {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: flex-start !important;
  flex: 0 0 2.5rem !important;
  width: 2.5rem !important;
  min-width: 2.5rem !important;
  max-width: 2.5rem !important;
  height: auto !important;
  margin: 0 !important;
  gap: 0 !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"]:hover {{
  border-color: color-mix(in srgb, var(--studio-accent) 80%, var(--studio-text)) !important;
  background: color-mix(in srgb, var(--studio-accent) 10%, var(--studio-panel)) !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"]:focus-within {{
  outline: 2px solid var(--studio-accent) !important;
  outline-offset: 3px !important;
}}
/* Browse files becomes a round plus; its label is hidden. */
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] {{
  width: 2.5rem !important;
  min-width: 2.5rem !important;
  height: 2.5rem !important;
  min-height: 2.5rem !important;
  padding: 0 !important;
  border: 0 !important;
  border-radius: 999px !important;
  box-shadow: none !important;
  color: transparent !important;
  background:
    linear-gradient(var(--studio-accent), var(--studio-accent)) center / 0.85rem 2px no-repeat,
    linear-gradient(var(--studio-accent), var(--studio-accent)) center / 2px 0.85rem no-repeat,
    color-mix(in srgb, var(--studio-text) 12%, transparent) !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] * {{
  opacity: 0 !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzoneInstructions"] {{
  display: flex !important;
  flex: 0 1 auto !important;
  align-self: center !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  justify-content: center !important;
  width: auto !important;
  gap: 0.15rem !important;
  margin: 0 !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzoneInstructions"] > * {{
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzoneInstructions"]::before {{
  content: "Upload audio";
  font-size: 1rem;
  font-weight: 650;
  line-height: 1.3;
  color: var(--studio-text);
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzoneInstructions"]::after {{
  content: "MP3, WAV, M4A, FLAC";
  font-size: 0.82rem;
  font-weight: 450;
  line-height: 1.3;
  color: var(--studio-muted);
}}
/* Secondary row: search YouTube. */
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button {{
  box-sizing: border-box !important;
  min-height: 3.5rem !important;
  height: auto !important;
  width: 100% !important;
  border-radius: 10px !important;
  border: 1px solid var(--studio-line) !important;
  background: var(--studio-panel) !important;
  color: var(--studio-text) !important;
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 1rem !important;
  padding: 0.75rem 1.5rem !important;
  white-space: normal !important;
  font-size: 0.95rem !important;
  font-weight: 600 !important;
  box-shadow: none !important;
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button > * {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 1rem !important;
  margin: 0 !important;
  width: auto !important;
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button::before {{
  content: "▶";
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  flex: 0 0 2rem;
  border-radius: 999px;
  font-size: 0.62rem;
  line-height: 1;
  color: color-mix(in srgb, var(--studio-text) 70%, transparent);
  background: color-mix(in srgb, var(--studio-text) 10%, transparent);
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button:hover {{
  border-color: color-mix(in srgb, var(--studio-accent) 45%, var(--studio-line)) !important;
  background: color-mix(in srgb, var(--studio-accent) 5%, var(--studio-panel)) !important;
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button:focus-visible {{
  outline: 2px solid var(--studio-accent) !important;
  outline-offset: 3px !important;
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button p {{
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  width: auto !important;
  margin: 0 !important;
  text-align: left !important;
  white-space: normal !important;
  font-size: 0.95rem !important;
  font-weight: 600 !important;
  line-height: 1.3 !important;
  color: var(--studio-text) !important;
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button p::after {{
  content: "Public videos only";
  display: block;
  margin-top: 0.15rem;
  font-size: 0.78rem;
  font-weight: 450;
  line-height: 1.3;
  color: var(--studio-muted);
}}
.st-key-tab_source_entry .st-key-tab_convert button {{
  width: 100% !important;
}}
@media (max-width: 640px) {{
  .st-key-tab_source_entry {{
    width: 100%;
    max-width: 100%;
    margin: 1rem auto 0.75rem auto;
  }}
  .st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] {{
    min-height: 5rem !important;
    padding: 0.9rem 1rem !important;
  }}
  .st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button {{
    min-height: 3.25rem !important;
    padding: 0.7rem 1rem !important;
  }}
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
