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
    """Import success contract and owned data.

    Attributes:
        success: Discriminator identifying whether the import stage succeeded.
        recording: Validated recording whose original source data remains unchanged.
        diagnostics: Structured diagnostics retaining stable codes and source locations.
    """

    success: Literal[True] = field(init=False)
    recording: Recording = field(repr=False)
    diagnostics: tuple[ImportDiagnostic, ...]

    def __init__(self, recording: Recording, diagnostics: Sequence[ImportDiagnostic] = ()) -> None:
        """Initialize import success and its owned state.

        Args:
            recording: Validated recording whose original source data remains unchanged.
            diagnostics: Structured diagnostics or their collector.

        Returns:
            None.

        Raises:
            TypeError: Import success requires a complete typed Recording.
            ValueError: Successful results cannot contain error diagnostics.
        """
        if not has_type(recording, Recording):
            raise TypeError("Import success requires a complete typed Recording")
        ordered = ordered_diagnostics(diagnostics)
        if any(item.severity is Severity.ERROR for item in ordered):
            raise ValueError("Successful results cannot contain error diagnostics")
        object.__setattr__(self, "success", True)
        object.__setattr__(self, "recording", recording)
        object.__setattr__(self, "diagnostics", ordered)

    @property
    def schema_version(self) -> str | None:
        """Return the retained declared or admitted source schema version.

        Returns:
            The retained declared or admitted source schema version.
        """
        return self.recording.schema_version

    @property
    def byte_count(self) -> int:
        """Return the original supplied source byte count.

        Returns:
            The original supplied source byte count.
        """
        return self.recording.source.provenance.byte_count

    @property
    def source_sha256(self) -> str:
        """Return the SHA-256 identity of the original supplied source bytes.

        Returns:
            The sha-256 identity of the original supplied source bytes.
        """
        return self.recording.source.provenance.sha256


@dataclass(frozen=True, slots=True, init=False)
class ImportFailure:
    """Import failure contract and owned data.

    Attributes:
        success: Discriminator identifying whether the import stage succeeded.
        diagnostics: Structured diagnostics retaining stable codes and source locations.
        source: Retained input identity or image; its original representation remains
            owned.
        schema_version: Version identifying the admitted source or stored document
            contract.
    """

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
        """Initialize import failure and its owned state.

        Args:
            diagnostics: Structured diagnostics or their collector.
            source: Input recording, retained source representation or source path to read.
            schema_version: Admitted document schema version.

        Returns:
            None.

        Raises:
            ValueError: Failure requires at least one error diagnostic. Known failure schema
                version must be a nonempty string.
            TypeError: Failure source must be an owned SourceEnvelope or None.
        """
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
        """Return the complete validated recording owned by this import result.

        Returns:
            None.
        """
        return None

    @property
    def byte_count(self) -> int | None:
        """Return the original supplied source byte count.

        Returns:
            The original supplied source byte count.
        """
        return self.source.provenance.byte_count if self.source is not None else None

    @property
    def source_sha256(self) -> str | None:
        """Return the SHA-256 identity of the original supplied source bytes.

        Returns:
            The sha-256 identity of the original supplied source bytes.
        """
        return self.source.provenance.sha256 if self.source is not None else None


type ImportResult = ImportSuccess | ImportFailure
