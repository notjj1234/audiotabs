"""Studio shell theme and HTML helpers."""

from __future__ import annotations

from pathlib import Path


def test_studio_theme_defines_tokens():
    from ui.studio_theme import STUDIO_TOKENS

    assert STUDIO_TOKENS["bg"] == "#0f1115"
    assert STUDIO_TOKENS["panel"] == "#171a21"
    assert STUDIO_TOKENS["line"] == "#46505f"
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
    assert "studio-hero-icon" not in html


def test_hero_html_can_include_app_icon():
    from ui.studio_shell import hero_html

    html = hero_html(icon_data_uri="data:image/png;base64,AAA")
    assert 'class="studio-hero-icon"' in html
    assert "data:image/png;base64,AAA" in html
    assert "<h1>Tab PDF</h1>" in html


def test_home_page_drops_experimental_note_and_info_banner():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
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


def test_result_header_html_can_inline_transcription_meta():
    from ui.studio_shell import result_header_html

    html = result_header_html(
        "Demo Song",
        key="E major",
        tempo="120 BPM",
        duration="1:30",
        confidence="high",
        notes="Stem separation on; mix-aware filtering off.",
        technical="Onset threshold 0.5, frame threshold 0.3.",
    )
    assert "Confidence" in html and "high" in html
    assert "Stem separation on" in html
    assert "Onset threshold 0.5" in html
    assert "studio-result-notes" in html
    assert "studio-result-technical" in html


def test_recent_conversions_heading_html():
    from ui.studio_shell import recent_conversions_heading_html

    html = recent_conversions_heading_html()
    assert "studio-recent-heading" in html
    assert "Recent conversions" in html


def test_advanced_panel_heading_html():
    from ui.studio_shell import advanced_panel_heading_html

    html = advanced_panel_heading_html()
    assert "studio-advanced-heading" in html
    assert "Advanced" in html


def test_player_html_uses_studio_tokens():
    from audio_to_tab.player_bar import player_html

    html = player_html(peaks=[0.1, 0.5, 0.2], duration=4.0, click_times=[0.0, 0.5], audio_b64="")
    assert "tab-player" in html
    assert "studio" in html
    assert "#e8a317" in html or "#0f1115" in html
    assert "0.25" in html


def test_page_wires_studio_shell():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "inject_studio_theme" in source
    assert "progress_card_html" in source
    assert "hero_html" in source


def test_entry_screen_offers_one_explicit_source_selector():
    """Screen 1 offers one explicit source selector: Upload / YouTube / Media URL."""
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    entry_at = source.find('key="tab_source_entry"')
    assert entry_at != -1
    segmented_at = source.find("st.segmented_control(")
    upload_at = source.find("st.file_uploader(")
    youtube_at = source.find('key="tab_youtube_search_open_btn"')
    paste_at = source.find("Paste media URL")
    assert segmented_at != -1 and upload_at != -1 and youtube_at != -1 and paste_at != -1
    assert entry_at < segmented_at
    assert 'key="tab_source_tab"' in source
    assert source.find("def _active_source") != -1
    assert 'st.text_input("Or paste a YouTube URL")' not in source
    assert '@st.dialog("Search YouTube"' in source
    assert "search_youtube_videos(" in source
    dialog = source[source.find("def _youtube_search_dialog") : source.find("def _render_player")]
    assert "st.caption(YOUTUBE_DISCLAIMER)" in dialog
    assert "st.warning(" in dialog
    assert "if continue_ok:" in source
    assert "disabled=not continue_ok" not in source


def test_hero_collapse_only_when_concrete_source_selected():
    """Empty Upload/YouTube/URL tabs keep the centered hero; only a real source collapses it."""
    from ui.tab_pdf import entry_source_selected

    assert entry_source_selected(has_upload=False, media_url="", youtube_url="") is False
    assert entry_source_selected(has_upload=True, media_url="", youtube_url="") is True
    assert entry_source_selected(
        has_upload=False, media_url="", youtube_url="https://youtu.be/abcdefghijk"
    ) is True
    assert entry_source_selected(
        has_upload=False, media_url="https://cdn.example.com/song.mp3", youtube_url=""
    ) is True
    assert entry_source_selected(has_upload=False, media_url="  ", youtube_url="") is False


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


def test_player_html_draws_playhead_on_raf():
    from audio_to_tab.player_bar import player_html

    html = player_html(peaks=[0.2, 0.8], duration=8.0, click_times=[0.0], audio_b64="")
    assert "requestAnimationFrame" in html
    assert "function paint(" in html
    assert "audio.currentTime" in html
    assert "(t / total) * w" in html
    assert "#e8eaef" in html  # playhead stroke on dark waveform


