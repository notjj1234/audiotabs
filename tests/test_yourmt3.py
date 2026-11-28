"""Opt-in YourMT3 transcriber: subprocess contract and fallback to Basic Pitch (no model needed)."""

import logging
import sys
import textwrap
import time

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

from audio_to_tab import transcribe, yourmt3
from audio_to_tab.subprocess_util import JobAborted
from audio_to_tab.yourmt3 import YOURMT3_REVISION, YourMT3Error, run_yourmt3


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "in.wav"
    sf.write(str(path), np.zeros(22050, dtype=np.float32), 22050)
    return path


@pytest.fixture
def fake_runner(tmp_path, monkeypatch):
    """Point the app at a stand-in runner run by this interpreter; returns a writer for its body."""

    def make(body: str):
        script = tmp_path / "fake_runner.py"
        script.write_text(
            "import json, sys, time\n"
            "args = sys.argv[1:]\n"
            "audio, out = args[4], args[5]\n" + textwrap.dedent(body)
        )
        monkeypatch.setattr(yourmt3, "runner_path", lambda: script)
        monkeypatch.setenv(yourmt3.YOURMT3_PYTHON_ENV, sys.executable)
        monkeypatch.setenv(yourmt3.YOURMT3_HOME_ENV, str(tmp_path / "home"))
        return script

    return make


@pytest.fixture
def basic_pitch_calls(monkeypatch):
    calls = []

    def fake_basic_pitch(audio_path, dest, **_kw):
        calls.append(audio_path)
        pm = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=24)
        inst.notes = [pretty_midi.Note(90, 52, 0.0, 0.5)]
        pm.instruments.append(inst)
        pm.write(str(dest))

    monkeypatch.setattr(transcribe, "_basic_pitch_midi", fake_basic_pitch)
    return calls


def _pitches(path):
    return sorted(n.pitch for i in pretty_midi.PrettyMIDI(str(path)).instruments for n in i.notes)


NOTES_BODY = """
json.dump({"notes": [
    {"pitch": 64, "start": 0.10, "end": 0.40, "program": 24},
    {"pitch": 67, "start": 0.50, "end": 0.52, "program": 24},
    {"pitch": 20, "start": 0.60, "end": 0.90, "program": 33},
], "device": "cpu", "seconds": 0.1}, open(out, "w"))
"""


def test_basic_pitch_stays_the_default(wav, tmp_path, basic_pitch_calls, monkeypatch):
    monkeypatch.delenv(yourmt3.TRANSCRIBER_ENV, raising=False)
    monkeypatch.setattr(yourmt3, "run_yourmt3", lambda *_: pytest.fail("YourMT3 must not run"))
    out = transcribe.transcribe_audio(wav, tmp_path / "out.mid", normalize=False)
    assert len(basic_pitch_calls) == 1
    assert _pitches(out) == [52]


def test_runner_gets_the_pinned_revision_and_its_notes_come_back(wav, tmp_path, fake_runner):
    fake_runner(
        """
        assert args[0] == "--home" and args[2] == "--revision"
        json.dump({"notes": [{"pitch": 60, "start": 0.0, "end": 0.5}], "device": "cpu"},
                  open(out, "w"))
        """
    )
    notes = run_yourmt3(wav)
    assert notes == [{"pitch": 60, "start": 0.0, "end": 0.5, "program": 24}]
    assert YOURMT3_REVISION in yourmt3._runner_cmd()
    assert str(tmp_path / "home") in yourmt3._runner_cmd()


def test_opted_in_transcription_uses_yourmt3_notes_through_the_cleanup(
    wav, tmp_path, fake_runner, basic_pitch_calls, monkeypatch
):
    monkeypatch.setenv(yourmt3.TRANSCRIBER_ENV, "yourmt3")
    fake_runner(NOTES_BODY)
    out = transcribe.transcribe_audio(wav, tmp_path / "out.mid", normalize=False)
    assert basic_pitch_calls == []
    # 20 is below the guitar range and removed by the cleanup; the 20 ms note is kept because
    # short YourMT3 notes are lengthened to 60 ms before the cleanup's 50 ms floor.
    assert _pitches(out) == [64, 67]


