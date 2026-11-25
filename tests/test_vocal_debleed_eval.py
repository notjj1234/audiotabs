"""G4 evidence: vocal de-bleed on a deterministic synthetic fixture with real Basic Pitch.

Guitar line (Karplus–Strong, 16 notes, one in unison with the singer) plus a
vibrato vocal mixed in at 0.3 (≈ −10 dB) as bleed. Metrics: note recall from
``scripts/eval_tabs.note_match_f1`` against the guitar reference, and the number
of transcribed notes that sit on a sung pitch while it is sung and match no
guitar note (vocal-pitch notes in the guitar tab).
"""

from __future__ import annotations

import json
from dataclasses import replace

import pretty_midi
import pytest

pytest.importorskip("basic_pitch")

from audio_to_tab.midi_cleanup import mix_aware_cleanup_config  # noqa: E402
from audio_to_tab.transcribe import transcribe_audio  # noqa: E402
from audio_to_tab.vocal_debleed import DebleedFeatures, reject_vocal_bleed  # noqa: E402
from scripts.eval_tabs import note_match_f1  # noqa: E402
from tests.audio_fixtures import GUITAR_NOTES, UNISON, VOCAL_NOTES, make_bleed_fixture  # noqa: E402

ONSET_TOL = 0.05


def _transcribe(path, out):
    # Same thresholds and cleanup the pipeline uses for separated full mixes.
    transcribe_audio(
        path,
        out,
        onset_threshold=0.58,
        frame_threshold=0.40,
        minimum_note_length_ms=90,
        cleanup=replace(mix_aware_cleanup_config(), quantize_sec=None),
        normalize=False,
    )
    return [n for inst in pretty_midi.PrettyMIDI(str(out)).instruments for n in inst.notes]


def _is_guitar(n) -> bool:
    return any(n.pitch == p and abs(n.start - s) <= ONSET_TOL for p, s, _e in GUITAR_NOTES)


def _vocal_pitch_notes(notes) -> int:
    return sum(
        any(n.pitch % 12 == p % 12 and s - ONSET_TOL <= n.start <= e for p, s, e in VOCAL_NOTES)
        and not _is_guitar(n)
        for n in notes
    )


def _recall(notes) -> float:
    hyp = [{"pitch": n.pitch, "start": n.start, "end": n.end} for n in notes]
    ref = [{"pitch": p, "start": s, "end": e} for p, s, e in GUITAR_NOTES]
    return note_match_f1(hyp, ref)["note_recall"]


def test_debleed_removes_vocal_notes_without_losing_guitar(tmp_path):
    guitar_stem, vocals_stem, _gref, _vref = make_bleed_fixture(tmp_path)
    before = _transcribe(guitar_stem, tmp_path / "hyp.mid")
    after, report = reject_vocal_bleed(before, DebleedFeatures.from_audio(guitar_stem, vocals_stem))

    row = {
        "before": {"vocal_pitch_notes": _vocal_pitch_notes(before), "recall": _recall(before)},
        "after": {"vocal_pitch_notes": _vocal_pitch_notes(after), "recall": _recall(after)},
        "removed": report.notes_removed,
    }
    print(json.dumps(row))

    b, a = row["before"], row["after"]
    assert b["vocal_pitch_notes"] >= 5, "fixture must actually produce bleed notes"
    assert a["vocal_pitch_notes"] <= 0.3 * b["vocal_pitch_notes"]  # ≥ 70 % fewer
    assert a["vocal_pitch_notes"] <= 2
    assert b["recall"] - a["recall"] <= 0.02
    assert any(n.pitch == UNISON[0] and abs(n.start - UNISON[1]) <= ONSET_TOL for n in after)
