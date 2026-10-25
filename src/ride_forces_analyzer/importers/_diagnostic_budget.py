"""Shared bounded diagnostics for standalone subsets and full import calls.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field

from ride_forces_analyzer.domain import SourceEnvelope

from .diagnostics import ImportDiagnostic, Severity, json_pointer
from .result import ImportFailure


class DiagnosticBudgetExceeded(Exception):
    """Signal that the configured diagnostic capacity has been exhausted."""

    pass


@dataclass(slots=True)
class DiagnosticBudget:
    """Collect import diagnostics within a fixed resource budget.

    Attributes:
        maximum: Maximum retained value or configured resource limit.
        records: Diagnostics retained within the configured budget.
    """

    maximum: int
    records: list[ImportDiagnostic] = field(default_factory=list[ImportDiagnostic])

    def append(self, diagnostic: ImportDiagnostic) -> None:
        """Append a diagnostic within the configured resource budget.

        Args:
            diagnostic: Structured diagnostic with code and source location.

        Returns:
            None.

        Raises:
            DiagnosticBudgetExceeded: If the diagnostic budget is exhausted.
        """
        if len(self.records) == self.maximum:
            self.records[-1] = ImportDiagnostic(
                "RESOURCE_LIMIT_EXCEEDED",
                Severity.ERROR,
                diagnostic.json_path,
                "Resource budget exceeded: max_diagnostics",
                diagnostic.sample_index,
            )
            raise DiagnosticBudgetExceeded
        self.records.append(diagnostic)

    def add(
        self,
        code: str,
        path: tuple[str | int, ...],
        message: str,
        *,
        severity: Severity = Severity.WARNING,
        index: int | None = None,
    ) -> None:
        """Create and append a structured diagnostic.

        Args:
            code: Stable diagnostic code used to select its localized explanation.
            path: Object keys and sequence indices identifying the source JSON location.
            message: Text or diagnostic message to present or validate.
            severity: Diagnostic severity.
            index: Source or collection index selected for this operation.

        Returns:
            None.
        """
        self.append(ImportDiagnostic(code, severity, json_pointer(*path), message, index))

    def failure(self, source: SourceEnvelope) -> ImportFailure:
        """Create an import failure from the retained diagnostics.

        Args:
            source: Input recording, retained source representation or source path to read.

        Returns:
            Import failure containing the retained diagnostics and source envelope.
        """
        version = source.root.get("schemaVersion") if source.root is not None else None
        return ImportFailure(
            self.records,
            source=source,
            schema_version=version if isinstance(version, str) and version else None,
        )
