"""A deterministic legacy Lead/Rhythm run folder (meta without details.parts)."""

from __future__ import annotations

from pathlib import Path

from app.server.store import RunRecord
from tests.test_score_tracks import _midi, _record, _result


def legacy_lead_rhythm_record(run_dir: Path) -> RunRecord:
    run_dir.mkdir(parents=True, exist_ok=True)
    beats = [round(i * 0.5, 3) for i in range(17)]
    lead = _midi(run_dir / "lead.mid", [(64, 0.0, 0.5), (67, 0.5, 1.0), (71, 2.0, 2.25), (72, 2.25, 2.5)])
    rhythm = _midi(run_dir / "rhythm.mid", [(40, 0.0, 1.0), (47, 0.0, 1.0), (52, 0.0, 1.0), (45, 2.0, 4.0)])
    combined = _midi(run_dir / "stems.mid", [(64, 0.0, 0.5), (40, 0.0, 1.0), (45, 2.0, 4.0)])
    return _record(
        run_dir,
        {
            "lead_midi": lead,
            "rhythm_midi": rhythm,
            "midi": combined,
            "lead_result": _result(run_dir / "lead.json", beats=beats, downbeats=[0.0, 2.0]),
            "rhythm_result": _result(run_dir / "rhythm.json", beats=beats, downbeats=[0.0, 2.0]),
            "result": _result(run_dir / "result.json", beats=beats, downbeats=[0.0, 2.0]),
        },
    )
