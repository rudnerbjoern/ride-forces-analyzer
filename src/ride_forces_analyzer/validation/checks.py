"""Shared runtime checks independent of domain, analysis and UI modules.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from enum import StrEnum
import re


def has_type(value: object, expected: type | tuple[type, ...]) -> bool:
    """Check a runtime type without narrowing the static type of the input.

    Args:
        value: Candidate value to validate, format or store.
        expected: Runtime type or tuple of types accepted by the check.

    Returns:
        True when the value has an accepted runtime type; otherwise False.
    """
    return isinstance(value, expected)


def require(condition: bool, message: str) -> None:
    """Reject an unsatisfied structural or semantic constraint.

    Args:
        condition: Whether the required invariant holds.
        message: Error description when the invariant fails.

    Returns:
        None.

    Raises:
        ValueError: The supplied condition is false.
    """
    if not condition:
        raise ValueError(message)


def require_type(value: object, kind: type) -> None:
    """Check a runtime type without coercion or collection copying.

    Args:
        value: Candidate value to check.
        kind: Required runtime type.

    Returns:
        None.

    Raises:
        TypeError: The candidate has an incompatible runtime type.
    """
    if not has_type(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


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
    require_type(value, kind)


def validate_sha256(value: object, message: str) -> str:
    """Require a lowercase SHA-256 hexadecimal digest without normalization.

    Args:
        value: Candidate digest, accepted only as 64 lowercase hexadecimal characters.
        message: Caller-specific error description for an invalid digest.

    Returns:
        The original validated digest string.

    Raises:
        ValueError: The value is not a lowercase SHA-256 hexadecimal digest.
    """
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(message)
    return value


def validate_diagnostic_code(value: object) -> None:
    """Require a stable uppercase diagnostic identifier.

    Args:
        value: Identifier beginning with an ASCII uppercase letter, followed only
            by ASCII uppercase letters, digits or underscores.

    Returns:
        None without changing the supplied identifier.

    Raises:
        ValueError: The value is not a supported diagnostic identifier.
    """
    require(
        isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", value) is not None,
        "Diagnostic code must be a stable uppercase identifier",
    )


def validate_sample_range(
    first: int,
    last: int,
    count: int,
    message: str,
    *,
    type_message: str | None = None,
) -> None:
    """Require an inclusive integer sample interval within a source length.

    Args:
        first: First included source sample index; booleans are rejected.
        last: Last included source sample index; booleans are rejected.
        count: Number of source samples defining the exclusive upper bound.
        message: Error description for an invalid interval.
        type_message: Optional separate TypeError description for indices that
            are not integers; otherwise they raise ValueError using message.

    Returns:
        None without coercing or changing the indices.

    Raises:
        TypeError: An index is not an integer and type_message was supplied.
        ValueError: The interval is negative, reversed or outside the source, or
            an index is not an integer and no type_message was supplied.
    """
    if type(first) is not int or type(last) is not int:
        if type_message is not None:
            raise TypeError(type_message)
        raise ValueError(message)
    require(0 <= first <= last < count, message)