def test_chords_view_uses_aligned_blocks_not_a_line_dump():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    body = source[source.find("def _render_success") : source.find("def main")]
    chords_branch = body[body.find('if view == "Chords":') : body.find('elif view == "Tab":')]
    assert "chord_lyric_blocks" in chords_branch
    assert "chord_lyric_block_html" in chords_branch
    assert "align_chords_to_lyrics(chords" not in chords_branch
    assert 'class="chord-names"' not in chords_branch.split("elif chords")[0]
    assert "chord_lyric_block_html" in source

    from ui.studio_theme import studio_css

    css = studio_css()
    assert ".chord-lyric" in css
    assert ".chord-row" in css
    assert ".lyric-row" in css
    assert "white-space: pre" in css


def test_result_workspace_follows_the_song_page():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    body = source[source.find("def _render_success") : source.find("def main")]
    assert '["Staff", "Chords", "Text", "Piano roll"]' in body
    assert 'key="tab_new_song"' in body
    assert "Playback" in body
    assert "Tab settings" in body
    assert "Score view" in body
    assert "Playing the original audio" in body
    assert "Transpose (semitones)" in body
    assert "Bars per line" in body
    assert "_unique_chords" in body
    assert "score_playhead_html" in body or "chords_playhead_html" in body
    assert 'class="score-title"' not in body
    assert body.find("result_header_html") < body.find("_render_player")
    assert body.find("_render_player") < body.find('key="tab_result_tuning"')
    assert body.find('key="tab_result_tuning"') < body.find('key="tab_pdf_view"')
    assert body.find('key="tab_pdf_view"') < body.find("studio-stage")
    assert "ink=" in body


def test_entry_form_stays_off_the_run_and_the_song():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    main = source[source.find("\ndef main") :]
    assert main.find("tab_pdf_pending") < main.find("_render_entry(")
    assert main.find("tab_pdf_artifacts") < main.find("_render_entry(")


def test_setup_controls_sit_ahead_of_advanced():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    entry = source[source.find("def _render_entry") : source.find("def _execute_pending")]
    advanced = entry.find('key="tab_advanced_toggle"')
    assert advanced > 0
    assert 'key="tab_advanced_panel"' in entry
    assert "st.expander(" not in entry
    assert entry.find('key="tab_setup_tuning"') < advanced
    assert entry.find('key="tab_separate_stems"') > advanced
    assert entry.find('key="tab_max_duration_sec"') > advanced
    assert entry.find('key="tab_expert_options"') > advanced
    assert "if continue_ok:" in entry
    # Advanced gated behind a source being present.
    assert entry.find("if continue_ok:") < advanced


def test_live_tab_pdf_has_no_streamlit_expanders():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "st.expander(" not in source
    assert "recent_conversions_heading_html" in source
    assert 'list_recent_runs("tab_pdf", limit=5)' in source
    assert "tab_show_advanced" in source
    assert 'key="tab_error_detail"' in source


def test_studio_css_styles_fixed_panels():
    from ui.studio_theme import studio_css

    css = studio_css()
    assert ".studio-recent-heading" in css
    assert ".st-key-tab_advanced_panel" in css
    assert ".st-key-tab_advanced_toggle" in css
    assert 'data-testid="stExpander"' not in css


def test_entry_stack_uses_one_vertical_rhythm():
    from ui.studio_theme import studio_css

    css = studio_css()
    assert "--studio-stack: 0.75rem" in css
    assert "gap: var(--studio-stack) !important" in css
    source = css[css.find(".st-key-tab_source_entry {") :]
    source_block = source[: source.find("}")]
    assert "margin: 0 auto" in source_block
    assert "1.25rem" not in source_block
    recent = css[css.find(".st-key-tab_recent {") :]
    recent_block = recent[: recent.find("}")]
    assert "margin: 0 auto" in recent_block
    hero = css[css.find(".studio-hero {") :]
    hero_block = hero[: hero.find("}")]
    assert "margin: 12vh auto 0" in hero_block


def test_long_clip_player_mentions_tab_sync_unavailable():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    player = source[source.find("def _render_player") : source.find("def _capo_label")]
    assert "browser player" in player
    assert "Position on the tab is unavailable" in player


