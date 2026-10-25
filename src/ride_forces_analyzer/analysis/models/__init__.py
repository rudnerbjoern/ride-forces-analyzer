"""Public immutable analysis contracts; calculations live in dedicated modules.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from .samples import (
    SampleValues,
)
from .channels import (
    CapabilityState,
    QuantityKind,
    UnitLabel,
    EvidenceState,
    FrameLabel,
    SourceSequence,
    ProcessingKind,
    TimeBasisKind,
    UnitAssignment,
    TimeBasis,
    AnalysisChannel,
)
from .profiles import (
    ParameterValue,
    ProfileName,
    AnalysisProfile,
)
from .results import (
    AnalysisDiagnostic,
    AnalysisProvenance,
    ResultValidity,
    AnalysisResult,
)

__all__ = [
    "AnalysisChannel",
    "AnalysisDiagnostic",
    "AnalysisProfile",
    "AnalysisProvenance",
    "AnalysisResult",
    "CapabilityState",
    "EvidenceState",
    "FrameLabel",
    "ParameterValue",
    "ProcessingKind",
    "ProfileName",
    "QuantityKind",
    "ResultValidity",
    "SampleValues",
    "SourceSequence",
    "TimeBasis",
    "TimeBasisKind",
    "UnitAssignment",
    "UnitLabel",
]
