"""Discriminated full-import results; their construction performs no decoding or I/O.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from ride_forces_analyzer.domain._validation import has_type
from ride_forces_analyzer.domain.models import Recording
from ride_forces_analyzer.domain.source import SourceEnvelope

from .diagnostics import ImportDiagnostic, Severity, ordered_diagnostics


@dataclass(frozen=True, slots=True, init=False)
class ImportSuccess:
    success: Literal[True] = field(init=False)
    recording: Recording = field(repr=False)
    diagnostics: tuple[ImportDiagnostic, ...]

    def __init__(self, recording: Recording, diagnostics: Sequence[ImportDiagnostic] = ()) -> None:
        if not has_type(recording, Recording):
            raise TypeError("Import success requires a complete typed Recording")
        ordered = ordered_diagnostics(diagnostics)
        if any(item.severity is Severity.ERROR for item in ordered):
            raise ValueError("Successful results cannot contain error diagnostics")
        object.__setattr__(self, "success", True)
        object.__setattr__(self, "recording", recording)
        object.__setattr__(self, "diagnostics", ordered)

    @property
    def schema_version(self) -> str:
        return self.recording.schema_version

    @property
    def byte_count(self) -> int:
        return self.recording.source.provenance.byte_count

    @property
    def source_sha256(self) -> str:
        return self.recording.source.provenance.sha256


@dataclass(frozen=True, slots=True, init=False)
class ImportFailure:
    success: Literal[False] = field(init=False)
    diagnostics: tuple[ImportDiagnostic, ...]
    source: SourceEnvelope | None = field(repr=False)
    schema_version: str | None

    def __init__(
        self,
        diagnostics: Sequence[ImportDiagnostic],
        *,
        source: SourceEnvelope | None = None,
        schema_version: str | None = None,
    ) -> None:
        ordered = ordered_diagnostics(diagnostics)
        if not any(item.severity is Severity.ERROR for item in ordered):
            raise ValueError("Failure requires at least one error diagnostic")
        if source is not None and not has_type(source, SourceEnvelope):
            raise TypeError("Failure source must be an owned SourceEnvelope or None")
        if schema_version is not None and (not has_type(schema_version, str) or not schema_version):
            raise ValueError("Known failure schema version must be a nonempty string")
        object.__setattr__(self, "diagnostics", ordered)
        object.__setattr__(self, "success", False)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "schema_version", schema_version)

    @property
    def recording(self) -> None:
        return None

    @property
    def byte_count(self) -> int | None:
        return self.source.provenance.byte_count if self.source is not None else None

    @property
    def source_sha256(self) -> str | None:
        return self.source.provenance.sha256 if self.source is not None else None


type ImportResult = ImportSuccess | ImportFailure
