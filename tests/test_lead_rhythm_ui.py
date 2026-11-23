"""Lead/rhythm split engine helpers (no Streamlit)."""

from __future__ import annotations

from app.helpers.guitar_engines import (
    TRACK_OPTIONS,
    guitar_track_radio_ids,
    normalize_guitar_track_selection,
)
from app.helpers.sources import tab_model_from_guitar_engine

NEW_ID = "guitar_lead_rhythm_split"


def test_radio_includes_new_engine_only_when_available():
    assert NEW_ID in guitar_track_radio_ids(roformer_available=True, lead_rhythm_available=True)
    assert NEW_ID not in guitar_track_radio_ids(roformer_available=True, lead_rhythm_available=False)
    assert NEW_ID in guitar_track_radio_ids(roformer_available=True)


def test_normalize_falls_back_when_unavailable():
    assert (
        normalize_guitar_track_selection(NEW_ID, roformer_available=True, lead_rhythm_available=False)
        == "guitar_demucs_6s"
    )
    assert (
        normalize_guitar_track_selection(NEW_ID, roformer_available=True, lead_rhythm_available=True)
        == NEW_ID
    )


def test_track_option_label_documents_pipeline():
    label = TRACK_OPTIONS[NEW_ID]["label"]
    assert "listra92" in label
    assert "guitar-ft" in label


def test_engine_to_model_mapping():
    assert tab_model_from_guitar_engine(NEW_ID) == ("lead_rhythm_split", False)


def test_download_menu_includes_new_artifacts(tmp_path):
    from audio_to_tab.tab_bundle import download_menu

    fake = {
        "musicxml": tmp_path / "score.musicxml",
        "stems_midi": tmp_path / "stems.mid",
        "lead_tab": tmp_path / "lead" / "transcription.tab",
        "lead_guitar": tmp_path / "lead_guitar.wav",
    }
    for path in fake.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    labels = [item["label"] for item in download_menu(fake)]
    assert any("MusicXML" in label or "musicxml" in label.lower() for label in labels)
