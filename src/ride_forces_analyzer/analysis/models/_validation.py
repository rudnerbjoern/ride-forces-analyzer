"""Shared metadata checks for immutable analysis models.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from enum import StrEnum

from ride_forces_analyzer.domain._validation import has_type


def validate_text(value: str, name: str) -> None:
    """Require nonempty text without changing its spelling.

    Args:
        value: Text to check.
        name: Field name included in the error message.

    Returns:
        None.

    Raises:
        ValueError: The value is not text or contains only whitespace.
    """
    if not has_type(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")


def text_values(values: Sequence[str], name: str) -> tuple[str, ...]:
    """Own a sequence of nonempty text values, preserving order and spelling.

    Args:
        values: Sequence of text entries to check and copy.
        name: Field name included in validation errors.

    Returns:
        Immutable tuple of the supplied entries.

    Raises:
        TypeError: A string, bytes or non-iterable value is supplied as the sequence.
        ValueError: An entry is not nonempty text.
    """
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} requires a sequence of text values")
    owned = tuple(values)
    for value in owned:
        validate_text(value, name)
    return owned


def validate_enum(value: object, kind: type[StrEnum]) -> None:
    """Require a member of the declared enumeration without coercion.

    Args:
        value: Candidate enumeration member.
        kind: Required string enumeration type.

    Returns:
        None.

    Raises:
        TypeError: The value is not a member of the required enumeration.
    """
    if not isinstance(value, kind):
        raise TypeError(f"Expected {kind.__name__}")
