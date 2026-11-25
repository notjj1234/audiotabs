"""Generic parts model: tracks[] for every selected part; legacy runs unchanged."""

from __future__ import annotations

import json
from pathlib import Path

from app.server.score import available_parts, build_score
from app.server.store import RunRecord
from tests.legacy_run_fixture import legacy_lead_rhythm_record
from tests.test_score_tracks import _midi, _result

FIXTURES = Path(__file__).parent / "fixtures"
BEATS = [round(i * 0.5, 3) for i in range(17)]


def test_legacy_payload_is_unchanged(tmp_path):
    rec = legacy_lead_rhythm_record(tmp_path / "run")
    for part in ("lead", "combined"):
        score = build_score(rec, view="staff", part=part)
        got = {"tab": score["tab"], "part": score["part"], "parts": score["parts"]}
        want = json.loads((FIXTURES / f"legacy_score_{part}.json").read_text())
        assert json.loads(json.dumps(got, sort_keys=True)) == want


def _json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _parts_record(run_dir: Path, parts: list[str], *, guitar: bool = True) -> RunRecord:
    run_dir.mkdir(parents=True, exist_ok=True)
    arts: dict[str, Path] = {
        "result": _result(run_dir / "result.json", beats=BEATS, downbeats=[0.0, 2.0]),
        "bass_result": _json(run_dir / "bass.json", {
            "kind": "tab", "instrument": "bass", "tuning_midi": [28, 33, 38, 43],
            "tuning_names": ["E", "A", "D", "G"],
            "notes": [{"pitch": 28, "start": 0.0, "end": 0.5, "velocity": 90},
                      {"pitch": 45, "start": 2.0, "end": 2.5, "velocity": 90}],
        }),
        "vocals_result": _json(run_dir / "vocals.json", {
            "kind": "staff", "clef": "treble",
            "notes": [{"pitch": 66, "start": 0.5, "end": 1.0, "velocity": 80},
                      {"pitch": 64, "start": 2.0, "end": 3.0, "velocity": 80}],
        }),
        "keys_result": _json(run_dir / "keys.json", {
            "kind": "staff", "clef": "grand",
            "notes": [{"pitch": 48, "start": 0.0, "end": 1.0, "velocity": 70},
                      {"pitch": 64, "start": 0.0, "end": 1.0, "velocity": 70}],
        }),
        "drums_result": _json(run_dir / "drums.json", {"kind": "drums", "hits": [], "empty_reason": "No notes found in this part."}),
    }
    if guitar:
        arts.update(
            lead_midi=_midi(run_dir / "lead.mid", [(64, 0.0, 0.5), (67, 2.0, 2.5)]),
            rhythm_midi=_midi(run_dir / "rhythm.mid", [(40, 0.0, 1.0), (45, 2.0, 4.0)]),
            midi=_midi(run_dir / "stems.mid", [(64, 0.0, 0.5), (40, 0.0, 1.0)]),
            lead_result=_result(run_dir / "lead_r.json", beats=BEATS, downbeats=[0.0, 2.0]),
            rhythm_result=_result(run_dir / "rhythm_r.json", beats=BEATS, downbeats=[0.0, 2.0]),
        )
    return RunRecord(
        id=run_dir.name, dir=run_dir, title="Song", created_at=0.0, artifacts=arts,
        details={"parts": parts, "empty_parts": {"drums": "No notes found in this part."}},
        feedback=None, source=None, config=None,
    )


ALL = ["lead", "rhythm", "combined", "bass", "vocals", "keys", "drums"]


def test_every_selected_part_becomes_a_track_on_shared_measures(tmp_path):
    rec = _parts_record(tmp_path / "run", ALL)
    assert available_parts(rec) == ALL
    score = build_score(rec, view="staff")
    tab = score["tab"]
    assert [t["id"] for t in tab["tracks"]] == ALL
    assert score["part"] == "lead"
    n = len(tab["measures"])
    for track in tab["tracks"]:
        assert all(0 <= e["measure"] < n for e in track["events"])
    kinds = {t["id"]: t["kind"] for t in tab["tracks"]}
    assert kinds == {"lead": "tab", "rhythm": "tab", "combined": "tab", "bass": "tab",
                     "vocals": "staff", "keys": "staff", "drums": "drums"}
    labels = {t["id"]: t["label"] for t in tab["tracks"]}
    assert labels["combined"] == "Combined guitar" and labels["keys"] == "Piano / keys"


def test_bass_track_has_four_strings_and_playable_frets(tmp_path):
    tab = build_score(_parts_record(tmp_path / "run", ["bass"], guitar=False), view="staff")["tab"]
    bass = tab["tracks"][0]
    assert bass["strings"] == ["E", "A", "D", "G"]
    notes = [n for e in bass["events"] for n in e["notes"]]
    assert all(0 <= n["string"] <= 3 and 0 <= n["fret"] <= 24 for n in notes)
    assert notes[0]["fret"] == 0  # low E open


def test_staff_and_drum_tracks(tmp_path):
    tab = build_score(_parts_record(tmp_path / "run", ["vocals", "keys", "drums"], guitar=False), view="staff")["tab"]
    by = {t["id"]: t for t in tab["tracks"]}
    assert by["vocals"]["clef"] == "treble"
    assert [n["spelling"] for e in by["vocals"]["events"] for n in e["notes"]] == ["F#4", "E4"]
    assert by["vocals"]["events"][0]["rhythm"]["type"]
    assert by["keys"]["clef"] == "grand"
    assert len(by["keys"]["events"][0]["notes"]) == 2
    assert by["drums"]["events"] == []
    assert by["drums"]["empty_reason"] == "No notes found in this part."


def test_no_guitar_run_still_gets_a_tab_payload(tmp_path):
    score = build_score(_parts_record(tmp_path / "run", ["keys"], guitar=False), view="staff")
    assert score["parts"] == ["keys"]
    assert score["part"] == "keys"
    assert [t["id"] for t in score["tab"]["tracks"]] == ["keys"]


def test_transpose_moves_pitched_parts_not_drums(tmp_path):
    rec = _parts_record(tmp_path / "run", ["vocals"], guitar=False)
    tab = build_score(rec, view="staff", transpose=2)["tab"]
    assert [n["pitch"] for e in tab["tracks"][0]["events"] for n in e["notes"]] == [68, 66]


def test_empty_guitar_part_shows_its_reason_instead_of_a_blank_tab(tmp_path):
    rec = _parts_record(tmp_path / "run", ["combined", "keys"], guitar=False)
    rec.details["empty_parts"] = {"combined": "No notes found in this part."}
    tab = build_score(rec, view="staff")["tab"]
    by = {t["id"]: t for t in tab["tracks"]}
    assert list(by) == ["combined", "keys"]
    assert by["combined"]["events"] == []
    assert by["combined"]["empty_reason"] == "No notes found in this part."
    assert by["combined"]["kind"] == "tab"


def test_guitar_track_without_events_gets_a_reason(tmp_path):
    rec = _parts_record(tmp_path / "run", ["lead", "rhythm"])
    rec.artifacts["lead_midi"] = _midi(rec.dir / "lead_empty.mid", [])
    tab = build_score(rec, view="staff")["tab"]
    lead = next(t for t in tab["tracks"] if t["id"] == "lead")
    assert lead["events"] == [] and lead["empty_reason"] == "No notes found in this part."
