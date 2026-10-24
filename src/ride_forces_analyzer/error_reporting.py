"""Local, unbounded error reports for the current application run.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

# cspell:words getpid backslashreplace excepthook unraisablehook

import atexit
import ctypes
from datetime import UTC, datetime
import faulthandler
import logging
import os
from pathlib import Path
import platform
import sys
import threading
import traceback
from types import TracebackType
from typing import TextIO

from ride_forces_analyzer import __version__
from ride_forces_analyzer.runtime_paths import data_directory

_LOGGER = logging.getLogger("ride_forces_analyzer.errors")
_stream: TextIO | None = None


class _CompleteTraceback(logging.Formatter):
    def formatException(
        self,
        ei: tuple[type[BaseException], BaseException, TracebackType | None]
        | tuple[None, None, None],
    ) -> str:
        kind, error, trace = ei
        if kind is None or error is None:
            return ""
        formatted = traceback.TracebackException(
            kind,
            error,
            trace,
            capture_locals=False,
            max_group_width=sys.maxsize,
            max_group_depth=sys.maxsize,
        )
        return "".join(formatted.format(chain=True)).rstrip()


def record_error(area: str, error: BaseException | None = None, *, message: str = "") -> None:
    """Record a failure without inspecting locals, arguments or recording objects.

    Exception messages and all available chained traceback frames are retained.
    Reporting must never replace an application's original error handling.
    """
    _LOGGER.error("%s: %s", area, message or "Operation failed", exc_info=error)


def _running(pid: int) -> bool:
    """Avoid removing reports owned by another running application instance."""
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.WaitForSingleObject.restype = ctypes.c_uint32
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE access.
        if handle:
            try:
                # A process object may remain accessible after the process has exited.
                return bool(kernel.WaitForSingleObject(handle, 0))
            finally:
                kernel.CloseHandle(handle)
        return ctypes.get_last_error() != 87  # Invalid PID; other errors may mean access denied.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def initialize_error_reporting() -> Path | None:
    """Install process hooks once; return the local report path when writable.

    Prepare the text file at startup so faulthandler can write during native faults.
    Completed-run reports are removed on the next start; active instances retain
    independent files. No size/count limit, uploads, locals or source dumps.
    Unwritable support storage leaves normal application/error handling intact.
    """
    global _stream
    if _stream is not None:
        return Path(_stream.name)
    directory = data_directory() / "support"
    path = directory / f"error-report-{os.getpid()}.txt"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for previous in directory.glob("error-report-*.txt"):
            try:
                pid = int(previous.stem.removeprefix("error-report-"))
                if pid == os.getpid() or not _running(pid):
                    previous.unlink(missing_ok=True)
            except OSError, ValueError:
                continue
        stream = path.open("w", encoding="utf-8", errors="backslashreplace")
        stream.write(
            f"Ride Forces Analyzer: {__version__}\n"
            f"Run started (UTC): {datetime.now(UTC).isoformat()}\n"
            f"Operating system: {platform.system()} {platform.release()}\n"
            f"Architecture: {platform.machine()}\nPython: {platform.python_version()}\n"
            "Local support report. Review personal data before sharing.\n\n",
        )
        stream.flush()
    except OSError:
        return None
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.ERROR)
    handler.setFormatter(_CompleteTraceback("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger("ride_forces_analyzer").addHandler(handler)
    _stream = stream
    previous_exception = sys.excepthook
    previous_thread = threading.excepthook
    previous_unraisable = sys.unraisablehook

    def exception_hook(
        kind: type[BaseException],
        error: BaseException,
        trace: TracebackType | None,
    ) -> None:
        record_error("Unhandled main-thread exception", error.with_traceback(trace))
        previous_exception(kind, error, trace)

    def thread_hook(arguments: threading.ExceptHookArgs) -> None:
        if arguments.exc_value is not None:
            record_error(
                "Unhandled thread exception",
                arguments.exc_value.with_traceback(arguments.exc_traceback),
            )
        previous_thread(arguments)

    # The unraisable-hook argument type is internal to CPython; sys provides no public constructor.
    def unraisable_hook(arguments: sys.UnraisableHookArgs) -> None:
        if arguments.exc_value is not None:
            record_error(
                "Unraisable exception",
                arguments.exc_value.with_traceback(arguments.exc_traceback),
            )
        previous_unraisable(arguments)

    sys.excepthook = exception_hook
    threading.excepthook = thread_hook
    sys.unraisablehook = unraisable_hook
    try:
        faulthandler.enable(file=stream, all_threads=True)
    except OSError, RuntimeError:
        record_error("Native fault handler", message=traceback.format_exc())

    def close() -> None:
        faulthandler.disable()
        if sys.excepthook is exception_hook:
            sys.excepthook = previous_exception
        if threading.excepthook is thread_hook:
            threading.excepthook = previous_thread
        if sys.unraisablehook is unraisable_hook:
            sys.unraisablehook = previous_unraisable
        logging.getLogger("ride_forces_analyzer").removeHandler(handler)
        handler.flush()
        stream.close()

    atexit.register(close)
    return path