def test_a_failing_runner_falls_back_to_basic_pitch(
    wav, tmp_path, fake_runner, basic_pitch_calls, monkeypatch, caplog
):
    monkeypatch.setenv(yourmt3.TRANSCRIBER_ENV, "yourmt3")
    fake_runner('sys.stderr.write("CUDA exploded\\n"); sys.exit(3)\n')
    with caplog.at_level(logging.WARNING):
        out = transcribe.transcribe_audio(wav, tmp_path / "out.mid", normalize=False)
    assert len(basic_pitch_calls) == 1 and _pitches(out) == [52]
    assert "exited with 3" in caplog.text and "CUDA exploded" in caplog.text


def test_missing_environment_names_the_setup_command(wav, tmp_path, monkeypatch, basic_pitch_calls):
    monkeypatch.setenv(yourmt3.TRANSCRIBER_ENV, "yourmt3")
    monkeypatch.setenv(yourmt3.YOURMT3_PYTHON_ENV, str(tmp_path / "nope" / "python"))
    assert "python -m audio_to_tab.yourmt3 setup" in yourmt3.yourmt3_skip_reason()
    transcribe.transcribe_audio(wav, tmp_path / "out.mid", normalize=False)
    assert len(basic_pitch_calls) == 1


def test_a_hung_runner_is_stopped(wav, fake_runner, monkeypatch):
    fake_runner("time.sleep(30)\n")
    monkeypatch.setattr(yourmt3, "_timeout_for", lambda _p: 0.5)
    with pytest.raises(YourMT3Error, match="did not finish"):
        run_yourmt3(wav)


def test_garbage_output_is_an_error_not_a_crash(wav, fake_runner):
    fake_runner('open(out, "w").write("{\\"notes\\": [{\\"pitch\\": \\"x\\"}]}")\n')
    with pytest.raises(YourMT3Error, match="unreadable"):
        run_yourmt3(wav)


def test_the_runner_file_ships_next_to_the_module():
    assert yourmt3.runner_path().is_file()


def test_cancel_kills_the_runner_and_stops_the_job_without_falling_back(
    wav, tmp_path, fake_runner, basic_pitch_calls, monkeypatch
):
    monkeypatch.setenv(yourmt3.TRANSCRIBER_ENV, "yourmt3")
    fake_runner("time.sleep(30)\n")
    started = time.monotonic()
    with yourmt3.abort_scope(lambda: time.monotonic() - started > 0.3), pytest.raises(JobAborted):
        transcribe.transcribe_audio(wav, tmp_path / "out.mid", normalize=False)
    assert time.monotonic() - started < 10
    assert basic_pitch_calls == []


def test_non_guitar_audio_keeps_basic_pitch(wav, tmp_path, basic_pitch_calls, monkeypatch):
    monkeypatch.setenv(yourmt3.TRANSCRIBER_ENV, "yourmt3")
    monkeypatch.setattr(yourmt3, "run_yourmt3", lambda *_: pytest.fail("YourMT3 must not run"))
    transcribe.transcribe_audio(wav, tmp_path / "out.mid", normalize=False, allow_yourmt3=False)
    assert len(basic_pitch_calls) == 1


def test_bass_keys_and_other_parts_opt_out_of_yourmt3(tmp_path, monkeypatch):
    from audio_to_tab import part_transcribe
    from audio_to_tab.pipeline import PipelineConfig
    from tests.test_part_transcribe import _fake_basic_pitch

    fake = _fake_basic_pitch([40, 43])
    monkeypatch.setattr(part_transcribe, "transcribe_audio", fake)
    stem = tmp_path / "bass.wav"
    sf.write(str(stem), np.zeros(22050, dtype=np.float32), 22050)
    part_transcribe.transcribe_part("bass", stem, tmp_path / "out", cfg=PipelineConfig())
    assert fake.kwargs["allow_yourmt3"] is False


def test_run_pipeline_hands_its_cancel_token_to_yourmt3(tmp_path, monkeypatch):
    from audio_to_tab import pipeline
    from audio_to_tab.cancel import CancelToken

    seen = {}

    def fake_run(**_kw):
        seen["abort"] = yourmt3._SHOULD_ABORT.get()
        return {}

    monkeypatch.setattr(pipeline, "_run_pipeline", fake_run)
    token = CancelToken()
    pipeline.run_pipeline(output_dir=tmp_path, cancel=token)
    assert seen["abort"] == token.is_cancelled
    assert yourmt3._SHOULD_ABORT.get() is None
