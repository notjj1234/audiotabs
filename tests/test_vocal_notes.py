"""Vocal melody → notes via librosa pyin."""

from __future__ import annotations

import numpy as np
import soundfile as sf

from audio_to_tab.vocal_notes import pyin_notes
from tests.analysis_fakes import SR, vocal_melody

MELODY = [(60, 0.1, 0.6), (64, 0.75, 1.25), (67, 1.4, 1.95)]


def test_pyin_recovers_planted_melody(tmp_path):
    notes = pyin_notes(vocal_melody(tmp_path / "v.wav", MELODY))
    assert [n.pitch for n in notes] == [60, 64, 67]
    for got, (_, start, end) in zip(notes, MELODY):
        assert abs(got.start - start) <= 0.05
        assert abs(got.end - end) <= 0.08
        assert 1 <= got.velocity <= 127


def test_pyin_silence_gives_no_notes(tmp_path):
    path = tmp_path / "s.wav"
    sf.write(path, np.zeros(SR), SR)
    assert pyin_notes(path) == []


def test_pitch_track_is_computed_once_per_audio_content(tmp_path, monkeypatch):
    import shutil

    import librosa

    import audio_to_tab.vocal_notes as vocal_notes

    calls = []
    real = librosa.pyin

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(librosa, "pyin", counting)
    vocal_notes.clear_cache()
    a = vocal_melody(tmp_path / "a.wav", MELODY)
    b = tmp_path / "copy" / "vocals.wav"
    b.parent.mkdir()
    shutil.copy2(a, b)
    first = vocal_notes.vocal_pitch_track(a)
    second = vocal_notes.vocal_pitch_track(b)
    assert len(calls) == 1
    assert np.array_equal(np.nan_to_num(first.f0), np.nan_to_num(second.f0))
