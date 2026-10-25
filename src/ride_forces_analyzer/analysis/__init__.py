"""Lazy public analysis models; raw extrema do not load optional numerical libraries.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import (
        AnalysisChannel,
        AnalysisDiagnostic,
        AnalysisProfile,
        AnalysisProvenance,
        AnalysisResult,
        CapabilityState,
        EvidenceState,
        FrameLabel,
        ParameterValue,
        ProcessingKind,
        ProfileName,
        QuantityKind,
        ResultValidity,
        SampleValues,
        SourceSequence,
        TimeBasis,
        TimeBasisKind,
        UnitAssignment,
        UnitLabel,
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


def __getattr__(name: str) -> object:
    """Load public model exports only when requested, preserving raw-only imports.

    Args:
        name: Public analysis model name to resolve.

    Returns:
        The shared model object, cached on this package for subsequent access.

    Raises:
        AttributeError: The name is not a declared public model export.
        ModuleNotFoundError: Model access requires an unavailable optional dependency.
    """
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value: object = getattr(import_module(f"{__name__}.models"), name)
    globals()[name] = value
    return value
