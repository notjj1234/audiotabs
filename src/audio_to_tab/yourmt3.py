"""Opt-in YourMT3+ note transcription, run out of process in its own environment.

``ATT_TRANSCRIBER=yourmt3`` makes :func:`audio_to_tab.transcribe.transcribe_audio` try
YourMT3+ (YPTF.MoE+Multi, Chang et al. 2024) before Basic Pitch; any failure falls back to
Basic Pitch. On EGDB electric guitar it raised note F1 on clean and crunch tones and on real
recordings but not on high-gain tones (docs/guitar-separation-eval.md).

YourMT3 pins transformers 4.45 (which needs huggingface_hub < 1, older than this app's), and its
code is GPL-3.0, so it lives in a separate virtualenv that ``python -m audio_to_tab.yourmt3
setup`` creates, and runs in a subprocess via ``yourmt3_runner.py``. Code and checkpoint come
from a pinned revision of the Hugging Face Space on first use; nothing ships with the app and
no audio leaves the machine.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from audio_to_tab.subprocess_util import run_process, subprocess_run_kwargs

logger = logging.getLogger(__name__)

# Set by the tab job (``abort_scope``) so a cancelled job kills the runner mid-song instead of
# waiting minutes for it; transcribe_audio's callers don't carry the job's cancel token.
_SHOULD_ABORT: ContextVar[Callable[[], bool] | None] = ContextVar("yourmt3_abort", default=None)

TRANSCRIBER_ENV = "ATT_TRANSCRIBER"
YOURMT3_PYTHON_ENV = "ATT_YOURMT3_PYTHON"
YOURMT3_HOME_ENV = "ATT_YOURMT3_HOME"
YOURMT3_DEVICE_ENV = "ATT_YOURMT3_DEVICE"

YOURMT3_REVISION = "5e66c1ea173a8186e0d20432b841d3180cc015b5"  # mimbres/YourMT3 Space, 2025-01-31
# Versions the EGDB comparison ran with. transformers 5.x fails to import YourMT3's T5 code.
YOURMT3_REQUIREMENTS = (
    "torch>=2.2",
    "torchaudio>=2.2",
    "transformers==4.45.1",
    "lightning==2.6.6",
    "einops==0.8.2",
    "deprecated==1.3.1",
    "mido==1.3.3",
    "mir_eval==0.8.2",
    "librosa==0.11.0",
    "numpy==1.26.4",
    "soundfile==0.14.0",
)
_TIMEOUT_BASE_SEC = 300.0  # model load + first-use download allowance
_TIMEOUT_PER_AUDIO_SEC = 4.0


class YourMT3Error(RuntimeError):
    """YourMT3 could not transcribe; the caller falls back to Basic Pitch."""


@contextmanager
def abort_scope(should_abort: Callable[[], bool] | None) -> Iterator[None]:
    """While active, a YourMT3 run stops (``JobAborted``) as soon as ``should_abort()`` is true."""
    token = _SHOULD_ABORT.set(should_abort)
    try:
        yield
    finally:
        _SHOULD_ABORT.reset(token)


def wants_yourmt3() -> bool:
    return os.environ.get(TRANSCRIBER_ENV, "").strip().lower() == "yourmt3"


def yourmt3_home() -> Path:
    if env := os.environ.get(YOURMT3_HOME_ENV):
        return Path(env)
    return Path.home() / ".cache" / "audio_to_tab" / "yourmt3"


def yourmt3_python() -> Path:
    if env := os.environ.get(YOURMT3_PYTHON_ENV):
        return Path(env)
    venv = yourmt3_home() / "venv"
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def runner_path() -> Path:
    return Path(__file__).with_name("yourmt3_runner.py")


def yourmt3_skip_reason() -> str | None:
    """Why YourMT3 can't run here, or None when it can."""
    if not runner_path().is_file():
        return "yourmt3_runner.py is not in this build"
    if not yourmt3_python().is_file():
        return (
            f"no YourMT3 environment at {yourmt3_python()} "
            "(run: python -m audio_to_tab.yourmt3 setup)"
        )
    return None


