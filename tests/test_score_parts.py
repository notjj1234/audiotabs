"""Score and audio selection by Lead / Rhythm / Combined part."""

from __future__ import annotations

import json
from pathlib import Path

import pretty_midi
import pytest
from fastapi.testclient import TestClient

from app.server.main import create_app
from app.server.score import available_parts, build_score, resolve_part_paths
from app.server.store import write_run_metadata

_TOKEN = {"X-Tab-Token": "t"}


def _write_midi(path: Path, pitches: list[int]) -> None:
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=25)
    for i, pitch in enumerate(pitches):
        start = 0.1 + i * 0.4
        inst.notes.append(pretty_midi.Note(100, pitch, start, start + 0.3))
    pm.instruments.append(inst)
    path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(path))


def _seed_lead_rhythm_run(data_dir: Path, run_id: str = "lr-1") -> Path:
    run_dir = data_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    lead_dir = run_dir / "lead"
    rhythm_dir = run_dir / "rhythm"
    combined_midi = run_dir / "stems.mid"
    lead_midi = run_dir / "lead.mid"
    rhythm_midi = run_dir / "rhythm.mid"
    # Distinct pitch sets so part=lead cannot match rhythm frets from combined.
    _write_midi(combined_midi, [40, 45, 64, 67])
    _write_midi(lead_midi, [64, 67, 71])
    _write_midi(rhythm_midi, [40, 45, 47])
    result = {
        "title": "Song",
        "key": "C major",
        "tempo_bpm": 120.0,
        "tempo_confidence": "high",
        "duration_sec": 4.0,
        "tuning_name": "Standard (EADGBE)",
        "capo": 0,
        "transpose": 0,
        "bars_per_line": 4,
        "beats_per_measure": 4,
        "chords": [],
        "lyrics": [],
        "lyrics_status": "",
    }
    (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (lead_dir).mkdir(parents=True, exist_ok=True)
    (rhythm_dir).mkdir(parents=True, exist_ok=True)
    lead_result = dict(result)
    lead_result["title"] = "Song (Lead)"
    rhythm_result = dict(result)
    rhythm_result["title"] = "Song (Rhythm)"
    (lead_dir / "result.json").write_text(json.dumps(lead_result), encoding="utf-8")
    (rhythm_dir / "result.json").write_text(json.dumps(rhythm_result), encoding="utf-8")
    (run_dir / "lead_guitar.wav").write_bytes(b"RIFF" + b"\x00" * 40)
    (run_dir / "rhythm_guitar.wav").write_bytes(b"RIFF" + b"\x00" * 40)
    (run_dir / "playback.wav").write_bytes(b"RIFF" + b"\x00" * 40)
    write_run_metadata(
        run_dir,
        page="tab_pdf",
        title="Song",
        artifacts={
            "midi": combined_midi,
            "result": run_dir / "result.json",
            "lead_midi": lead_midi,
            "rhythm_midi": rhythm_midi,
            "lead_result": lead_dir / "result.json",
            "rhythm_result": rhythm_dir / "result.json",
            "lead_guitar": run_dir / "lead_guitar.wav",
            "rhythm_guitar": run_dir / "rhythm_guitar.wav",
            "playback": run_dir / "playback.wav",
        },
    )
    return run_dir


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, token="t"))


def test_available_parts_lists_lead_rhythm_combined(tmp_path):
    _seed_lead_rhythm_run(tmp_path)
    from app.server.store import get_run

    record = get_run(tmp_path, "lr-1")
    assert available_parts(record) == ["lead", "rhythm", "combined"]


def test_available_parts_combined_only_without_stems(tmp_path):
    run_dir = tmp_path / "solo"
    run_dir.mkdir()
    midi = run_dir / "out.mid"
    _write_midi(midi, [60, 64, 67])
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "title": "Solo",
                "key": "C major",
                "tempo_bpm": 100.0,
                "tempo_confidence": "high",
                "duration_sec": 2.0,
                "tuning_name": "Standard (EADGBE)",
                "capo": 0,
                "transpose": 0,
                "bars_per_line": 4,
                "beats_per_measure": 4,
                "chords": [],
                "lyrics": [],
                "lyrics_status": "",
            }
        ),
        encoding="utf-8",
    )
    write_run_metadata(
        run_dir,
        page="tab_pdf",
        title="Solo",
        artifacts={"midi": midi, "result": run_dir / "result.json"},
    )
    from app.server.store import get_run

    record = get_run(tmp_path, "solo")
    assert available_parts(record) == ["combined"]


def test_resolve_part_paths_selects_lead_midi(tmp_path):
    _seed_lead_rhythm_run(tmp_path)
    from app.server.store import get_run

    record = get_run(tmp_path, "lr-1")
    midi, result = resolve_part_paths(record, "lead")
    assert midi.name == "lead.mid"
    assert result.parent.name == "lead"


def test_build_score_part_lead_uses_lead_result_title(tmp_path):
    _seed_lead_rhythm_run(tmp_path)
    from app.server.store import get_run

    record = get_run(tmp_path, "lr-1")
    score = build_score(record, view="staff", part="lead")
    assert score["part"] == "lead"
    assert score["parts"] == ["lead", "rhythm", "combined"]
    assert "Lead" in score["meta"]["title"]


def test_api_score_part_query(client, tmp_path):
    _seed_lead_rhythm_run(tmp_path)
    r = client.get("/api/runs/lr-1/score?part=rhythm", headers=_TOKEN)
    assert r.status_code == 200
    body = r.json()
    assert body["part"] == "rhythm"
    assert "Rhythm" in body["meta"]["title"]
    assert body["parts"] == ["lead", "rhythm", "combined"]


def test_api_audio_lead_and_rhythm(client, tmp_path):
    _seed_lead_rhythm_run(tmp_path)
    for kind in ("lead", "rhythm", "original"):
        r = client.get(f"/api/runs/lr-1/audio?kind={kind}", headers=_TOKEN)
        assert r.status_code == 200, kind
