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
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu,
footer {{
  display: none !important;
}}
.stApp {{
  scrollbar-color: var(--studio-line) var(--studio-bg);
}}
.stApp ::selection {{
  background: var(--studio-accent);
  color: #111;
}}
.stApp :focus-visible {{
  outline: 2px solid var(--studio-accent);
  outline-offset: 2px;
}}
.block-container {{
  padding-top: 0.85rem;
  padding-bottom: 5.5rem;
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
  margin: 0.35rem auto 1.25rem auto;
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
.studio-hero {{
  background: transparent;
  border: 0;
  text-align: center;
  padding: 0;
  margin: 12vh auto 0.85rem;
  max-width: 36rem;
}}
.studio-hero-icon {{
  display: block;
  width: 72px;
  height: 72px;
  margin: 0 auto 0.85rem;
  border-radius: 14px;
  object-fit: contain;
  background: #fff;
}}
.studio-hero h1 {{
  margin: 0;
  font-size: 1.85rem;
  font-weight: 680;
  letter-spacing: -0.03em;
}}
.studio-run-title {{
  width: min(40rem, 100%);
  margin: 3.25rem auto 0.85rem;
}}
.studio-run-title h1 {{
  margin: 0;
  font-size: 1.7rem;
  font-weight: 650;
  letter-spacing: -0.03em;
}}
.studio-progress {{
  width: min(40rem, 100%);
  margin: 0 auto 1rem;
  background: var(--studio-panel);
  border: 1px solid var(--studio-line);
  border-radius: 10px;
  padding: 1rem 1.1rem 0.85rem;
}}
.studio-progress .head {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0 0 0.75rem;
}}
.studio-progress .pct {{
  display: grid;
  place-items: center;
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 999px;
  border: 2px solid var(--studio-accent);
  color: var(--studio-accent);
  font-size: 0.68rem;
  font-weight: 700;
}}
.studio-progress h3 {{
  margin: 0;
  font-size: 1rem;
  font-weight: 650;
}}
.studio-progress-bar {{
  height: 3px;
  background: var(--studio-line);
  border-radius: 999px;
  overflow: hidden;
  margin: 0 0 0.85rem;
}}
.studio-progress-bar span {{
  display: block;
  height: 100%;
  background: var(--studio-accent);
}}
.studio-progress ul {{
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}}
.studio-progress li {{
  display: grid;
  grid-template-columns: 0.85rem minmax(0, 1fr) auto;
  gap: 0.7rem;
  align-items: center;
  font-size: 0.92rem;
}}
.studio-progress .mark {{
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 999px;
  border: 1.5px solid var(--studio-muted);
}}
.studio-progress li.done .mark {{
  background: var(--studio-accent);
  border-color: var(--studio-accent);
}}
.studio-progress li.active .mark {{
  border-color: var(--studio-accent);
  box-shadow: inset 0 0 0 2px var(--studio-panel), inset 0 0 0 4px var(--studio-accent);
}}
.studio-progress .state {{
  font-weight: 600;
  color: var(--studio-muted);
  font-size: 0.82rem;
}}
.studio-progress .state.done {{ color: var(--studio-accent); }}
.studio-progress .state.active {{ color: var(--studio-text); }}
.studio-progress .state.skipped,
.studio-progress .state.pending {{ color: var(--studio-muted); }}
.studio-result-header {{
  background: transparent;
  border: 0;
  padding: 0.15rem 0 0.35rem;
  margin: 0 0 0.35rem;
}}
.studio-result-header h2 {{
  margin: 0 0 0.35rem 0;
  font-size: 1.85rem;
  font-weight: 650;
  letter-spacing: -0.03em;
}}
.studio-result-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.85rem;
  color: var(--studio-muted) !important;
  font-size: 0.88rem;
}}
.studio-result-meta strong {{
  color: var(--studio-text);
  font-weight: 600;
}}
.st-key-tab_pdf_view div[role="radiogroup"] {{
  gap: 0.4rem;
}}
.st-key-tab_pdf_view div[role="radiogroup"] > label {{
  background: var(--studio-panel);
  border: 1px solid var(--studio-line);
  border-radius: 8px;
  padding: 0.22rem 0.7rem;
  min-height: 2rem;
}}
.st-key-tab_pdf_view div[role="radiogroup"] > label:has(input:checked) {{
  background: var(--studio-accent);
  border-color: var(--studio-accent);
}}
.st-key-tab_pdf_view div[role="radiogroup"] > label:has(input:checked) p,
.st-key-tab_pdf_view div[role="radiogroup"] > label:has(input:checked) span,
.st-key-tab_pdf_view div[role="radiogroup"] > label:has(input:checked) div {{
  color: #111 !important;
}}
.studio-stage {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) 17rem;
  gap: 0.75rem;
  align-items: start;
  margin: 0.35rem 0 1rem;
}}
.studio-score {{
  background: var(--studio-panel);
  color: var(--studio-text);
  border: 1px solid var(--studio-line);
  border-radius: 10px;
  padding: 1.15rem 1.25rem 1.4rem;
  overflow-x: auto;
  min-height: 16rem;
}}
.studio-score .score-title {{
  margin: 0 0 1rem;
  text-align: center;
  font-size: 1.15rem;
  font-weight: 650;
}}
.studio-score .chord-names {{
  margin: 0.9rem 0 0.1rem;
  color: var(--studio-accent);
  font-weight: 650;
}}
.studio-score .lyric-line {{
  margin: 0 0 0.2rem;
  color: var(--studio-text);
}}
.studio-score pre, .studio-score code {{
  color: var(--studio-text) !important;
  background: transparent !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.78rem;
  line-height: 1.35;
}}
.studio-rail {{
  background: var(--studio-panel);
  border: 1px solid var(--studio-line);
  border-radius: 10px;
  padding: 0.85rem 0.7rem 1rem;
  max-height: 70vh;
  overflow: auto;
}}
.studio-rail h4 {{
  margin: 0 0.4rem 0.55rem;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--studio-muted) !important;
}}
.studio-rail .diagrams {{
  display: grid;
  grid-template-columns: 1fr 1fr;
}}
.studio-rail .diagram {{
  background: transparent;
  padding: 0.15rem;
  margin: 0;
}}
.st-key-tab_recent {{
  width: min(36rem, 100%);
  margin: 0.5rem auto 0;
}}
@media (max-width: 960px) {{
  .block-container {{
    padding-left: 0.85rem;
    padding-right: 0.85rem;
  }}
  .studio-stage {{
    grid-template-columns: 1fr;
  }}
  .studio-result-header h2,
  .studio-hero h1 {{
    font-size: 1.45rem;
  }}
  .studio-rail {{
    max-height: none;
  }}
}}
</style>
"""


def inject_studio_theme() -> None:
    st.markdown(studio_css(), unsafe_allow_html=True)
