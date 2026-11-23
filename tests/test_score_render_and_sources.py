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
    from app.helpers.sources import active_source as _active_source

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
    from app.helpers.sources import unique_chords as _unique_chords

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


def test_reopen_run_is_available_via_api(tmp_path):
    """Completed runs remain readable after Streamlit removal (API reopen)."""
    from fastapi.testclient import TestClient

    from app.server.main import create_app
    from app.server.store import write_run_metadata

    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    pdf = run_dir / "song.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    write_run_metadata(
        run_dir,
        page="tab_pdf",
        title="Saved Song",
        artifacts={"pdf": str(pdf)},
    )
    client = TestClient(create_app(data_dir=tmp_path, token="t"))
    r = client.get("/api/runs/run1", headers={"X-Tab-Token": "t"})
    assert r.status_code == 200
    assert r.json()["title"] == "Saved Song"