def test_entry_screen_css_has_one_hierarchy():
    from ui.studio_theme import studio_css

    css = studio_css()
    tile = css[css.find("Tab PDF entry:") :]
    assert tile
    assert "tab_source_entry" in tile
    assert "36rem" in tile
    assert "min-height: 5.5rem" in tile
    assert "height: 5.5rem !important" in tile
    assert "3.5rem" not in tile
    assert "1px solid" in tile
    assert "1px dashed" not in tile
    assert "Upload audio" in tile
    assert "MP3, WAV, M4A, FLAC" in tile
    assert "Search or pick a video" in tile
    assert "tab_media_url_paste" in tile
    assert "stSegmentedControl" in tile
    assert "button-group" in tile
    assert "flex: 1 1 0 !important" in tile
    # Shared tile chrome — upload / YouTube / URL use the same panel border.
    assert "[data-testid=\"stFileUploaderDropzone\"]" in tile
    assert ".st-key-tab_youtube_search_open_btn button" in tile
    assert "stTextInputRootElement" in tile
    assert "border: 1px solid var(--studio-line)" in tile
    assert "color-mix(in srgb, var(--studio-accent) 55%, transparent) !important;\n  background: color-mix(in srgb, var(--studio-accent) 6%" not in tile
    # Upload dropzone uses grid so icon+label center (Streamlit defaults to align-items:flex-start).
    assert "display: grid !important" in tile
    assert "grid-template-columns: 2.5rem minmax(0, 1fr) !important" in tile
    assert "align-self: center !important" in tile
    # Upload plus matches muted icon treatment — no accent glyph at rest.
    plus = tile[tile.find("stBaseButton-secondary") :]
    plus = plus[: plus.find("stFileUploaderDropzoneInstructions")]
    assert "linear-gradient(var(--studio-muted)" in plus
    assert "linear-gradient(var(--studio-accent)" not in plus
    # Segment selection must not reflow: reserved 1px transparent border + inset chrome.
    assert "border: 1px solid transparent !important" in tile
    assert "box-shadow: inset 0 0 0 1px" in tile
    # Kill Streamlit primaryColor on the entry dropzone at rest.
    assert "border-color: var(--studio-line) !important" in tile
    assert "outline: none !important" in tile
    # Old BaseWeb text-input selectors must not be the Media URL target (Streamlit 1.67+).
    assert '[data-baseweb="input"] > div' not in tile
    # Disclaimer stays in the dialog, not the empty-state tile.
    assert "Public videos only" not in tile
    assert "▶" not in tile
    assert "data:image/svg+xml" in tile


def test_active_chord_highlight_does_not_reflow():
    from ui.studio_theme import studio_css

    css = studio_css()
    block = css[css.find(".studio-score .chord-lyric.is-active") :]
    block = block[: block.find("}")]
    assert "padding" not in block
    assert "margin" not in block
    assert "box-shadow" in block


def test_score_panel_scrolls_internally():
    from ui.studio_theme import studio_css

    css = studio_css()
    block = css[css.find(".studio-score {") :]
    block = block[: block.find("}")]
    assert "max-height: 70vh" in block
    assert "overflow-y: auto" in block


def test_help_and_remove_targets_have_minimum_size():
    from ui.studio_theme import studio_css

    css = studio_css()
    assert "min-width: 24px" in css
    assert "min-height: 24px" in css


def test_entry_warns_when_roformer_over_cap():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "RoFormer limit on this machine" in source
    assert "Use Demucs instead" in source
    assert 'key="tab_switch_demucs"' in source


def test_safer_length_warning_copy_present():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "Only the first" in source and "will be transcribed" in source
    assert 'key="tab_full_track_confirm"' in source


def test_full_track_requires_confirm_checkbox():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "I understand this may be very slow / memory-heavy" in source
    assert "Confirm the full-track warning" in source


def test_expert_options_gate_thresholds():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert 'key="tab_expert_options"' in source
    assert 'key="tab_onset_threshold"' in source
    assert "Expert options" in source


def test_entry_shows_duration_and_guitar_caution():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "Best results: clean solo guitar" in source
    assert "Duration about" in source
    assert 'key="tab_trim_start_sec"' in source


def test_entry_accepts_direct_media_url_copy():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "Paste media URL" in source
    assert "is_direct_media_url" in source
    assert "download_direct_media" in source


def test_tab_pdf_uses_guitar_ft_weights_cached_not_is_file():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "guitar_ft_weights_cached()" in source
    assert "guitar_ft_weights_path().is_file()" not in source
