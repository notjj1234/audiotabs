"""Streamlit surface for the lead/rhythm split mode."""

from __future__ import annotations

from audio_to_tab.tab_bundle import download_menu
from ui.guitar_engines import (
    TRACK_OPTIONS,
    guitar_track_radio_ids,
    normalize_guitar_track_selection,
)
from ui.tab_pdf import _tab_model_from_guitar_engine

NEW_ID = "guitar_lead_rhythm_split"


def test_radio_includes_new_engine_only_when_available():
    assert NEW_ID in guitar_track_radio_ids(roformer_available=True, lead_rhythm_available=True)
    assert NEW_ID not in guitar_track_radio_ids(roformer_available=True, lead_rhythm_available=False)
    # Existing callers (no kwarg) keep seeing it: default True.
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
    assert _tab_model_from_guitar_engine(NEW_ID) == ("lead_rhythm_split", False)


def test_download_menu_includes_new_artifacts(tmp_path):
    fake = {
        "musicxml": tmp_path / "score.musicxml",
        "stems_midi": tmp_path / "stems.mid",
        "lead_tab": tmp_path / "lead" / "transcription.tab",
        "lead_guitar": tmp_path / "lead_guitar.wav",
    }
    fake["musicxml"].write_text("<score-partwise/>", encoding="utf-8")
    fake["stems_midi"].write_bytes(b"MThd")
    fake["lead_tab"].parent.mkdir(parents=True)
    fake["lead_tab"].write_text("e|--0--", encoding="utf-8")
    fake["lead_guitar"].write_bytes(b"RIFF")
    items = download_menu(fake)
    by_key = {item["key"]: item for item in items}
    assert by_key["musicxml"]["mime"] == "application/vnd.recordare.musicxml+xml"
    assert by_key["stems_midi"]["label"] == "Stems MIDI"
    assert by_key["lead_tab"]["mime"] == "text/plain"
    assert by_key["lead_guitar"]["label"] == "Lead guitar stem"
