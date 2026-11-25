"""Run API for multi-part runs: saved view state, part-aware export and audio."""

from __future__ import annotations

from pathlib import Path

import pretty_midi
import pytest
from fastapi.testclient import TestClient

from app.server.main import create_app
from app.server.store import write_run_metadata
from tests.legacy_run_fixture import legacy_lead_rhythm_record
from tests.test_score_parts_generic import ALL, _parts_record
from tests.test_score_tracks import _midi

H = {"X-Tab-Token": "t"}


def _save(record) -> str:
    write_run_metadata(
        record.dir, page="tab_pdf", title="Song", artifacts=record.artifacts, details=record.details
    )
    return record.id


@pytest.fixture
def parts_run(tmp_path):
    rec = _parts_record(tmp_path / "run1", ALL)
    rec.artifacts["vocals_midi"] = _midi(rec.dir / "vocals.mid", [(66, 0.5, 1.0)])
    stem = rec.dir / "stems" / "vocals.wav"
    stem.parent.mkdir()
    stem.write_bytes(b"RIFFvocals")
    rec.artifacts["vocals_stem"] = stem
    run_id = _save(rec)
    return TestClient(create_app(data_dir=tmp_path, token="t")), run_id


def test_view_state_round_trips_and_drops_unknown_parts(parts_run):
    client, run_id = parts_run
    r = client.put(
        f"/api/runs/{run_id}/view",
        headers=H,
        json={"mode": "together", "part": "vocals", "shown": ["lead", "vocals", "kazoo"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["view"] == {"mode": "together", "part": "vocals", "shown": ["lead", "vocals"]}
    again = client.get(f"/api/runs/{run_id}", headers=H).json()
    assert again["view"] == {"mode": "together", "part": "vocals", "shown": ["lead", "vocals"]}
    assert again["details"]["parts"] == ALL


def test_view_state_rejects_bad_mode(parts_run):
    client, run_id = parts_run
    r = client.put(f"/api/runs/{run_id}/view", headers=H, json={"mode": "sideways", "part": "lead", "shown": []})
    assert r.status_code == 422


def test_export_without_part_is_unchanged_for_legacy_runs(tmp_path):
    rec = legacy_lead_rhythm_record(tmp_path / "legacy")
    run_id = _save(rec)
    client = TestClient(create_app(data_dir=tmp_path, token="t"))
    r = client.post(f"/api/runs/{run_id}/export", headers=H, json={"format": "midi"})
    assert r.status_code == 200
    assert r.content == Path(rec.artifacts["midi"]).read_bytes()


def test_export_midi_for_one_part(parts_run):
    client, run_id = parts_run
    r = client.post(f"/api/runs/{run_id}/export", headers=H, json={"format": "midi", "part": "vocals"})
    assert r.status_code == 200
    assert r.content == (Path(client.app.state.data_dir) / run_id / "vocals.mid").read_bytes()


def test_unsupported_format_for_notation_part_is_a_friendly_422(parts_run):
    client, run_id = parts_run
    r = client.post(f"/api/runs/{run_id}/export", headers=H, json={"format": "pdf", "part": "vocals"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "export_unsupported"
    assert detail["message"] == "PDF isn't available for notation parts yet; use MusicXML."


def test_export_all_shown_parts_as_one_multitrack_midi(parts_run, tmp_path):
    client, run_id = parts_run
    r = client.post(
        f"/api/runs/{run_id}/export",
        headers=H,
        json={"format": "midi", "all_shown": True, "shown": ["lead", "vocals"]},
    )
    assert r.status_code == 200
    out = tmp_path / "multi.mid"
    out.write_bytes(r.content)
    names = [inst.name for inst in pretty_midi.PrettyMIDI(str(out)).instruments]
    assert names == ["Lead guitar", "Vocals"]


def test_audio_for_a_part_stem(parts_run):
    client, run_id = parts_run
    r = client.get(f"/api/runs/{run_id}/audio", headers=H, params={"kind": "part:vocals"})
    assert r.status_code == 200
    assert r.content == b"RIFFvocals"
    missing = client.get(f"/api/runs/{run_id}/audio", headers=H, params={"kind": "part:kazoo"})
    assert missing.status_code == 404


def test_musicxml_for_notation_part_and_all_shown(parts_run):
    client, run_id = parts_run
    one = client.post(f"/api/runs/{run_id}/export", headers=H, json={"format": "musicxml", "part": "vocals"})
    assert one.status_code == 200, one.text
    assert b"<part-name>Vocals</part-name>" in one.content
    many = client.post(
        f"/api/runs/{run_id}/export", headers=H,
        json={"format": "musicxml", "all_shown": True, "shown": ["lead", "vocals", "drums"]},
    )
    assert many.status_code == 200, many.text
    for name in (b"Lead guitar", b"Vocals", b"Drums (rough)"):
        assert b"<part-name>" + name + b"</part-name>" in many.content


def test_musicxml_for_one_guitar_part_contains_only_that_part(parts_run):
    client, run_id = parts_run
    r = client.post(f"/api/runs/{run_id}/export", headers=H, json={"format": "musicxml", "part": "lead"})
    assert r.status_code == 200, r.text
    assert r.content.count(b"<part-name>") == 1
    assert b"<part-name>Lead guitar</part-name>" in r.content
