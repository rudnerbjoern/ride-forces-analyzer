"""Shared data-export format identifiers, independent of Qt and serializers.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from enum import StrEnum


class DataExportFormat(StrEnum):
    """Available sample-export formats with stable text identifiers.

    Attributes:
        CSV: Sample rows in CSV format, identified by ``csv``.
        JSON: JSON shaped like the original application export, identified by ``json``.
        ANALYZER_JSON: Structured analyzer JSON, identified by ``analyzer_json``.
    """

    CSV = "csv"
    JSON = "json"
    ANALYZER_JSON = "analyzer_json"
