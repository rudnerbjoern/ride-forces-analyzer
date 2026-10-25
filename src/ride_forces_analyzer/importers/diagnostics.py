"""Immutable import diagnostics and deterministic JSON Pointer ordering.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
import re


from ride_forces_analyzer.domain._validation import has_type


class Severity(StrEnum):
    """Severity contract and owned data.

    Attributes:
        ERROR: Named value for error (`error`).
        WARNING: Named value for warning (`warning`).
        INFO: Named value for info (`info`).
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ImportDiagnostic:
    """Import diagnostic contract and owned data.

    Attributes:
        code: Stable diagnostic code used to select its localized explanation.
        severity: Diagnostic severity.
        json_path: Location within the input JSON document.
        message: Text or diagnostic message to present or validate.
        sample_index: Source index associated with the diagnostic, when available.
    """

    code: str
    severity: Severity
    json_path: str
    message: str
    sample_index: int | None = None

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Diagnostic code must be a stable uppercase identifier. Diagnostic path
                must be an RFC 6901 JSON Pointer. Diagnostic message must not be empty.
                Diagnostic sample index must be a nonnegative integer.
            TypeError: Diagnostic severity must be a Severity.
        """
        if not has_type(self.code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.code):
            raise ValueError("Diagnostic code must be a stable uppercase identifier")
        if not has_type(self.severity, Severity):
            raise TypeError("Diagnostic severity must be a Severity")
        if (
            not has_type(self.json_path, str)
            or (self.json_path and not self.json_path.startswith("/"))
            or re.search(r"~(?:[^01]|$)", self.json_path)
        ):
            raise ValueError("Diagnostic path must be an RFC 6901 JSON Pointer")
        if not has_type(self.message, str) or not self.message.strip():
            raise ValueError("Diagnostic message must not be empty")
        if self.sample_index is not None and (
            type(self.sample_index) is not int or self.sample_index < 0
        ):
            raise ValueError("Diagnostic sample index must be a nonnegative integer")


def json_pointer(*tokens: str | int) -> str:
    """Build an escaped pointer, with the empty pointer identifying the root.

    Args:
        *tokens: Additional positional arguments accepted by the callback.

    Returns:
        Escaped JSON pointer; an empty string identifies the root.

    Raises:
        ValueError: Pointer tokens require strings or nonnegative integer indices.
    """
    escaped: list[str] = []
    for token in tokens:
        if not isinstance(token, str) and (type(token) is not int or token < 0):
            raise ValueError("Pointer tokens require strings or nonnegative integer indices")
        escaped.append(str(token).replace("~", "~0").replace("/", "~1"))
    return "".join("/" + token for token in escaped)


def ordered_diagnostics(diagnostics: Sequence[ImportDiagnostic]) -> tuple[ImportDiagnostic, ...]:
    """Copy and sort by severity, escaped pointer and code; exact ties stay stable.

    Args:
        diagnostics: Structured diagnostics or their collector.

    Returns:
        Diagnostics ordered by severity, pointer and code with stable exact ties.

    Raises:
        TypeError: Diagnostics must contain ImportDiagnostic values.
    """
    owned = tuple(diagnostics)
    if any(not has_type(item, ImportDiagnostic) for item in owned):
        raise TypeError("Diagnostics must contain ImportDiagnostic values")
    ranks = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    return tuple(sorted(owned, key=lambda item: (ranks[item.severity], item.json_path, item.code)))
