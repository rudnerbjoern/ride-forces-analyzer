"""Shared error recording and safe presentation without a Qt dependency.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words backslashreplace

import logging
import subprocess

_LOGGER = logging.getLogger("ride_forces_analyzer.errors")
_LOGGER.addHandler(logging.NullHandler())


def record_error(
    area: str,
    error: BaseException | None = None,
    *,
    message: str = "",
    context: str = "",
) -> None:
    """Record original errors and explicit context before presentation masks them.

    Args:
        area: Operation handling the failure.
        error: Original exception, retaining its type, message, chain and traceback.
        message: Original structured diagnostic or additional operation detail.
        context: Explicit context such as the affected filesystem path.

    No exception text or context is translated, truncated or masked. Local variables
    and recording objects are not inspected. The application report handler owns
    persistence. A null handler prevents standalone imports without handlers from
    formatting tracebacks through stderr; configured handlers receive all records.
    """
    _LOGGER.error(
        "%s: %s%s",
        area,
        message or "Operation failed",
        f"\nContext: {context}" if context else "",
        exc_info=error,
    )
    if isinstance(error, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
        for name, output in (("stdout", error.stdout), ("stderr", error.stderr)):
            if output is not None:
                _LOGGER.error(
                    "%s %s:\n%s",
                    area,
                    name,
                    output.decode("utf-8", errors="backslashreplace")
                    if isinstance(output, bytes)
                    else output,
                )


def error_message(error: BaseException | str = "") -> str:
    """Return approved interface text or a generic localized error-report hint.

    Args:
        error: Exception or failure text requiring safe presentation.

    Returns:
        A known static interface message, or a masked message for internal details.
        Original failures must be recorded separately before using this function.
    """
    from ride_forces_analyzer.i18n import tr
    from ride_forces_analyzer.i18n.de import GERMAN
    from ride_forces_analyzer.i18n.fr import FRENCH

    original = str(error)
    if original in GERMAN and original in FRENCH:
        return tr(original)
    return tr("The operation failed. See the error report for details.")
