"""Visual-system contract for the Svelte shell (replaces Streamlit chrome CSS tests)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_CSS = ROOT / "app" / "web" / "src" / "app.css"
RESULT_SVELTE = ROOT / "app" / "web" / "src" / "lib" / "screens" / "Result.svelte"


def test_app_css_uses_satoshi_and_home_accent():
    css = APP_CSS.read_text(encoding="utf-8")
    assert "font-family: 'Satoshi'" in css or 'font-family: "Satoshi"' in css
    assert "--accent: #f6ad49" in css.lower() or "--accent: #F6AD49" in css
    assert "--bg: #192542" in css
    assert "home-bar-slide" in css
    assert "@keyframes spin" in css
    assert "--content-max: 800px" in css
    assert "--gutter: 48px" in css
    assert "--weight-semibold: 500" in css
    assert "--shadow-transport:" in css


def test_web_css_has_no_streamlit_selectors():
    css = APP_CSS.read_text(encoding="utf-8")
    for needle in (
        'data-testid="stAppViewContainer"',
        "stHeader",
        "stToolbar",
        "#MainMenu",
        "stAppViewContainer",
    ):
        assert needle not in css


def test_result_score_panel_uses_deeper_art_mix():
    source = RESULT_SVELTE.read_text(encoding="utf-8")
    assert "color-mix(in srgb, var(--art) 72%, var(--surface))" in source


def test_result_defaults_to_four_bars_per_line():
    """Practice default: 4 measures/line so fewer rows and less scroll."""
    source = RESULT_SVELTE.read_text(encoding="utf-8")
    assert "let bars = $state(4)" in source
    assert "let bars = $state(2)" not in source


def test_result_audio_load_avoids_effect_cycle():
    """Listen $effect must not re-subscribe via audioSrc (infinite /audio storm)."""
    source = RESULT_SVELTE.read_text(encoding="utf-8")
    assert "untrack" in source
    assert "shouldApplyAudioResult" in source
    assert "audioPending" in source


def test_result_score_is_immersive_with_floating_controls():
    source = RESULT_SVELTE.read_text(encoding="utf-8")
    assert 'class="score-stage"' in source or "score-stage" in source
    assert "panelOpen" in source or "controlsOpen" in source
    assert "grid-template-columns: 1fr 240px" not in source
    assert "width: 100%" in source
    assert "overflow-x: hidden" in source
    assert "--content-max: 800px" in (ROOT / "app" / "web" / "src" / "app.css").read_text(
        encoding="utf-8"
    )


def test_tab_staff_svg_is_fluid_width():
    from audio_to_tab.notation_view import tab_staff_svg
    from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote

    doc = TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[TabNote(start=0.0, end=0.5, string=0, fret=3, pitch=40)],
            )
        ],
        tempo_bpm=120.0,
    )
    svg = tab_staff_svg(doc, bars_per_line=2)
    assert 'width="100%"' in svg
    assert "preserveAspectRatio=" in svg


def test_app_shell_centers_content_column():
    app = (ROOT / "app" / "web" / "src" / "App.svelte").read_text(encoding="utf-8")
    css = (ROOT / "app" / "web" / "src" / "app.css").read_text(encoding="utf-8")
    assert "margin-left: auto" in app and "margin-right: auto" in app
    assert "max-width: var(--content-max)" in app
    assert "#app" in css
    assert "width: 100%" in css
