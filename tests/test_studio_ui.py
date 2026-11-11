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


def test_hero_html_is_title_only():
    from ui.studio_shell import hero_html

    html = hero_html()
    assert "studio-hero" in html
    assert "<h1>Tab PDF</h1>" in html
    assert "<p>" not in html


def test_home_page_drops_experimental_note_and_info_banner():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "studio-note" not in source
    assert "Stem separation is unavailable" not in source


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


def test_entry_screen_offers_two_sources():
    """Screen 1 is one card with two rows: upload audio, then search YouTube.

    A URL field on the entry screen would bring paste-and-fetch back; the
    search dialog owns the URL, the disclaimer, and its errors.
    """
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    entry_at = source.find('key="tab_source_entry"')
    assert entry_at != -1
    upload_at = source.find("st.file_uploader(")
    youtube_at = source.find('key="tab_youtube_search_open_btn"')
    assert upload_at != -1 and youtube_at != -1
    assert upload_at < youtube_at
    assert 'st.text_input("Or paste a YouTube URL")' not in source
    assert "@st.dialog(\"Search YouTube\"" in source
    assert "search_youtube_videos(" in source
    dialog = source[source.find("def _youtube_search_dialog") : source.find("def _render_player")]
    assert "st.caption(YOUTUBE_DISCLAIMER)" in dialog
    assert "st.warning(" in dialog
    assert "if continue_ok and st.button(" in source
    assert "disabled=not continue_ok" not in source


def test_progress_row_puts_the_state_after_the_label():
    from ui.studio_shell import progress_card_html

    html = progress_card_html([{"state": "done", "label": "Separating stems", "detail": ""}])
    assert html.find("Separating stems") < html.find(">Done<")
    assert "studio-progress-bar" in html


def test_hero_sits_on_the_ground():
    from ui.studio_theme import studio_css

    css = studio_css()
    hero = css[css.find(".studio-hero {") :]
    block = hero[: hero.find("}")]
    assert "transparent" in block


def test_studio_css_hides_streamlit_chrome():
    from ui.studio_theme import studio_css

    css = studio_css()
    assert 'data-testid="stHeader"' in css
    assert "display: none" in css


def test_score_panel_is_dark():
    from ui.studio_theme import studio_css

    css = studio_css()
    score = css[css.find(".studio-score") :]
    assert "#f4f5f7" not in score[:500]
    assert "studio-stage" in css


def test_player_waveform_and_fixed_transport():
    from audio_to_tab.player_bar import player_html

    html = player_html(peaks=[0.2, 0.8], duration=8.0, click_times=[0.0], audio_b64="")
    assert 'id="tab-wave"' in html
    assert 'class="transport"' in html
    assert "position: fixed" in html
    assert html.find('id="tab-wave"') < html.find('class="transport"')
    assert 'id="tab-loop"' in html and 'id="tab-metro"' in html


def test_result_workspace_follows_the_song_page():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    body = source[source.find("def _render_success") : source.find("def main")]
    assert '["Tab", "Chords", "Text", "Piano roll"]' in body
    assert 'key="tab_new_song"' in body
    assert body.find("result_header_html") < body.find("_render_player")
    assert body.find("_render_player") < body.find('key="tab_pdf_view"')
    assert body.find('key="tab_pdf_view"') < body.find("studio-stage")
    assert "ink=" in body


def test_entry_form_stays_off_the_run_and_the_song():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    main = source[source.find("\ndef main") :]
    assert main.find("tab_pdf_pending") < main.find("_render_entry(")
    assert main.find("tab_pdf_artifacts") < main.find("_render_entry(")


def test_setup_controls_sit_ahead_of_advanced():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    entry = source[source.find("def _render_entry") : source.find("def _execute_pending")]
    advanced = entry.find('st.expander(\n        "Advanced"')
    if advanced < 0:
        advanced = entry.find('st.expander("Advanced"')
    assert advanced > 0
    assert entry.find('key="tab_setup_tuning"') < advanced
    assert entry.find('key="tab_separate_stems"') < advanced
    assert advanced < entry.find('key="tab_max_duration_sec"')


def test_entry_screen_css_has_one_hierarchy():
    from ui.studio_theme import studio_css

    css = studio_css()
    tile = css[css.find("Tab PDF entry:") :]
    assert tile
    assert "tab_source_entry" in tile
    assert "36rem" in tile
    assert "min-height: 5.5rem" in tile
    assert "min-height: 3.5rem" in tile
    assert "1px solid" in tile
    assert "1px dashed" not in tile
    assert "Upload audio" in tile
    assert "MP3, WAV, M4A, FLAC" in tile
    assert "Public videos only" in tile
