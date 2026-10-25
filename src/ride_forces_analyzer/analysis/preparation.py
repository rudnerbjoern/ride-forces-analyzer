"""Prepare and reuse immutable analysis stages using the source-app policy.

Recording contracts and structural validation live in analysis.recording.
This module owns numerical stage orchestration and delegates event evaluation
without requiring recording models to import the event implementation.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import replace
from datetime import datetime

import numpy as np

from ride_forces_analyzer import __version__
from ride_forces_analyzer.domain import RecordingFormat
from ride_forces_analyzer.importers import ImportSuccess, Severity

from . import airtime, events as event_detection
from ._validation import require as _require, require_type as _typed
from .calibration import (
    prepare_calibration_basis,
)
from .models import (
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisProvenance,
    CapabilityState,
    EvidenceState,
    ProfileName,
    SampleValues,
    TimeBasis,
    TimeBasisKind,
    UnitAssignment,
    UnitLabel,
)
from .orientation import orientation_degrees
from .projection import project_directions, source_directions
from .smoothing import centered_mean, combined_force

from .recording import (
    AnalysisConfiguration,
    AnalysisQuality,
    AnalysisStage,
    AnalysisTime,
    AvailabilityState,
    ForceChannels,
    ForceSeries,
    OrientationSeries,
    ProjectedForces,
    RecordingAnalysis,
    SampleContext,
    SmoothedForces,
    StageAvailability,
    StageConfiguration,
    VerticalContext,
    validate_configuration,
)


def source_app_configuration() -> AnalysisConfiguration:
    """Return the existing owner-adopted source-app policy and default window.

    Returns:
        Versioned source-direction projection, centered mean (11 samples),
        independent gravity tilt and current provisional context rules.
        This opt-in policy does not qualify universal physical rider loading.
    """
    return AnalysisConfiguration(
        AnalysisProfile(
            ProfileName.RIDER_CALIBRATED,
            policy_references=("ADR-0006: source-app projection and centered mean",),
            assumptions=("Source acceleration interpreted as g under the owner-adopted policy",),
            allow_provisional=True,
        ),
        StageConfiguration("source-direction-unit-projection", "1"),
        StageConfiguration("centered-mean", "1", (("window_samples", 11),)),
        StageConfiguration("source-gravity-tilt", "1"),
        StageConfiguration("vertical-context", "1"),
    )


def prepare_recording_analysis(
    source: ImportSuccess,
    configuration: AnalysisConfiguration,
    *,
    revision: int,
    calculation_time: datetime,
) -> RecordingAnalysis:
    """Prepare a validated immutable snapshot using the existing source-app policy.

    Args:
        source: Successful lossless import retaining original bytes and metadata.
        configuration: Effective stage configurations and scientific policy.
        revision: Service request revision assigned to the planned result.
        calculation_time: Caller-supplied timezone-aware UTC calculation time.

    Returns:
        RecordingAnalysis retaining the complete source, inferred time axis,
        independent orientation, projected/smoothed forces and prepared context.
        Missing prerequisites retain raw values and explicit exclusion reasons.
        Configured airtime-events version 1 evaluates separate domain episodes.
        Disabled/unavailable event stages retain NOT_EVALUATED with a reason.

    Raises:
        TypeError: Source/configuration has an incompatible type.
        ValueError: Configuration, revision or UTC calculation time is invalid.
            Only version 1 of the documented algorithms/default context rules
            is supported. Numerical force range failures exclude affected stages.
    """
    return _prepare_analysis(
        source,
        configuration,
        revision=revision,
        calculation_time=calculation_time,
    )


def reconfigure_recording_analysis(
    previous: RecordingAnalysis,
    configuration: AnalysisConfiguration,
    *,
    revision: int,
    calculation_time: datetime,
) -> RecordingAnalysis:
    """Reconfigure a validated snapshot while reusing compatible immutable stages.

    Args:
        previous: Snapshot supplying the original source and reusable stages.
        configuration: Requested effective analysis configuration.
        revision: Request revision, strictly greater than the previous snapshot's.
        calculation_time: Timezone-aware UTC time for recalculated stages.

    Returns:
        New validated snapshot sharing unchanged stages and their provenance.
        The previous snapshot remains unchanged; no history is retained.

    Raises:
        TypeError: Snapshot or configuration fields have incompatible types.
        ValueError: Snapshot, configuration, revision or calculation time is invalid.
    """
    previous.validate()
    _require(
        type(revision) is int and revision > previous.revision,
        "Reconfiguration revision must increase",
    )
    return _prepare_analysis(
        previous.source,
        configuration,
        revision=revision,
        calculation_time=calculation_time,
        previous=previous,
    )


def _prepare_analysis(
    source: ImportSuccess,
    configuration: AnalysisConfiguration,
    *,
    revision: int,
    calculation_time: datetime,
    previous: RecordingAnalysis | None = None,
) -> RecordingAnalysis:
    """Prepare changed stages; retain compatible dependencies, never old snapshots."""
    _typed(source, ImportSuccess)
    _typed(configuration, AnalysisConfiguration)
    _require(type(revision) is int and revision >= 0, "Invalid snapshot revision")
    validate_configuration(configuration)
    if configuration.ride_bounds is not None:
        _require(
            configuration.ride_bounds[1] < len(source.recording.motion.acceleration),
            "Ride markers outside recording",
        )
    window = _preparation_window(configuration)
    if configuration.events is not None:
        event_detection.event_rules(configuration.events)
    provenance = AnalysisProvenance(
        source.recording.source.provenance,
        f"{__version__}; numpy={np.__version__}",
        "recording-analysis",
        calculation_time,
    )
    motion = source.recording.motion
    time = (
        previous.time
        if previous is not None
        else AnalysisTime(
            TimeBasis(TimeBasisKind.INFERRED_UNIFORM, motion.sample_rate),
            tuple(range(len(motion.acceleration))),
            source.recording.indices.start,
        )
    )
    raw_mode = configuration.profile.name is ProfileName.RAW_DEVICE_ONLY
    evidence = configuration.profile.policy_references + configuration.profile.assumptions
    if source.recording.source_format is RecordingFormat.RFDB:
        evidence += (
            "RFDB calibration Y/X/Z maps to provisional vertical/lateral/longitudinal directions",
        )
    source_vertical, lateral, longitudinal = source_directions(source.recording)
    vertical = source_vertical
    same_policy = previous is not None and configuration.profile == previous.configuration.profile
    same_calibration = (
        previous is not None and configuration.calibration == previous.configuration.calibration
    )
    calibration = (
        previous.calibration
        if previous is not None and same_calibration
        else prepare_calibration_basis(
            source,
            configuration.calibration,
            calculation_time=calculation_time,
        )
    )
    if calibration is not None:
        vertical, lateral, longitudinal = calibration.directions
    if (
        previous is not None
        and same_policy
        and same_calibration
        and configuration.projection == previous.configuration.projection
    ):
        projected = previous.forces.projected
    else:
        raw = None
        projection_availability = StageAvailability(AvailabilityState.AVAILABLE)
        if raw_mode:
            projection_availability = _unavailable(
                "RAW_PROFILE",
                "Raw profile excludes derived forces",
            )
        elif vertical is None or lateral is None or longitudinal is None:
            projection_availability = _unavailable(
                "PROJECTION_UNAVAILABLE",
                "Source directions are incomplete",
            )
        else:
            try:
                raw = project_directions(motion.acceleration, (vertical, lateral, longitudinal))
            except ValueError as error:
                projection_availability = _unavailable("PROJECTION_UNAVAILABLE", str(error))
        projected = ProjectedForces(
            source,
            time,
            configuration.projection,
            projection_availability,
            _force_channels(raw) if raw is not None else None,
            UnitAssignment(UnitLabel.DIMENSIONLESS, EvidenceState.ASSUMED, evidence)
            if not raw_mode
            else UnitAssignment(),
            _prepared_quality("projection", projection_availability),
            replace(provenance, algorithm=configuration.projection.algorithm)
            if raw is not None
            else None,
            calibration,
        )
    if (
        previous is not None
        and projected is previous.forces.projected
        and configuration.smoothing == previous.configuration.smoothing
    ):
        smoothed = previous.forces.smoothed
    else:
        filtered = None
        combined_values = None
        smoothing_availability = StageAvailability(AvailabilityState.AVAILABLE)
        channels = projected.channels
        if channels is None:
            smoothing_availability = _unavailable(
                "SMOOTHING_UNAVAILABLE",
                "Projection is unavailable",
            )
        else:
            try:
                filtered = tuple(
                    centered_mean(tuple(float(value) for value in axis.values), window)
                    for axis in channels
                )
            except ValueError as error:
                filtered = None
                smoothing_availability = _unavailable("SMOOTHING_UNAVAILABLE", str(error))
        if filtered is not None:
            try:
                combined_values = combined_force(motion.acceleration, window)
            except ValueError:
                combined_values = (None,) * len(motion.acceleration)
        combined_diagnostics = tuple(
            AnalysisDiagnostic(
                "COMBINED_SAMPLE_UNAVAILABLE",
                Severity.WARNING,
                "Device-axis smoothing or magnitude exceeds finite display range",
                "combined",
                index,
            )
            for index, value in enumerate(combined_values or ())
            if value is None
        )
        smoothing_quality = _prepared_quality("smoothing", smoothing_availability)
        smoothed = SmoothedForces(
            projected,
            configuration.smoothing,
            smoothing_availability,
            _force_channels(filtered) if filtered is not None else None,
            replace(
                smoothing_quality,
                diagnostics=smoothing_quality.diagnostics + combined_diagnostics,
            ),
            replace(provenance, algorithm=configuration.smoothing.algorithm)
            if filtered is not None
            else None,
            SampleValues(
                np.array([np.nan if value is None else value for value in combined_values]),
                valid_rows=tuple(value is not None for value in combined_values),
            )
            if combined_values is not None
            else None,
        )
    if (
        previous is not None
        and same_policy
        and configuration.orientation == previous.configuration.orientation
        and configuration.calibration.gravity_index
        == previous.configuration.calibration.gravity_index
    ):
        orientation = previous.orientation
    else:
        orientation_availability = StageAvailability(AvailabilityState.AVAILABLE)
        orientation_values = None
        orientation_diagnostics: tuple[AnalysisDiagnostic, ...] = ()
        if (
            raw_mode
            or motion.gravity is None
            or vertical is None
            or (vertical.x, vertical.y, vertical.z) == (0.0, 0.0, 0.0)
        ):
            orientation_availability = _unavailable(
                "ORIENTATION_UNAVAILABLE",
                "Orientation requires gravity, a vertical direction and an opt-in profile",
            )
        else:
            angles = orientation_degrees(
                source.recording,
                vertical_direction=(
                    vertical
                    if configuration.calibration.gravity_index is not None
                    else source_vertical
                ),
            )
            orientation_values = SampleValues(
                np.array([np.nan if value is None else value for value in angles]),
                valid_rows=tuple(value is not None for value in angles),
            )
            orientation_diagnostics = tuple(
                AnalysisDiagnostic(
                    "ORIENTATION_SAMPLE_UNAVAILABLE",
                    Severity.WARNING,
                    "Zero gravity has no orientation",
                    "orientation",
                    index,
                )
                for index, value in enumerate(angles)
                if value is None
            )
        orientation_quality = _prepared_quality("orientation", orientation_availability)
        orientation = OrientationSeries(
            source,
            time,
            configuration.orientation,
            orientation_availability,
            orientation_values,
            UnitAssignment(UnitLabel.DEGREES, EvidenceState.ASSUMED, evidence)
            if not raw_mode
            else UnitAssignment(),
            replace(
                orientation_quality,
                diagnostics=orientation_quality.diagnostics + orientation_diagnostics,
            ),
            replace(provenance, algorithm=configuration.orientation.algorithm)
            if orientation_values is not None
            else None,
            configuration.calibration.gravity_index,
        )
    context_input = (
        projected if configuration.context_input is AnalysisStage.PROJECTION else smoothed
    )
    if (
        previous is not None
        and context_input is previous.context.input
        and configuration.context == previous.configuration.context
    ):
        context = previous.context
    else:
        context_availability = StageAvailability(AvailabilityState.AVAILABLE)
        labels = None
        channels = context_input.channels
        if channels is None:
            context_availability = _unavailable(
                "CONTEXT_UNAVAILABLE",
                "Selected force input is unavailable",
            )
        else:
            values = tuple(float(value) for value in channels[0].values)
            labels = tuple(
                VerticalContext(label.lower().replace(" ", "_"))
                for label in airtime.AirtimeContext.prepare(values, motion.sample_rate.value).labels
            )
        context = SampleContext(
            context_input,
            configuration.context,
            context_availability,
            labels,
            _prepared_quality("context", context_availability),
            replace(provenance, algorithm=configuration.context.algorithm)
            if labels is not None
            else None,
        )
    events_input = projected if configuration.events_input is AnalysisStage.PROJECTION else smoothed
    if (
        previous is not None
        and events_input is previous.events.input
        and configuration.events == previous.configuration.events
    ):
        events = previous.events
    else:
        events = event_detection.evaluate_events(
            events_input,
            configuration.events,
            motion.sample_rate.value,
            provenance,
        )
    qualities = (
        projected.quality,
        smoothed.quality,
        orientation.quality,
        context.quality,
        events.quality,
    )
    result = RecordingAnalysis(
        source,
        configuration,
        time,
        previous.forces
        if previous is not None
        and projected is previous.forces.projected
        and smoothed is previous.forces.smoothed
        else ForceSeries(projected, smoothed),
        orientation,
        context,
        events,
        AnalysisQuality(
            capabilities=(
                (("calibration", calibration.references.capability),)
                if calibration is not None
                else ()
            )
            + tuple(item for quality in qualities for item in quality.capabilities),
            diagnostics=tuple(item for quality in qualities for item in quality.diagnostics),
        ),
        revision,
        calibration,
    )
    result.validate()
    return result


def _preparation_window(configuration: AnalysisConfiguration) -> int:
    """Admit supported algorithms/parameters and return the centered-mean window."""
    for stage, algorithm in (
        (configuration.projection, "source-direction-unit-projection"),
        (configuration.smoothing, "centered-mean"),
        (configuration.orientation, "source-gravity-tilt"),
        (configuration.context, "vertical-context"),
    ):
        _require(
            stage.algorithm == algorithm and stage.version == "1",
            "Unsupported stage algorithm/version",
        )
    _require(
        not configuration.projection.parameters and not configuration.orientation.parameters,
        "Projection/orientation parameters are unsupported",
    )
    smoothing = dict(configuration.smoothing.parameters)
    _require(smoothing.keys() <= {"window_samples"}, "Unsupported smoothing parameters")
    window = smoothing.get("window_samples", 11)
    _require(
        type(window) is int and 1 <= window <= 51 and window % 2 == 1,
        "Smoothing window must be an odd integer from 1 through 51",
    )
    defaults = {
        "floater_bound_g": airtime.FLOATER_BOUND_G,
        "strong_bound_g": airtime.STRONG_BOUND_G,
        "onset_window_seconds": airtime.ONSET_WINDOW_SECONDS,
        "ejector_onset_g_per_second": airtime.EJECTOR_ONSET_G_PER_SECOND,
        "onset_memory_seconds": airtime.ONSET_MEMORY_SECONDS,
        "context_confirm_seconds": airtime.CONTEXT_CONFIRM_SECONDS,
        "floater_exit_bound_g": airtime.FLOATER_EXIT_BOUND_G,
        "strong_exit_bound_g": airtime.STRONG_EXIT_BOUND_G,
    }
    for key, value in configuration.context.parameters:
        _require(
            key in defaults and type(value) in (int, float) and value == defaults[key],
            "Unsupported context parameters; version 1 uses the existing default rules",
        )
    profile = configuration.profile
    _require(
        profile.name in (ProfileName.RAW_DEVICE_ONLY, ProfileName.RIDER_CALIBRATED),
        "Unsupported recording analysis profile",
    )
    if profile.name is ProfileName.RIDER_CALIBRATED:
        _require(profile.allow_provisional, "Source-app analysis requires provisional permission")
    assert isinstance(window, int)
    return window


def _unavailable(code: str, message: str) -> StageAvailability:
    """Retain an explicit whole-stage exclusion without manufacturing payloads."""
    return StageAvailability(
        AvailabilityState.UNAVAILABLE,
        AnalysisDiagnostic(code, Severity.WARNING, message),
    )


def _prepared_quality(identifier: str, availability: StageAvailability) -> AnalysisQuality:
    """Keep source-app derivations provisional, independently of payload presence."""
    return AnalysisQuality(
        capabilities=(
            (
                identifier,
                CapabilityState.PROVISIONAL
                if availability.state is AvailabilityState.AVAILABLE
                else CapabilityState.UNAVAILABLE,
            ),
        ),
        diagnostics=(availability.reason,) if availability.reason is not None else (),
    )


def _force_channels(values: tuple[tuple[float, ...], ...]) -> ForceChannels:
    """Own immutable scalar buffers without changing existing float64 results."""
    return (
        SampleValues(np.array(values[0])),
        SampleValues(np.array(values[1])),
        SampleValues(np.array(values[2])),
    )
