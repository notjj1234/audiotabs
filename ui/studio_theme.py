"""Dark studio theme tokens and Streamlit CSS injection."""

from __future__ import annotations

import streamlit as st

STUDIO_TOKENS: dict[str, str] = {
    "bg": "#0f1115",
    "panel": "#171a21",
    "line": "#46505f",
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
  --studio-stack: 0.75rem;
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
/* Hit targets: keep Streamlit chrome at or above 24x24. */
.stApp button {{
  min-width: 24px;
  min-height: 24px;
}}
.block-container {{
  padding-top: 0.5rem;
  padding-bottom: 5.5rem;
  max-width: 1180px;
}}
/* One vertical rhythm for the main column (entry + result). */
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"],
.block-container > div > [data-testid="stVerticalBlock"] {{
  gap: var(--studio-stack) !important;
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
/* Tab PDF entry: one column; switcher + source tile share the same width. */
.st-key-tab_source_entry {{
  width: min(36rem, 100%);
  max-width: 36rem;
  margin: 0 auto;
}}
.st-key-tab_source_entry > [data-testid="stVerticalBlock"] {{
  gap: var(--studio-stack) !important;
}}
.st-key-tab_source_entry [data-testid="stElementContainer"],
.st-key-tab_source_entry [data-testid="element-container"],
.st-key-tab_source_entry [data-testid="stVerticalBlockBorderWrapper"],
.st-key-tab_source_entry [data-testid="stFileUploader"],
.st-key-tab_source_entry [data-testid="stFileUploader"] section,
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn,
.st-key-tab_source_entry .st-key-tab_media_url_paste,
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInput"],
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"] {{
  width: 100% !important;
  max-width: 100% !important;
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
/* Full-width segmented switcher — same chrome on every selection. */
.st-key-tab_source_entry [data-testid="stSegmentedControl"],
.st-key-tab_source_entry [data-baseweb="button-group"] {{
  width: 100% !important;
  max-width: 100% !important;
}}
.st-key-tab_source_entry [data-testid="stSegmentedControl"] > div,
.st-key-tab_source_entry [data-baseweb="button-group"] {{
  width: 100% !important;
  display: flex !important;
  gap: 0.2rem !important;
  box-sizing: border-box !important;
  padding: 0.2rem !important;
  background: var(--studio-panel) !important;
  border: 1px solid var(--studio-line) !important;
  border-radius: 10px !important;
}}
.st-key-tab_source_entry [data-testid="stSegmentedControl"] button,
.st-key-tab_source_entry [data-baseweb="button-group"] button {{
  flex: 1 1 0 !important;
  min-width: 0 !important;
  justify-content: center !important;
  margin: 0 !important;
  border: 1px solid transparent !important;
  border-radius: 8px !important;
  background: transparent !important;
  color: var(--studio-muted) !important;
  box-shadow: none !important;
  font-weight: 600 !important;
}}
.st-key-tab_source_entry [data-testid="stSegmentedControl"] button[aria-checked="true"],
.st-key-tab_source_entry [data-testid="stSegmentedControl"] button[kind="primary"],
.st-key-tab_source_entry [data-baseweb="button-group"] button[aria-checked="true"],
.st-key-tab_source_entry [data-baseweb="button-group"] button[aria-selected="true"] {{
  background: color-mix(in srgb, var(--studio-accent) 16%, var(--studio-panel)) !important;
  color: var(--studio-text) !important;
  border-color: transparent !important;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--studio-accent) 50%, transparent) !important;
}}
/* Shared empty-state tile for upload / YouTube / Media URL (Streamlit 1.67+). */
.st-key-tab_source_entry [data-testid="stFileUploader"],
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn,
.st-key-tab_source_entry .st-key-tab_media_url_paste,
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInput"] {{
  margin: 0 !important;
  padding: 0 !important;
  gap: 0 !important;
}}
/* Only the visible chrome is a fixed tile — do not inflate outer wrappers. */
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn,
.st-key-tab_source_entry .st-key-tab_media_url_paste,
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInput"] {{
  min-height: 5.5rem !important;
  height: 5.5rem !important;
  overflow: hidden !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"],
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button,
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"] {{
  box-sizing: border-box !important;
  width: 100% !important;
  max-width: 100% !important;
  min-height: 5.5rem !important;
  height: 5.5rem !important;
  max-height: 5.5rem !important;
  border-radius: 10px !important;
  border: 1px solid var(--studio-line) !important;
  border-color: var(--studio-line) !important;
  background: var(--studio-panel) !important;
  box-shadow: none !important;
  outline: none !important;
  color: var(--studio-text) !important;
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button,
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"] {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 1rem !important;
  padding: 1rem 1.5rem !important;
}}
/* Upload dropzone: Streamlit uses align-items:flex-start — grid centers reliably. */
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] {{
  cursor: pointer;
  border-style: solid !important;
  border-color: var(--studio-line) !important;
  background-color: var(--studio-panel) !important;
  outline: none !important;
  display: grid !important;
  grid-template-columns: 2.5rem minmax(0, 1fr) !important;
  grid-template-rows: 5.5rem !important;
  align-items: center !important;
  justify-items: start !important;
  column-gap: 1rem !important;
  row-gap: 0 !important;
  padding: 0 1.5rem !important;
  gap: 1rem !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"]:hover,
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button:hover,
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"]:hover {{
  border-color: color-mix(in srgb, var(--studio-accent) 45%, var(--studio-line)) !important;
  background: color-mix(in srgb, var(--studio-accent) 5%, var(--studio-panel)) !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"]:focus-within,
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button:focus-visible,
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"]:focus-within {{
  outline: 2px solid var(--studio-accent) !important;
  outline-offset: 3px !important;
  border-color: color-mix(in srgb, var(--studio-accent) 55%, var(--studio-line)) !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] > input {{
  grid-column: 1 / -1 !important;
  grid-row: 1 !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] > span {{
  grid-column: 1 !important;
  grid-row: 1 !important;
  justify-self: center !important;
  align-self: center !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  width: 2.5rem !important;
  height: 2.5rem !important;
  margin: 0 !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] > [data-testid="stFileUploaderDropzoneInstructions"] {{
  grid-column: 2 !important;
  grid-row: 1 !important;
  justify-self: start !important;
  align-self: center !important;
}}
/* Hide Browse chrome; first grid cell carries one muted upload SVG (matches YT/URL). */
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"],
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] button {{
  visibility: hidden !important;
  width: 0 !important;
  min-width: 0 !important;
  height: 0 !important;
  min-height: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
  border: 0 !important;
  overflow: hidden !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] > span {{
  background-color: color-mix(in srgb, var(--studio-text) 12%, transparent) !important;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M8 1.5a.75.75 0 0 1 .75.75v5.19l1.72-1.72a.75.75 0 1 1 1.06 1.06l-3 3a.75.75 0 0 1-1.06 0l-3-3a.75.75 0 0 1 1.06-1.06l1.72 1.72V2.25A.75.75 0 0 1 8 1.5zM3.5 10.5a.75.75 0 0 1 .75.75v1.5h7.5v-1.5a.75.75 0 0 1 1.5 0v2.25a.75.75 0 0 1-.75.75h-9a.75.75 0 0 1-.75-.75V11.25a.75.75 0 0 1 .75-.75z' fill='%239aa3b2'/%3E%3C/svg%3E") !important;
  background-repeat: no-repeat !important;
  background-position: center !important;
  background-size: 1rem !important;
  border-radius: 999px !important;
}}
.st-key-tab_source_entry [data-testid="stFileUploaderDropzoneInstructions"] {{
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  justify-content: center !important;
  width: auto !important;
  max-width: 100% !important;
  gap: 0.15rem !important;
  margin: 0 !important;
  padding: 0 !important;
  min-width: 0 !important;
  flex: unset !important;
  align-self: center !important;
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
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button {{
  white-space: normal !important;
  font-size: 1rem !important;
  font-weight: 650 !important;
  color: var(--studio-text) !important;
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
  content: "";
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  flex: 0 0 2.5rem;
  border-radius: 999px;
  line-height: 1;
  background-color: color-mix(in srgb, var(--studio-text) 12%, transparent);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M5 3.5v9l7.5-4.5z' fill='%239aa3b2'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: center;
  background-size: 0.85rem;
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button p {{
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  gap: 0.15rem !important;
  width: auto !important;
  margin: 0 !important;
  text-align: left !important;
  white-space: normal !important;
  font-size: 1rem !important;
  font-weight: 650 !important;
  line-height: 1.3 !important;
  color: var(--studio-text) !important;
}}
.st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button p::after {{
  content: "Search or pick a video";
  font-size: 0.82rem;
  font-weight: 450;
  line-height: 1.3;
  color: var(--studio-muted);
}}
/* Media URL — Streamlit 1.67 uses stTextInputRootElement (not BaseWeb input). */
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"] {{
  padding: 0 1.5rem 0 4.5rem !important;
  position: relative !important;
  gap: 0 !important;
}}
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"]::before {{
  content: "";
  position: absolute;
  left: 1.5rem;
  top: 50%;
  transform: translateY(-50%);
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 999px;
  background-color: color-mix(in srgb, var(--studio-text) 12%, transparent);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M6.5 2.5a3 3 0 0 0-4.24 4.24l2.12 2.12a.75.75 0 0 0 1.06-1.06L3.32 5.68A1.5 1.5 0 1 1 5.44 3.56l2.12 2.12a.75.75 0 1 0 1.06-1.06L6.5 2.5zm3 11a3 3 0 0 0 4.24-4.24l-2.12-2.12a.75.75 0 0 0-1.06 1.06l2.12 2.12a1.5 1.5 0 1 1-2.12 2.12L8.44 10.32a.75.75 0 1 0-1.06 1.06L9.5 13.5zM5.97 8.97a.75.75 0 0 0 1.06 1.06l3-3a.75.75 0 1 0-1.06-1.06l-3 3z' fill='%239aa3b2'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: center;
  background-size: 1rem;
}}
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputField"] {{
  min-height: 0 !important;
  height: auto !important;
  width: 100% !important;
  font-size: 1rem !important;
  font-weight: 550 !important;
  line-height: 1.3 !important;
  color: var(--studio-text) !important;
  background: transparent !important;
  border: 0 !important;
  padding: 0 !important;
  box-shadow: none !important;
}}
.st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputField"]::placeholder {{
  color: var(--studio-muted) !important;
  opacity: 1 !important;
}}
.st-key-tab_source_entry .st-key-tab_convert button {{
  width: 100% !important;
}}
@media (max-width: 640px) {{
  .st-key-tab_source_entry {{
    width: 100%;
    max-width: 100%;
    margin: 0 auto;
  }}
  .st-key-tab_source_entry .st-key-tab_youtube_search_open_btn,
  .st-key-tab_source_entry .st-key-tab_media_url_paste,
  .st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInput"],
  .st-key-tab_source_entry [data-testid="stFileUploaderDropzone"],
  .st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button,
  .st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"] {{
    min-height: 5rem !important;
    height: 5rem !important;
    max-height: 5rem !important;
  }}
  .st-key-tab_source_entry [data-testid="stFileUploaderDropzone"] {{
    grid-template-rows: 5rem !important;
    padding: 0 1rem !important;
  }}
  .st-key-tab_source_entry .st-key-tab_youtube_search_open_btn button {{
    padding: 0.9rem 1rem !important;
  }}
  .st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"] {{
    padding: 0 1rem 0 4rem !important;
  }}
  .st-key-tab_source_entry .st-key-tab_media_url_paste [data-testid="stTextInputRootElement"]::before {{
    left: 1rem;
  }}
}}
.studio-converter-card,
.st-key-tab_source_entry {{
  width: min(40rem, 100%);
  margin: 0 auto 1rem;
  padding: 1rem 1.1rem 1.05rem;
  background: var(--studio-panel);
  border: 1px solid var(--studio-line);
  border-radius: 12px;
}}
.st-key-tab_source_entry > [data-testid="stVerticalBlock"] {{
  gap: var(--studio-stack) !important;
}}
.studio-converter-chip-name {{
  margin: 0 0 0.2rem;
  font-weight: 650;
  color: var(--studio-text);
}}
.studio-converter-chip-meta {{
  margin: 0 0 0.55rem;
  font-size: 0.78rem;
  color: var(--studio-muted);
}}
.studio-hero {{
  background: transparent;
  border: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 0;
  margin: 12vh auto 2.25rem;
  max-width: 36rem;
}}
.studio-hero-icon {{
  display: block;
  width: 72px;
  height: 72px;
  margin: 0 0 var(--studio-stack);
  border-radius: 14px;
  object-fit: contain;
  background: #fff;
}}
.studio-hero-title {{
  margin: 0;
  font-size: 1.85rem;
  font-weight: 680;
  letter-spacing: -0.03em;
  color: var(--studio-text) !important;
  line-height: 1.2;
}}
/* No Streamlit heading-link affordance on the brand title. */
.studio-hero [data-testid="stHeaderActionElements"],
.studio-hero a[href^="#"] {{
  display: none !important;
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
  flex: 1;
  min-width: 0;
}}
.studio-progress-elapsed {{
  margin-left: auto;
  color: var(--studio-muted);
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}}
.studio-progress-bar {{
  height: 3px;
  background: var(--studio-line);
  border-radius: 999px;
  overflow: hidden;
  margin: 0 0 0.85rem;
}}
.studio-progress-tip {{
  margin: -0.35rem 0 0.85rem;
  color: var(--studio-muted);
  font-size: 0.78rem;
  line-height: 1.35;
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
.studio-depth-banner {{
  margin: 0 0 0.75rem;
  padding: 0.7rem 0.85rem;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--studio-accent) 28%, var(--studio-border));
  background: color-mix(in srgb, var(--studio-accent) 8%, transparent);
}}
.studio-depth-banner-title {{
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 650;
  color: var(--studio-muted);
  margin: 0 0 0.2rem;
}}
.studio-depth-banner-copy {{
  margin: 0 0 0.35rem;
  font-size: 0.92rem;
  color: var(--studio-text);
}}
.studio-depth-banner-list {{
  margin: 0;
  padding-left: 1.1rem;
  color: var(--studio-muted);
  font-size: 0.88rem;
}}
.studio-section-label {{
  margin: 0.85rem 0 0.35rem;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--studio-muted) !important;
  font-weight: 650;
}}
.studio-score .chord-lyric.is-active {{
  border-radius: 8px;
  background: rgba(232, 163, 23, 0.08);
  box-shadow: inset 0 0 0 1px var(--studio-accent);
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
  overflow-y: auto;
  max-height: 70vh;
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
.studio-score .chord-lyric {{
  margin: 0 0 0.9rem;
}}
.studio-score .chord-row,
.studio-score .lyric-row {{
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9rem;
  line-height: 1.5;
  letter-spacing: 0;
  white-space: pre;
}}
.studio-score .chord-row {{
  color: var(--studio-accent);
  font-weight: 700;
}}
.studio-score .lyric-row {{
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
  margin: 0 auto;
  background: var(--studio-panel);
  border: 1px solid color-mix(in srgb, var(--studio-text) 10%, transparent);
  border-radius: 12px;
  padding: 16px 16px 12px;
  /* Streamlit applies st-key-* to the vertical block itself — zero that gap. */
  gap: 0 !important;
}}
.st-key-tab_recent [data-testid="stVerticalBlock"] {{
  gap: 0 !important;
}}
.studio-recent-heading {{
  margin: 0;
  padding-bottom: 16px;
}}
/* Streamlit markdown uses margin-bottom:-16px; that ate the heading→confirm gap. */
.st-key-tab_recent [data-testid="stElementContainer"]:has(.studio-recent-heading),
.st-key-tab_recent [data-testid="stElementContainer"]:has(.studio-recent-heading) [data-testid="stMarkdown"],
.st-key-tab_recent [data-testid="stElementContainer"]:has(.studio-recent-heading) [data-testid="stMarkdown"] > div,
.st-key-tab_recent [data-testid="stElementContainer"]:has(.studio-recent-heading) [data-testid="stMarkdownContainer"] {{
  height: auto !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: visible !important;
}}
.studio-recent-heading-label,
.studio-recent-heading h3 {{
  margin: 0;
  font-size: 0.8125rem;
  letter-spacing: 0;
  text-transform: none;
  font-weight: 500;
  color: var(--studio-muted) !important;
}}
.st-key-tab_recent [data-testid="stHorizontalBlock"] {{
  align-items: center !important;
  gap: 8px !important;
  min-height: 36px;
  padding: 8px 0;
  border-top: 1px solid color-mix(in srgb, var(--studio-text) 10%, transparent);
}}
div.st-key-tab_recent [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  min-height: 36px !important;
}}
div.st-key-tab_recent [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div {{
  width: 100%;
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
}}
/* Row-only height lock — never apply to alerts/confirm markdown. */
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"]),
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]),
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stMarkdown"],
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stCaption"],
.st-key-tab_recent [data-testid="stHorizontalBlock"] .stMarkdown {{
  height: 36px !important;
  min-height: 36px !important;
  display: flex !important;
  align-items: center !important;
  overflow: visible !important;
  line-height: 1 !important;
}}
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stMarkdown"] > div,
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stCaption"] > div {{
  height: 36px !important;
  display: flex !important;
  align-items: center !important;
  width: 100%;
  line-height: 1 !important;
}}
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stMarkdownContainer"],
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stCaptionContainer"] {{
  display: flex !important;
  align-items: center !important;
  justify-content: flex-start !important;
  height: 36px !important;
  width: 100%;
  margin: 0 !important;
  line-height: 1 !important;
}}
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stMarkdownContainer"] p {{
  margin: 0 !important;
  font-size: 0.875rem !important;
  line-height: 1.25 !important;
  font-weight: 400 !important;
}}
.st-key-tab_recent [data-testid="stHorizontalBlock"] [data-testid="stCaptionContainer"] p {{
  margin: 0 !important;
  font-size: 0.75rem !important;
  line-height: 1.25 !important;
  font-variant-numeric: tabular-nums;
  color: var(--studio-muted) !important;
}}
/* React Aria checkbox (Streamlit 1.55+): center mark with title/buttons. */
.st-key-tab_recent .stCheckbox,
.st-key-tab_recent [data-testid="stCheckbox"] {{
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-height: 36px !important;
  height: 36px !important;
  margin: 0 !important;
  padding: 0 !important;
}}
.st-key-tab_recent .stCheckbox label,
.st-key-tab_recent [data-testid="stCheckbox"] label {{
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 0 !important;
  min-height: 36px !important;
  height: 36px !important;
  margin: 0 !important;
  padding: 0 !important;
}}
.st-key-tab_recent .stCheckbox [data-testid="stWidgetLabel"] {{
  display: none !important;
}}
/* Visual box is the bare div sibling of the visually-hidden input span. */
.st-key-tab_recent [data-testid="stCheckbox"] label > div:not([data-testid]) {{
  width: 16px !important;
  height: 16px !important;
  min-width: 16px !important;
  min-height: 16px !important;
  margin: 0 !important;
  border-radius: 4px !important;
  border: 1px solid var(--studio-line) !important;
  background: transparent !important;
  box-shadow: none !important;
  flex-shrink: 0 !important;
}}
.st-key-tab_recent [data-testid="stCheckbox"] label:has(input:checked) > div:not([data-testid]) {{
  background: var(--studio-accent) !important;
  border-color: var(--studio-accent) !important;
}}
.st-key-tab_recent [data-testid="stCheckbox"] label > div:not([data-testid]) svg {{
  width: 12px !important;
  height: 12px !important;
  color: #111 !important;
}}
.st-key-tab_recent .stButton > button {{
  min-height: 32px !important;
  height: 32px !important;
  padding: 0 12px !important;
  font-size: 0.8125rem !important;
  font-weight: 500 !important;
  width: 100%;
  border-radius: 8px !important;
  background: transparent !important;
  border-color: color-mix(in srgb, var(--studio-text) 12%, transparent) !important;
  color: var(--studio-text) !important;
  box-shadow: none !important;
}}
.st-key-tab_recent .stButton > button:hover {{
  background: color-mix(in srgb, var(--studio-text) 6%, transparent) !important;
  border-color: var(--studio-line) !important;
}}
.st-key-tab_recent [data-testid="stAlert"] {{
  margin: 8px 0 4px !important;
}}
/* Delete confirm: natural alert height, no list-row chrome on Cancel/Delete.
   Must beat `.st-key-tab_recent [data-testid=stVerticalBlock] {{ gap: 0 }}`. */