def _runner_cmd(*extra: str) -> list[str]:
    return [
        str(yourmt3_python()),
        str(runner_path()),
        "--home",
        str(yourmt3_home()),
        "--revision",
        YOURMT3_REVISION,
        *extra,
    ]


def _timeout_for(audio_path: Path) -> float:
    try:
        import soundfile as sf

        duration = float(sf.info(str(audio_path)).duration)
    except (ImportError, RuntimeError, OSError):
        duration = 600.0
    return _TIMEOUT_BASE_SEC + _TIMEOUT_PER_AUDIO_SEC * duration


def run_yourmt3(audio_path: str | Path) -> list[dict]:
    """Notes (``pitch``, ``start``, ``end``, ``program``) for ``audio_path``.

    Raises YourMT3Error when it can't transcribe, and JobAborted (not caught by the Basic Pitch
    fallback) when the surrounding ``abort_scope`` says the job was cancelled.
    """
    if reason := yourmt3_skip_reason():
        raise YourMT3Error(reason)
    audio_path = Path(audio_path)
    with tempfile.TemporaryDirectory() as tmp:
        out_json = Path(tmp) / "notes.json"
        extra = [str(audio_path.resolve()), str(out_json)]
        if device := os.environ.get(YOURMT3_DEVICE_ENV):
            extra += ["--device", device]
        try:
            proc = run_process(
                _runner_cmd(*extra),
                should_abort=_SHOULD_ABORT.get(),
                timeout_sec=_timeout_for(audio_path),
                capture_output=True,
                text=True,
                **subprocess_run_kwargs(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise YourMT3Error(f"YourMT3 did not finish: {exc}") from exc
        if proc.returncode != 0 or not out_json.is_file():
            tail = (proc.stderr or "").strip().splitlines()[-5:]
            raise YourMT3Error(f"YourMT3 exited with {proc.returncode}: {' | '.join(tail)}")
        try:
            result = json.loads(out_json.read_text(encoding="utf-8"))
            notes = [
                {
                    "pitch": int(n["pitch"]),
                    "start": float(n["start"]),
                    "end": float(n["end"]),
                    "program": int(n.get("program", 24)),
                }
                for n in result["notes"]
            ]
        except (ValueError, KeyError, TypeError) as exc:
            raise YourMT3Error(f"YourMT3 wrote unreadable output: {exc}") from exc
    logger.info(
        "YourMT3 transcribed %s: %d notes on %s in %ss",
        audio_path.name, len(notes), result.get("device"), result.get("seconds"),
    )
    return notes


def setup_environment() -> Path:
    """Create the YourMT3 virtualenv, install its pinned deps, prefetch code + checkpoint."""
    venv = yourmt3_home() / "venv"
    uv = shutil.which("uv")
    if uv:
        subprocess.run([uv, "venv", "--python", "3.11", str(venv)], check=True)
        install = [uv, "pip", "install", "--python", str(yourmt3_python())]
    elif not getattr(sys, "frozen", False):
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        install = [str(yourmt3_python()), "-m", "pip", "install"]
    else:
        raise YourMT3Error("setup needs uv or a Python interpreter; this app build has neither")
    subprocess.run([*install, *YOURMT3_REQUIREMENTS], check=True)
    subprocess.run(_runner_cmd("--prefetch"), check=True)
    return yourmt3_python()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["setup"]:
        print("usage: python -m audio_to_tab.yourmt3 setup", file=sys.stderr)
        return 2
    if os.environ.get(YOURMT3_PYTHON_ENV):
        print(f"{YOURMT3_PYTHON_ENV} is set; setup only manages {yourmt3_home() / 'venv'}",
              file=sys.stderr)
        return 2
    python = setup_environment()
    print(f"YourMT3 ready: {python}\nUse it with {TRANSCRIBER_ENV}=yourmt3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
