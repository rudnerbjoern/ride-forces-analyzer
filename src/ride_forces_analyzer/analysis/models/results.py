"""Analysis results, diagnostics, provenance and structural result validity.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


from ride_forces_analyzer.domain import SourceProvenance
from ride_forces_analyzer.validation.checks import has_type, validate_diagnostic_code
from ride_forces_analyzer.importers import ImportSuccess, Severity

from ride_forces_analyzer.validation.checks import validate_text as _text, validate_enum as _enum
from .channels import AnalysisChannel, CapabilityState, ProcessingKind, QuantityKind, SourceSequence
from .profiles import AnalysisProfile, ProfileName


@dataclass(frozen=True, slots=True)
class AnalysisDiagnostic:
    """Analysis diagnostic contract and owned data.

    Attributes:
        code: Stable diagnostic code used to select its localized explanation.
        severity: Diagnostic severity.
        message: Text or diagnostic message to present or validate.
        channel_id: Identifier of the affected channel.
        source_index: Original source-sequence index associated with the value.
    """

    code: str
    severity: Severity
    message: str
    channel_id: str | None = None
    source_index: int | None = None

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Diagnostic code must be a stable uppercase identifier. Diagnostic
                index must be a nonnegative integer. Indexed diagnostics require a
                channel/sequence reference.
        """
        validate_diagnostic_code(self.code)
        _enum(self.severity, Severity)
        _text(self.message, "Diagnostic message")
        if self.channel_id is not None:
            _text(self.channel_id, "Diagnostic channel")
        if self.source_index is not None:
            if type(self.source_index) is not int or self.source_index < 0:
                raise ValueError("Diagnostic index must be a nonnegative integer")
            if self.channel_id is None:
                raise ValueError("Indexed diagnostics require a channel/sequence reference")


@dataclass(frozen=True, slots=True)
class AnalysisProvenance:
    """Analysis provenance contract and owned data.

    Attributes:
        source: Retained input identity or image; its original representation remains
            owned.
        engine_version: Version of the analysis engine producing the values.
        algorithm: Identifier of the algorithm used by the stage.
        calculation_time: Aware timestamp recorded in calculation provenance.
    """

    source: SourceProvenance
    engine_version: str
    algorithm: str
    calculation_time: datetime

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            TypeError: Analysis requires retained M2 source provenance.
            ValueError: Calculation time must be explicit timezone-aware UTC.
        """
        if not has_type(self.source, SourceProvenance):
            raise TypeError("Analysis requires retained M2 source provenance")
        _text(self.engine_version, "Engine version")
        _text(self.algorithm, "Algorithm identifier")
        if not has_type(
            self.calculation_time,
            datetime,
        ) or self.calculation_time.utcoffset() != timedelta(0):
            raise ValueError("Calculation time must be explicit timezone-aware UTC")


class ResultValidity(StrEnum):
    """Result validity contract and owned data.

    Attributes:
        VALID: Named value for valid (`valid`).
        RESTRICTED: Named value for restricted (`restricted`).
        INVALID: Named value for invalid (`invalid`).
    """

    VALID = "valid"
    RESTRICTED = "restricted"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Analysis result contract and owned data.

    Attributes:
        source: Retained input identity or image; its original representation remains
            owned.
        profile: Explicit analysis or codec profile selected for this data product.
        provenance: Source identity, processing configuration and calculation evidence.
        channels: Prepared channels to inspect or display.
        diagnostics: Structured diagnostics retaining stable codes and source locations.
        schema_version: Version identifying the admitted source or stored document
            contract.
    """

    source: ImportSuccess = field(repr=False)
    profile: AnalysisProfile
    provenance: AnalysisProvenance
    channels: tuple[AnalysisChannel, ...]
    diagnostics: tuple[AnalysisDiagnostic, ...] = ()
    schema_version: str = "1"

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            TypeError: Analysis results require full M2 import success, not a subset or
                failure. Analysis results require typed profile and provenance. Analysis
                diagnostics must be typed values.
            ValueError: Analysis provenance must match the complete M2 source. Result requires
                nonempty typed channels. Channel identifiers must be unique. Channel indices
                must be bounded independently by their source sequence. The raw default cannot
                expose physical or filtered channels. Provisional channels require explicit
                profile permission and assumptions. Diagnostic channel must exist in the
                result. Diagnostic index exceeds its independent source sequence.
        """
        if not has_type(self.source, ImportSuccess):
            raise TypeError(
                "Analysis results require full M2 import success, not a subset or failure",
            )
        if not has_type(self.profile, AnalysisProfile) or not has_type(
            self.provenance,
            AnalysisProvenance,
        ):
            raise TypeError("Analysis results require typed profile and provenance")
        if self.provenance.source != self.source.recording.source.provenance:
            raise ValueError("Analysis provenance must match the complete M2 source")
        _text(self.schema_version, "Result schema")
        channels = tuple(self.channels)
        if not channels or any(not has_type(channel, AnalysisChannel) for channel in channels):
            raise ValueError("Result requires nonempty typed channels")
        by_id = {channel.identifier: channel for channel in channels}
        if len(by_id) != len(channels):
            raise ValueError("Channel identifiers must be unique")
        recording = self.source.recording
        lengths = {
            SourceSequence.ACCELERATION: len(recording.motion.acceleration),
            SourceSequence.GRAVITY: len(recording.motion.gravity)
            if recording.motion.gravity is not None
            else 0,
            SourceSequence.GPS: len(recording.gps.entries) if recording.gps is not None else 0,
        }
        for channel in channels:
            if any(index >= lengths[channel.source_sequence] for index in channel.source_indices):
                raise ValueError(
                    "Channel indices must be bounded independently by their source sequence",
                )
            if self.profile.name is ProfileName.RAW_DEVICE_ONLY and (
                channel.quantity is not QuantityKind.SOURCE_VALUES
                or channel.processing is not ProcessingKind.RAW
            ):
                raise ValueError("The raw default cannot expose physical or filtered channels")
            if channel.state is CapabilityState.PROVISIONAL and not self.profile.allow_provisional:
                raise ValueError(
                    "Provisional channels require explicit profile permission and assumptions",
                )
        diagnostics = tuple(self.diagnostics)
        if any(not has_type(item, AnalysisDiagnostic) for item in diagnostics):
            raise TypeError("Analysis diagnostics must be typed values")
        for item in diagnostics:
            if item.channel_id is not None:
                if item.channel_id not in by_id:
                    raise ValueError("Diagnostic channel must exist in the result")
                if (
                    item.source_index is not None
                    and item.source_index >= lengths[by_id[item.channel_id].source_sequence]
                ):
                    raise ValueError("Diagnostic index exceeds its independent source sequence")
        ranks = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        ordered = tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    ranks[item.severity],
                    item.channel_id or "",
                    item.source_index if item.source_index is not None else -1,
                    item.code,
                ),
            ),
        )
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "diagnostics", ordered)

    @property
    def validity(self) -> ResultValidity:
        """Structural result status, never blanket scientific certification.

        Returns:
            Structural validity of the result, separate from scientific qualification.
        """
        if any(item.severity is Severity.ERROR for item in self.diagnostics) or any(
            channel.state is CapabilityState.INVALID for channel in self.channels
        ):
            return ResultValidity.INVALID
        if any(channel.state is not CapabilityState.VERIFIED for channel in self.channels):
            return ResultValidity.RESTRICTED
        return ResultValidity.VALID