.st-key-tab_recent_confirm,
.st-key-tab_recent_confirm[data-testid="stVerticalBlock"],
.st-key-tab_recent .st-key-tab_recent_confirm[data-testid="stVerticalBlock"] {{
  display: flex !important;
  flex-direction: column !important;
  gap: 12px !important;
  margin-top: 0;
}}
.st-key-tab_recent_confirm [data-testid="stAlert"] {{
  margin: 0 !important;
  overflow: visible !important;
  height: auto !important;
}}
.st-key-tab_recent_confirm [data-testid="stAlertContainer"] {{
  display: flex !important;
  align-items: center !important;
  height: auto !important;
  min-height: 48px !important;
  max-height: none !important;
  padding: 14px 16px !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}}
.st-key-tab_recent_confirm [data-testid="stAlertContentWarning"] {{
  display: flex !important;
  align-items: center !important;
  width: 100%;
  margin: 0 !important;
  padding: 0 !important;
}}
.st-key-tab_recent_confirm [data-testid="stElementContainer"]:has([data-testid="stAlert"]),
.st-key-tab_recent_confirm [data-testid="stAlert"],
.st-key-tab_recent_confirm [data-testid="stAlert"] > div,
.st-key-tab_recent_confirm [data-testid="stAlert"] [data-testid="stMarkdown"],
.st-key-tab_recent_confirm [data-testid="stAlert"] [data-testid="stMarkdown"] > div,
.st-key-tab_recent_confirm [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
.st-key-tab_recent_confirm [data-testid="stAlert"] .stMarkdown {{
  height: auto !important;
  min-height: 0 !important;
  max-height: none !important;
  margin: 0 !important;
  display: flex !important;
  align-items: center !important;
  overflow: visible !important;
  line-height: 1.4 !important;
}}
.st-key-tab_recent_confirm [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{
  margin: 0 !important;
  line-height: 1.4 !important;
  font-size: 0.875rem !important;
}}
.st-key-tab_recent_confirm [data-testid="stHorizontalBlock"] {{
  border-top: none !important;
  padding: 0 !important;
  min-height: 0 !important;
  align-items: stretch !important;
}}
.st-key-tab_recent_confirm [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
  min-height: 0 !important;
}}
.st-key-tab_recent_confirm .stButton > button {{
  width: 100%;
}}
/* Single footer rule: border on the footer shell, not every nested columns row. */
.st-key-tab_recent_footer {{
  border-top: 1px solid color-mix(in srgb, var(--studio-text) 10%, transparent);
  padding-top: 12px;
  margin-top: 0;
}}
.st-key-tab_recent_footer [data-testid="stHorizontalBlock"] {{
  border-top: none !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  min-height: 0 !important;
}}
.st-key-tab_recent_footer [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] {{
  border-top: none !important;
  padding: 0 !important;
  min-height: 0 !important;
}}
.st-key-tab_recent_footer .stButton > button {{
  width: auto !important;
  min-width: 0 !important;
}}
.st-key-tab_advanced_toggle {{
  width: min(36rem, 100%);
  margin: 0 auto;
}}
.st-key-tab_advanced_toggle button {{
  width: auto !important;
  min-height: 2rem !important;
  padding: 0.35rem 0.85rem !important;
  font-size: 0.95rem !important;
  font-weight: 550 !important;
  color: var(--studio-text) !important;
  background: var(--studio-panel) !important;
  border-color: var(--studio-line) !important;
}}
.st-key-tab_advanced_toggle button:hover {{
  color: var(--studio-text) !important;
  border-color: color-mix(in srgb, var(--studio-accent) 45%, var(--studio-line)) !important;
  background: color-mix(in srgb, var(--studio-accent) 5%, var(--studio-panel)) !important;
}}
.st-key-tab_advanced_panel {{
  width: min(36rem, 100%);
  margin: 0 auto;
  background: var(--studio-panel);
  border: 1px solid var(--studio-line);
  border-radius: 10px;
  padding: 0.75rem 1rem 0.85rem;
}}
.st-key-tab_advanced_panel > [data-testid="stVerticalBlock"] {{
  gap: var(--studio-stack) !important;
}}
.studio-advanced-heading {{
  width: min(36rem, 100%);
  margin: 0 auto;
}}
.studio-advanced-heading h3 {{
  margin: 0;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--studio-muted) !important;
}}
.studio-result-notes,
.studio-result-technical {{
  margin: 0.35rem 0 0 !important;
  font-size: 0.82rem !important;
  line-height: 1.35 !important;
  color: var(--studio-muted) !important;
}}
.studio-result-technical {{
  font-size: 0.75rem !important;
}}
.studio-error-detail {{
  width: min(36rem, 100%);
  margin: 0 auto;
}}
.studio-error-detail pre,
.studio-error-detail code {{
  font-size: 0.75rem !important;
  color: var(--studio-muted) !important;
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
  .studio-hero-title {{
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
