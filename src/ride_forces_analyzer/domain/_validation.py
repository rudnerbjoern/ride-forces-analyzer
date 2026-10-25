"""Runtime checks at typed dataclass boundaries; annotations do not validate input.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""


def has_type(value: object, expected: type | tuple[type, ...]) -> bool:
    """Check a runtime type without narrowing the static type of the input.

    Args:
        value: Candidate value to validate, format or store.
        expected: Runtime type or tuple of types accepted by the check.

    Returns:
        True when the requested check succeeds or the event is handled; otherwise False.
    """
    return isinstance(value, expected)
