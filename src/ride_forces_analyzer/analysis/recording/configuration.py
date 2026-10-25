"""Analysis configuration contracts and reusable stage identifiers.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from enum import StrEnum


from ..calibration import (
    CalibrationOverrides,
)
from ..models import (
    AnalysisProfile,
    ParameterValue,
)


class AnalysisStage(StrEnum):
    """Stable identifiers for independently reusable or invalidated analysis stages.

    Attributes:
        TIME: Named value for time (`time`).
        CALIBRATION: Named value for calibration (`calibration`).
        PROJECTION: Named value for projection (`projection`).
        SMOOTHING: Named value for smoothing (`smoothing`).
        ORIENTATION: Named value for orientation (`orientation`).
        CONTEXT: Named value for context (`context`).
        EVENTS: Named value for events (`events`).
    """

    TIME = "time"
    CALIBRATION = "calibration"
    PROJECTION = "projection"
    SMOOTHING = "smoothing"
    ORIENTATION = "orientation"
    CONTEXT = "context"
    EVENTS = "events"


@dataclass(frozen=True, slots=True)
class StageConfiguration:
    """Identify a stage algorithm and its effective scalar parameters.

    Attributes:
        algorithm: Stable algorithm identifier, without presentation settings.
        version: Version of that algorithm's calculation contract.
        parameters: Immutable name/value pairs, such as window_samples for
            smoothing. Snapshot validation checks scalar types and unique names;
            algorithm-specific parameter admission remains a calculation concern.
    """

    algorithm: str
    version: str
    parameters: tuple[tuple[str, ParameterValue], ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisConfiguration:
    """Collect scientific policy, stage configurations and declared dependencies.

    Attributes:
        profile: Existing analysis policy, evidence and provisional permissions.
        projection: Source-axis projection configuration.
        smoothing: Force filter configuration, independent of orientation.
        orientation: Source-gravity tilt configuration.
        context: Sample-label and stabilization configuration.
        events: Event-rule configuration, or None when no rules are configured.
        context_input: Force stage consumed by context; projection or smoothing.
        events_input: Force stage consumed by event detection when configured.
        ride_bounds: Optional inclusive user start/end markers; original source
            markers and full-history numerical stages remain unchanged.
        calibration: Typed custom Gravity/Incline references; default retains
            the exact original source directions and projection policy.
    """

    profile: AnalysisProfile
    projection: StageConfiguration
    smoothing: StageConfiguration
    orientation: StageConfiguration
    context: StageConfiguration
    events: StageConfiguration | None = None
    context_input: AnalysisStage = AnalysisStage.SMOOTHING
    events_input: AnalysisStage = AnalysisStage.SMOOTHING
    ride_bounds: tuple[int, int] | None = None
    calibration: CalibrationOverrides = CalibrationOverrides()
