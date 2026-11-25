"""Rough kit hits (kick / snare / hi-hat) from band-split onsets."""

from __future__ import annotations

import numpy as np
import soundfile as sf

from audio_to_tab.drum_transcribe import transcribe_drums
from tests.analysis_fakes import SR, drum_pattern

PATTERN = (
    [("kick", t) for t in (0.1, 1.1)]
    + [("snare", t) for t in (0.6, 1.6)]
    + [("hihat", t) for t in (0.35, 0.85, 1.35, 1.85)]
)


def _recall(hits, piece, times, tol=0.035):
    got = [h.start for h in hits if h.piece == piece]
    found = sum(any(abs(g - t) <= tol for g in got) for t in times)
    return found / len(times), len(got)


def test_each_piece_classified_on_planted_pattern(tmp_path):
    hits = transcribe_drums(drum_pattern(tmp_path / "d.wav", PATTERN))
    for piece in ("kick", "snare", "hihat"):
        times = [t for p, t in PATTERN if p == piece]
        recall, count = _recall(hits, piece, times)
        assert recall >= 0.8, (piece, recall, hits)
        assert count <= len(times) + 1, (piece, count, hits)
    assert all(1 <= h.velocity <= 127 for h in hits)


def test_silence_gives_no_hits(tmp_path):
    path = tmp_path / "s.wav"
    sf.write(path, np.zeros(SR * 2), SR)
    assert transcribe_drums(path) == []
