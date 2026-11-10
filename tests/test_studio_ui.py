"""Studio shell theme and HTML helpers."""

from __future__ import annotations

from pathlib import Path


def test_studio_theme_defines_tokens():
    from ui.studio_theme import STUDIO_TOKENS

    assert STUDIO_TOKENS["bg"] == "#0f1115"
    assert STUDIO_TOKENS["panel"] == "#171a21"
    assert STUDIO_TOKENS["line"] == "#2a2f3a"
    assert STUDIO_TOKENS["text"] == "#e8eaef"
    assert STUDIO_TOKENS["muted"] == "#9aa3b2"
    assert STUDIO_TOKENS["accent"] == "#e8a317"


def test_studio_css_includes_variables():
    from ui.studio_theme import studio_css

    css = studio_css()
    assert "--studio-bg: #0f1115" in css
    assert "--studio-accent: #e8a317" in css
    assert "data-testid=\"stAppViewContainer\"" in css or ".stApp" in css


def test_progress_card_html_renders_states():
    from ui.studio_shell import progress_card_html

    html = progress_card_html(
        [
            {"state": "done", "label": "Separating stems", "detail": ""},
            {"state": "active", "label": "Detecting notes", "detail": "Basic Pitch"},
            {"state": "pending", "label": "Mapping tablature", "detail": ""},
            {"state": "skipped", "label": "Extracting lyrics", "detail": "no vocal stem"},
        ]
    )
    assert "studio-progress" in html
    assert "Done" in html and "Separating stems" in html
    assert "Working" in html and "Detecting notes" in html
    assert "Waiting" in html and "Mapping tablature" in html
    assert "Skipped" in html and "no vocal stem" in html


def test_hero_html_mentions_upload():
    from ui.studio_shell import hero_html

    html = hero_html()
    assert "studio-hero" in html
    assert "audio" in html.lower() or "upload" in html.lower()


def test_result_header_html_shows_meta():
    from ui.studio_shell import result_header_html

    html = result_header_html("Demo Song", key="E major", tempo="120 BPM", duration="1:30")
    assert "Demo Song" in html
    assert "E major" in html
    assert "120 BPM" in html
    assert "1:30" in html


def test_player_html_uses_studio_tokens():
    from audio_to_tab.player_bar import player_html

    html = player_html(peaks=[0.1, 0.5, 0.2], duration=4.0, click_times=[0.0, 0.5], audio_b64="")
    assert "tab-player" in html
    assert "studio" in html
    assert "#e8a317" in html or "#0f1115" in html
    assert "0.25" in html


def test_page_wires_studio_shell():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "inject_studio_theme" in source
    assert "progress_card_html" in source
    assert "hero_html" in source
