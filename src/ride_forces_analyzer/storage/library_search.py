"""Normalized metadata projections for Library filtering without source BLOB reads.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from unicodedata import normalize


def normalize_library_text(value: str) -> str:
    """Normalize text consistently for Unicode substring and park matching.

    Args:
        value: Display spelling or user-entered query.

    Returns:
        Compatibility-normalized, case-folded text without surrounding whitespace.
    """
    return normalize("NFKC", value).casefold().strip()


def library_search_values(ride: str | None, park: str | None) -> tuple[str | None, str]:
    """Build disposable query projections from the effective display names.

    Args:
        ride: Effective ride name, if available.
        park: Effective park name, if available.

    Returns:
        Optional park key and combined ride/park search text.
    """
    key = normalize_library_text(park or "") or None
    return key, f"{normalize_library_text(ride or '')} {key or ''}"
