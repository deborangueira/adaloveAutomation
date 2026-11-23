"""Lifecycle helpers for `adalove serve` — keep a stale server from lingering.

Two failure modes this guards against (both seen in practice: a server left
running for weeks kept serving old code and hung on every Playwright call):

- IdleWatchdog: the server shuts itself down after a period with no requests,
  so the next launch always starts fresh code and dependencies.
- PID file: a new `adalove serve` stops the previous instance before binding,
  so double-clicking the launcher always "fixes" a wedged server.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from adalove.config.paths import SERVER_PIDFILE

PIDFILE = SERVER_PIDFILE


class IdleWatchdog:
    """Calls `on_idle` once no `touch()` happened for `idle_seconds`."""

    def __init__(
        self,
        idle_seconds: float,
        on_idle: Callable[[], None],
        check_every: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.idle_seconds = idle_seconds
        self.on_idle = on_idle
        self.check_every = check_every
        self._clock = clock
        self._last = clock()
        self._in_flight = 0
        self._lock = threading.Lock()

    def request_started(self) -> None:
        with self._lock:
            self._in_flight += 1
            self._last = self._clock()

    def request_finished(self) -> None:
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._last = self._clock()

    def is_idle(self) -> bool:
        # A request still being served (e.g. waiting on a browser login) is
        # activity, however long it takes.
        with self._lock:
            return self._in_flight == 0 and self._clock() - self._last >= self.idle_seconds

    def start(self) -> threading.Thread:
        def _loop() -> None:
            while True:
                time.sleep(self.check_every)
                if self.is_idle():
                    self.on_idle()
                    return

        t = threading.Thread(target=_loop, name="adalove-idle-watchdog", daemon=True)
        t.start()
        return t


def interrupt_main_process() -> None:
    """Stop the dev server the same way Ctrl+C would, so atexit hooks run."""
    os.kill(os.getpid(), signal.SIGINT)


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _is_adalove_server(pid: int) -> bool:
    """Only ever signal a process that is really `adalove serve` — the PID may
    have been recycled by an unrelated process since the file was written."""
    if not _is_alive(pid):
        return False
    try:
        cmd = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "adalove" in cmd and "serve" in cmd


def stop_previous_instance(pidfile: Path = PIDFILE, timeout: float = 5.0) -> int | None:
    """Stop the server recorded in `pidfile`, if it is still running.
    Returns the stopped PID, or None if there was nothing to stop."""
    try:
        pid = int(pidfile.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None

    if pid == os.getpid() or not _is_adalove_server(pid):
        pidfile.unlink(missing_ok=True)
        return None

    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while _is_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    if _is_alive(pid):
        os.kill(pid, signal.SIGKILL)
    pidfile.unlink(missing_ok=True)
    return pid


def write_pidfile(pidfile: Path = PIDFILE) -> None:
    pidfile.write_text(str(os.getpid()))


def remove_pidfile(pidfile: Path = PIDFILE) -> None:
    """Remove the PID file only if it is still ours — a newer server that
    replaced us has already written its own PID there."""
    try:
        if int(pidfile.read_text().strip()) == os.getpid():
            pidfile.unlink()
    except (FileNotFoundError, ValueError):
        pass
