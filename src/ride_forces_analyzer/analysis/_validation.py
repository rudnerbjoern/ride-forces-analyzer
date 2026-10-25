"""Shared runtime guards for recording contracts and analysis preparation.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.domain._validation import has_type


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
