"""Shared bounded diagnostics for standalone subsets and full import calls."""

from dataclasses import dataclass, field

from ride_forces_analyzer.domain import SourceEnvelope

from .diagnostics import ImportDiagnostic, Severity, json_pointer
from .result import ImportFailure


class DiagnosticBudgetExceeded(Exception):
    pass


@dataclass(slots=True)
class DiagnosticBudget:
    maximum: int
    records: list[ImportDiagnostic] = field(default_factory=list[ImportDiagnostic])

    def append(self, diagnostic: ImportDiagnostic) -> None:
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
        self.append(ImportDiagnostic(code, severity, json_pointer(*path), message, index))

    def failure(self, source: SourceEnvelope) -> ImportFailure:
        version = source.root.get("schemaVersion") if source.root is not None else None
        return ImportFailure(
            self.records,
            source=source,
            schema_version=version if isinstance(version, str) and version else None,
        )
