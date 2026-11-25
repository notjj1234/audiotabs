"""Structured tab payload for the interactive viewer (tracks, bars, beats, rhythm, techniques)."""

import json
from pathlib import Path

import pretty_midi
import pytest

from app.server.score import build_score, regular_grid, tab_measures
from app.server.store import RunRecord


def _midi(path: Path, notes: list[tuple[int, float, float]]) -> Path:
    music = pretty_midi.PrettyMIDI(initial_tempo=120)
    guitar = pretty_midi.Instrument(program=25)
    for pitch, start, end in notes:
        guitar.notes.append(pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=end))
    music.instruments.append(guitar)
    music.write(str(path))
    return path


def _result(path: Path, **extra) -> Path:
    payload = {
        "title": "Song",
        "key": "C",
        "tempo_bpm": 120.0,
        "duration_sec": 4.0,
        "tuning_name": "Standard (EADGBE)",
        "capo": 0,
        "transpose": 0,
        "bars_per_line": 4,
        "beats_per_measure": 4,
        "tempo_confidence": "high",
    }
    payload.update(extra)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _record(run_dir: Path, artifacts: dict[str, Path]) -> RunRecord:
    return RunRecord(
        id=run_dir.name,
        dir=run_dir,
        title="Song",
        created_at=0.0,
        artifacts=artifacts,
        details={},
        feedback=None,
        source=None,
        config=None,
    )


def test_regular_grid_fills_holes_and_runs_to_the_end():
    grid, length = regular_grid([0.0, 0.5, 1.0, 2.5, 3.0], 4.0)
    assert length == pytest.approx(0.5)
    assert grid == pytest.approx([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])


def test_measures_follow_detected_beats_and_downbeats():
    beats = [0.3 + 0.5 * i for i in range(16)]
    downbeats = [0.8, 2.8, 4.8, 6.8]  # bars start on the 2nd detected beat
    measures = tab_measures(
        beats=beats, downbeats=downbeats, tempo_bpm=120.0, beats_per_measure=4, end_time=8.0
    )
    starts = [m["start"] for m in measures]
    assert starts[:4] == pytest.approx([0.0, 0.8, 2.8, 4.8])  # pickup bar, then downbeats
    assert all(m["end"] > m["start"] for m in measures)
    assert measures[-1]["end"] >= 8.0


def test_measures_fall_back_to_fixed_tempo_without_beats():
    measures = tab_measures(
        beats=[], downbeats=[], tempo_bpm=120.0, beats_per_measure=4, end_time=5.0
    )
    assert [m["start"] for m in measures] == pytest.approx([0.0, 2.0, 4.0])


def test_single_guitar_run_returns_one_ai_track(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    midi = _midi(run_dir / "notes.mid", [(52, 0.0, 0.5), (55, 0.5, 1.0), (59, 2.0, 4.0)])
    record = _record(run_dir, {"midi": midi, "result": _result(run_dir / "result.json")})
    score = build_score(record, view="staff")
    tab = score["tab"]
    assert tab["ai_generated"] is True
    assert tab["tuning"] == ["E", "A", "D", "G", "B", "e"]
    assert [t["id"] for t in tab["tracks"]] == ["combined"]
    assert [m["start"] for m in tab["measures"]] == pytest.approx([0.0, 2.0])
    events = tab["tracks"][0]["events"]
    assert [e["measure"] for e in events] == [0, 0, 1]
    assert events[0]["rhythm"]["type"] == "quarter"  # 0.5 s at 120 BPM
    assert events[2]["rhythm"]["type"] == "whole"
    assert all("techniques" not in e for e in events)


def test_other_views_do_not_build_the_tab_payload(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    midi = _midi(run_dir / "notes.mid", [(52, 0.0, 0.5)])
    record = _record(run_dir, {"midi": midi, "result": _result(run_dir / "result.json")})
    assert build_score(record, view="text")["tab"] is None


def test_lead_rhythm_run_gets_a_track_per_stem_with_saved_techniques(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "lead").mkdir(parents=True)
    (run_dir / "rhythm").mkdir()
    lead = _midi(run_dir / "lead.mid", [(64, 0.0, 0.25), (66, 0.25, 0.5), (67, 1.0, 1.5)])
    rhythm = _midi(run_dir / "rhythm.mid", [(40, 0.0, 1.0), (47, 0.0, 1.0)])
    combined = _midi(run_dir / "stems.mid", [(64, 0.0, 0.25), (40, 0.0, 1.0)])
    notes = run_dir / "lead_rhythm_notes.json"
    notes.write_text(
        json.dumps(
            {
                "lead": {
                    "techniques": [
                        {"kind": "hammer_on", "start": 0.0, "end": 0.5, "confidence": "medium"},
                        {"kind": "bend", "start": 1.0, "end": 1.5, "confidence": "low"},
                    ]
                },
                "rhythm": {
                    "techniques": [
                        {"kind": "palm_mute", "start": 0.0, "end": 1.0, "confidence": "low"}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    record = _record(
        run_dir,
        {
            "midi": combined,
            "result": _result(run_dir / "result.json"),
            "lead_midi": lead,
            "lead_result": _result(run_dir / "lead" / "result.json"),
            "rhythm_midi": rhythm,
            "rhythm_result": _result(run_dir / "rhythm" / "result.json"),
            "lead_rhythm_notes": notes,
        },
    )
    tab = build_score(record, view="staff")["tab"]
    assert [t["id"] for t in tab["tracks"]] == ["lead", "rhythm"]
    lead_events = tab["tracks"][0]["events"]
    # The hammer-on joins note 1 to note 2, so the mark sits on note 2.
    assert lead_events[1].get("techniques") == ["hammer_on"]
    # Bends are never drawn from guessed data.
    assert all("bend" not in e.get("techniques", []) for e in lead_events)
    assert tab["tracks"][1]["events"][0].get("techniques") == ["palm_mute"]
