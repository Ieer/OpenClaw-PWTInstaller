from __future__ import annotations

import subprocess
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


class TtsCancelled(Exception):
    pass


def wait_process(
    process: subprocess.Popen,
    *,
    timeout: float,
    cancel_event: threading.Event | None = None,
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        return_code = process.poll()
        if return_code is not None:
            if return_code:
                raise subprocess.CalledProcessError(return_code, process.args)
            return
        if cancel_event is not None and cancel_event.is_set():
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise TtsCancelled("playback cancelled")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process.kill()
            process.wait()
            raise subprocess.TimeoutExpired(process.args, timeout)
        try:
            return_code = process.wait(timeout=min(0.1, remaining))
        except subprocess.TimeoutExpired:
            continue
        if return_code:
            raise subprocess.CalledProcessError(return_code, process.args)
        return


def run_process(
    args: Sequence[str],
    *,
    timeout: float,
    cancel_event: threading.Event | None = None,
    **kwargs: Any,
) -> None:
    process = subprocess.Popen(args, **kwargs)
    wait_process(process, timeout=timeout, cancel_event=cancel_event)


class TtsEngine(ABC):
    @abstractmethod
    def speak(self, text: str, cancel_event: threading.Event | None = None) -> None:
        """Speak text or raise an exception on failure."""
