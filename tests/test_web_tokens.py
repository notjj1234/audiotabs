"""Visual-system contract for the Svelte shell (replaces Streamlit chrome CSS tests)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_CSS = ROOT / "app" / "web" / "src" / "app.css"


def test_app_css_uses_satoshi_and_home_accent():
    css = APP_CSS.read_text(encoding="utf-8")
    assert "font-family: 'Satoshi'" in css or 'font-family: "Satoshi"' in css
    assert "--accent: #f6ad49" in css.lower() or "--accent: #F6AD49" in css
    assert "--bg: #192542" in css
    assert "home-bar-slide" in css
    assert "@keyframes spin" in css
    assert "--content-max: 1180px" in css
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
