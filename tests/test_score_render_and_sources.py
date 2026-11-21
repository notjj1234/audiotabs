"""Regressions for score rendering, source selection, and the Reopen crash."""

from __future__ import annotations

import json
import time
from pathlib import Path

from audio_to_tab.notation_view import chord_diagram_svg, score_playhead_html, svg_data_img
from audio_to_tab.player_bar import player_html


def test_svg_data_img_encodes_as_data_uri():
    img = svg_data_img('<svg xmlns="http://www.w3.org/2000/svg"></svg>', alt='A "quoted" tab')
    assert img.startswith('<img class="studio-score-img"')
    assert "data:image/svg+xml;base64," in img
    assert "<svg" not in img
    assert "&quot;quoted&quot;" in img


def test_chord_diagram_shipped_as_img():
    svg = chord_diagram_svg("Am", [0, 1, 2, 2, 0, None])
    img = svg_data_img(svg, alt="Am chord diagram", css_class="diagram-img")
    assert 'class="diagram-img"' in img
    assert "data:image/svg+xml;base64," in img
    assert "<svg" not in img


def test_active_source_uses_only_the_selected_tab():
    from ui.tab_pdf import _active_source

    path = Path("clip.mp3")
    youtube = "https://youtu.be/abcdefghijk"
    media = "https://cdn.example.com/song.mp3"
    # Upload selected: the file wins even with URLs present.
    assert _active_source("upload", upload_path=path, selected_url=youtube, media_url=media) == (
        path,
        "",
    )
    # YouTube selected: the picked video wins over the pasted URL.
    assert _active_source("youtube", upload_path=path, selected_url=youtube, media_url=media) == (
        None,
        youtube,
    )
    # Media URL selected: the pasted URL wins over any upload and YouTube pick.
    assert _active_source("url", upload_path=path, selected_url=youtube, media_url=media) == (
        None,
        media,
    )
    # Nothing provided on the active tab.
    assert _active_source("url", upload_path=None, selected_url="", media_url="  ") == (None, "")


def test_unique_chords_dedupes_by_name_and_frets():
    from ui.tab_pdf import _unique_chords

    hit = lambda name, frets: type("Hit", (), {"name": name, "frets": frets})()
    chords = [hit("C", [0, 1, 0, 2, 3, None]), hit("C", [0, 1, 0, 2, 3, None]), hit("G", [3, 2, 0, 0, 3, 3])]
    unique = _unique_chords(chords)
    assert [h.name for h in unique] == ["C", "G"]
    # Same name but different shape is a different chord.
    unique = _unique_chords([hit("C", [0, 1, 0, 2, 3, None]), hit("C", [None, 3, 2, 0, 1, 0])])
    assert len(unique) == 2


def test_player_speed_labels_use_multiplier_sign():
    html = player_html(peaks=[0.2], duration=8.0, click_times=[0.0], audio_b64="")
    for label in ("0.25×", "0.5×", "0.75×", "1×"):
        assert label in html
    assert "1X" not in html


def test_player_waveform_is_keyboard_focusable():
    html = player_html(peaks=[0.2], duration=8.0, click_times=[0.0], audio_b64="")
    assert 'id="tab-wave"' in html
    assert 'tabindex="0"' in html
    assert "ArrowLeft" in html and "ArrowRight" in html


def test_reopen_with_selected_source_does_not_raise(tmp_path, monkeypatch):
    """Regression: Reopen wrote tab_pdf_title after the Title widget existed."""
    import ui.common as common
    from streamlit.testing.v1 import AppTest

    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    pdf = run_dir / "song.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "page": "tab_pdf",
                "title": "Saved Song",
                "created_at": time.time(),
                "artifacts": {"pdf": str(pdf)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)

    app = Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py"
    at = AppTest.from_file(str(app), default_timeout=180)
    at.run()
    assert not at.exception

    # Pick the Media URL source and paste a direct media URL so the setup
    # block (including the Title widget) is on screen — the old crash shape.
    at.segmented_control(key="tab_source_tab").set_value("url").run()
    assert not at.exception
    at.text_input(key="tab_media_url_paste").set_value("https://cdn.example.com/song.mp3").run()
    assert not at.exception

    at.button(key=f"reopen_tab_{run_dir}").click()
    at.run()
    assert not at.exception
    assert any("Saved Song" in (m.value or "") for m in at.markdown)
