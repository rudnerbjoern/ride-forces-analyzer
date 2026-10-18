"""Runtime checks at typed dataclass boundaries; annotations do not validate input.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""


def has_type(value: object, expected: type | tuple[type, ...]) -> bool:
    return isinstance(value, expected)
