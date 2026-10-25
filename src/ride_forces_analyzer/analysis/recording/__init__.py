"""Public recording-analysis contracts and explicit structural validation.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from .configuration import (
    AnalysisStage,
    StageConfiguration,
    AnalysisConfiguration,
)
from .stages import (
    AvailabilityState,
    EventEvaluationState,
    VerticalContext,
    AnalysisTime,
    StageAvailability,
    AnalysisQuality,
    ForceChannels,
    ProjectedForces,
    SmoothedForces,
    ForceSeries,
    OrientationSeries,
    ForceInput,
    SampleContext,
    AirtimeEvent,
    EventAnalysis,
)
from .snapshot import (
    ForceSample,
    AnalyzedSample,
    RecordingAnalysis,
)
from .notifications import (
    RequestStatus,
    AnalysisState,
    AnalysisUpdated,
    AnalysisInvalidated,
    AnalysisFailed,
    AnalysisNotification,
)
from .validation import (
    validate_configuration,
)

__all__ = [
    "AirtimeEvent",
    "AnalysisConfiguration",
    "AnalysisFailed",
    "AnalysisInvalidated",
    "AnalysisNotification",
    "AnalysisQuality",
    "AnalysisStage",
    "AnalysisState",
    "AnalysisTime",
    "AnalysisUpdated",
    "AnalyzedSample",
    "AvailabilityState",
    "EventAnalysis",
    "EventEvaluationState",
    "ForceChannels",
    "ForceInput",
    "ForceSample",
    "ForceSeries",
    "OrientationSeries",
    "ProjectedForces",
    "RecordingAnalysis",
    "RequestStatus",
    "SampleContext",
    "SmoothedForces",
    "StageAvailability",
    "StageConfiguration",
    "VerticalContext",
    "validate_configuration",
]
