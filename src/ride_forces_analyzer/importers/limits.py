"""Immutable per-call budgets for the arc42 read-only import boundary.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, fields
import sys


@dataclass(frozen=True, slots=True)
class ImportLimits:
    max_bytes: int = 16_777_216
    max_depth: int = 32
    max_sequence_length: int = 100_000
    max_nodes: int = 1_000_000
    max_object_members: int = 1_024
    max_string_length: int = 65_536
    max_number_length: int = 128
    max_diagnostics: int = 1_000

    def __post_init__(self) -> None:
        for definition in fields(self):
            value = getattr(self, definition.name)
            if type(value) is not int or not 0 < value < sys.maxsize:
                raise ValueError(f"{definition.name} must be a positive bounded integer")
        # The standard-library decoder and source ownership use recursion. Keep
        # configured nesting within a conservative budget without changing Python globals.
        if self.max_depth > 128:
            raise ValueError("max_depth must not exceed the supported safety ceiling of 128")


DEFAULT_LIMITS = ImportLimits()
