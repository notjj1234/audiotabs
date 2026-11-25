"""Cooperative cancellation shared by analysis and tab jobs."""

from __future__ import annotations

import threading

from audio_to_tab.subprocess_util import JobAborted


class CancelToken:
    """Set once by the API thread, checked by the worker between stages.

    In-process model inference cannot be interrupted; the worker notices at the
    next ``check()`` (progress call) and Demucs subprocesses poll
    ``is_cancelled`` through ``run_demucs(should_abort=…)``.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise JobAborted("cancelled")
