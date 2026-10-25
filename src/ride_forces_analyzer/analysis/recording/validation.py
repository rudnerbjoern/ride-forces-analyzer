"""Structural recording validation without calculation, mutation or scientific certification.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from math import isfinite

from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.importers import ImportSuccess

from ride_forces_analyzer.validation.checks import require as _require, require_type as _typed
from ..calibration import (
    CalibrationBasis,
    CalibrationOverrides,
    CalibrationReferences,
    REFERENCE_WINDOW_SAMPLES,
)
from ..models import (
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisProvenance,
    AnalysisResult,
    CapabilityState,
    SampleValues,
    TimeBasis,
    TimeBasisKind,
    UnitAssignment,
    UnitLabel,
)
from ..projection import source_directions

from .stages import (
    AirtimeEvent,
    AnalysisQuality,
    AnalysisTime,
    AvailabilityState,
    EventAnalysis,
    EventEvaluationState,
    ForceChannels,
    ForceSeries,
    OrientationSeries,
    ProjectedForces,
    SampleContext,
    SmoothedForces,
    StageAvailability,
    VerticalContext,
)
from .configuration import (
    AnalysisConfiguration,
    AnalysisStage,
    StageConfiguration,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .snapshot import RecordingAnalysis


def validate_snapshot(snapshot: RecordingAnalysis) -> None:
    """Validate availability, source identity, indices and stage dependencies.

    Args:
        snapshot: Recording snapshot whose structure and stage relationships are checked.

    Returns:
        None after successful structural validation, without mutating data.

    Raises:
        TypeError: A field has an incompatible type or mutable collection.
        ValueError: Field values, payloads or source/stage relationships
            contradict the declared model. This check does not certify
            projection math, filtering, event rules or physical accuracy.
        AssertionError: If a required internal invariant does not hold.
    """
    for value, kind in (
        (snapshot.source, ImportSuccess),
        (snapshot.configuration, AnalysisConfiguration),
        (snapshot.time, AnalysisTime),
        (snapshot.forces, ForceSeries),
        (snapshot.orientation, OrientationSeries),
        (snapshot.context, SampleContext),
        (snapshot.events, EventAnalysis),
    ):
        _typed(value, kind)
    _typed(snapshot.forces.projected, ProjectedForces)
    _typed(snapshot.forces.smoothed, SmoothedForces)
    _require(type(snapshot.revision) is int and snapshot.revision >= 0, "Invalid snapshot revision")
    validate_configuration(snapshot.configuration)
    _time(snapshot.time, snapshot.source)
    _require(
        snapshot.ride_bounds[1] < len(snapshot.time.source_indices),
        "Ride markers outside recording",
    )
    _quality(snapshot.quality, snapshot.source)
    count = len(snapshot.time.source_indices)
    _calibration(snapshot.calibration, snapshot.configuration.calibration, snapshot.source)
    projected, smoothed = snapshot.forces.projected, snapshot.forces.smoothed
    orientation, context, events = snapshot.orientation, snapshot.context, snapshot.events
    _require(
        projected.calibration is snapshot.calibration,
        "Projection must reference the snapshot calibration",
    )
    _require(
        (orientation.gravity_index is None or type(orientation.gravity_index) is int)
        and orientation.gravity_index == snapshot.configuration.calibration.gravity_index,
        "Orientation Gravity reference differs from configuration",
    )
    for source, time in (
        (projected.source, projected.time),
        (orientation.source, orientation.time),
    ):
        _source(source, snapshot.source)
        _typed(time, AnalysisTime)
        _require(time == snapshot.time, "Stage time differs from snapshot time")
    _require(smoothed.projection is projected, "Smoothing must reference the shared projection")
    for actual, configuration in (
        (projected.configuration, snapshot.configuration.projection),
        (smoothed.configuration, snapshot.configuration.smoothing),
        (orientation.configuration, snapshot.configuration.orientation),
        (context.configuration, snapshot.configuration.context),
    ):
        _typed(actual, StageConfiguration)
        _require(
            actual == configuration,
            "Stage configuration differs from snapshot",
        )
    projection_available = _stage(
        projected.availability,
        projected.channels,
        projected.quality,
        projected.provenance,
        projected.configuration,
        snapshot.source,
    )
    _typed(projected.unit, UnitAssignment)
    if projection_available:
        _require(
            projected.unit.label is UnitLabel.DIMENSIONLESS,
            "Force unit must be dimensionless",
        )
        _channels(projected.channels, count)
    smoothing_available = _stage(
        smoothed.availability,
        smoothed.channels,
        smoothed.quality,
        smoothed.provenance,
        smoothed.configuration,
        snapshot.source,
    )
    if smoothing_available:
        _require(projection_available, "Smoothing requires an available projection")
        _channels(smoothed.channels, count)
        _samples(smoothed.combined, count)
        assert smoothed.combined is not None
        _require(
            all(
                value >= 0
                for value, valid in zip(
                    smoothed.combined.values,
                    smoothed.combined.valid_rows,
                    strict=True,
                )
                if valid
            ),
            "Combined force magnitude must be nonnegative",
        )
    else:
        _require(smoothed.combined is None, "Unavailable smoothing has no Combined values")
    orientation_available = _stage(
        orientation.availability,
        orientation.values,
        orientation.quality,
        orientation.provenance,
        orientation.configuration,
        snapshot.source,
    )
    _typed(orientation.unit, UnitAssignment)
    if orientation_available:
        _require(
            orientation.unit.label is UnitLabel.DEGREES,
            "Orientation unit must be degrees",
        )
        _samples(orientation.values, count)
        gravity = snapshot.source.recording.motion.gravity
        _require(gravity is not None, "Orientation requires source gravity")
        _require(
            source_directions(snapshot.source.recording)[0] is not None,
            "Orientation requires a vertical direction",
        )
        assert gravity is not None and orientation.values is not None
        for index, vector in enumerate(gravity):
            _require(
                (vector.x, vector.y, vector.z) != (0.0, 0.0, 0.0)
                or not orientation.values.valid_rows[index],
                "Zero gravity cannot produce a valid orientation sample",
            )
    for actual_input, selected in (
        (context.input, snapshot.configuration.context_input),
        (events.input, snapshot.configuration.events_input),
    ):
        expected = projected if selected is AnalysisStage.PROJECTION else smoothed
        _require(
            actual_input is expected,
            "Stage must reference its configured shared force input",
        )
    context_available = _stage(
        context.availability,
        context.labels,
        context.quality,
        context.provenance,
        context.configuration,
        snapshot.source,
    )
    if context_available:
        _require(
            context.input.availability.state is AvailabilityState.AVAILABLE,
            "Context requires available input",
        )
        labels = context.labels
        _typed(labels, tuple)
        assert labels is not None
        _require(len(labels) == count, "Context labels do not match the source axis")
        for index, label in enumerate(labels):
            _typed(label, VerticalContext)
            channels = context.input.channels
            assert channels is not None
            _require(
                channels[0].valid_rows[index] or label is VerticalContext.UNAVAILABLE,
                "Missing vertical samples cannot have an available context",
            )
    _events(events, snapshot.configuration.events, snapshot.source, count)


def _text(value: str) -> None:
    """Require a nonempty textual identifier, preserving the supplied spelling."""
    _typed(value, str)
    _require(bool(value.strip()), "Identifier must contain text")


def validate_configuration(configuration: AnalysisConfiguration) -> None:
    """Validate configuration metadata independently of algorithm admission.

    Args:
        configuration: Configuration whose types and immutable metadata are checked.

    Returns:
        None without changing the supplied configuration.

    Raises:
        TypeError: A field has an incompatible type or mutable collection.
        ValueError: Markers, stage selectors or identifiers are invalid.
    """
    _typed(configuration.calibration, CalibrationOverrides)
    if configuration.ride_bounds is not None:
        bounds = configuration.ride_bounds
        _typed(bounds, tuple)
        _require(
            len(bounds) == 2
            and all(type(value) is int for value in bounds)
            and 0 <= bounds[0] <= bounds[1],
            "Ride markers require ordered nonnegative integer indices",
        )
    _typed(configuration.profile, AnalysisProfile)
    for selector in (configuration.context_input, configuration.events_input):
        _typed(selector, AnalysisStage)
        _require(
            selector in (AnalysisStage.PROJECTION, AnalysisStage.SMOOTHING),
            "Context/events require a force input stage",
        )
    stages: tuple[StageConfiguration, ...] = (
        configuration.projection,
        configuration.smoothing,
        configuration.orientation,
        configuration.context,
    )
    if configuration.events is not None:
        stages += (configuration.events,)
    for stage in stages:
        _typed(stage, StageConfiguration)
        _text(stage.algorithm)
        _text(stage.version)
        _typed(stage.parameters, tuple)
        keys: set[str] = set()
        for item in stage.parameters:
            _typed(item, tuple)
            _require(len(item) == 2, "Parameters require name/value pairs")
            key, value = item
            _text(key)
            _require(key not in keys, "Parameter names must be unique")
            keys.add(key)
            _require(
                type(value) in (type(None), bool, str, int, float),
                "Parameter values must be immutable scalars",
            )
            if isinstance(value, float):
                _require(isfinite(value), "Parameter values must be finite")


def _calibration(
    basis: CalibrationBasis | None,
    overrides: CalibrationOverrides,
    source: ImportSuccess,
) -> None:
    """Check reference identity/support and graph ownership without recalculation."""
    if not overrides.active:
        _require(basis is None, "Inactive overrides require original source axes")
        return
    _typed(basis, CalibrationBasis)
    assert basis is not None
    references = basis.references
    _typed(references, CalibrationReferences)
    _require(references.overrides == overrides, "Calibration references differ from configuration")
    _provenance(
        references.provenance,
        StageConfiguration("user-reference-calibration", references.algorithm_version),
        source,
    )
    _require(
        references.window_samples == REFERENCE_WINDOW_SAMPLES
        and references.algorithm_version == "1"
        and references.capability is CapabilityState.PROVISIONAL,
        "Unsupported calibration reference contract",
    )
    count = len(source.recording.motion.acceleration)
    radius = REFERENCE_WINDOW_SAMPLES // 2
    for index, support in (
        (overrides.gravity_index, references.gravity_interval),
        (overrides.incline_index, references.incline_interval),
    ):
        if index is None:
            _require(support is None, "Retained source axis has no reference interval")
        else:
            _require(index < count, "Calibration index outside recording")
            _require(
                support == (max(0, index - radius), min(count - 1, index + radius)),
                "Calibration reference support differs from its original index",
            )
    for vector in (
        *basis.directions,
        references.vertical_reference,
        references.longitudinal_reference,
        references.polarity_reference,
    ):
        _typed(vector, Vector3)


def _time(time: AnalysisTime, source: ImportSuccess) -> None:
    """Check the full force axis against original acceleration indices and rate."""
    _typed(time.basis, TimeBasis)
    _typed(time.source_indices, tuple)
    for index in time.source_indices:
        _require(type(index) is int, "Source indices must be integers, not booleans")
    count = len(source.recording.motion.acceleration)
    _require(
        time.source_indices == tuple(range(count)),
        "Force axis must retain the complete original sample order",
    )
    _require(type(time.replay_origin) is int, "Replay origin must be an integer")
    _require(
        time.replay_origin == source.recording.indices.start,
        "Replay origin differs from source start marker",
    )
    if time.basis.sample_rate is None:
        _require(
            time.basis.kind is TimeBasisKind.SAMPLE_INDEX,
            "Timed axes require an explicit source sample rate",
        )
    else:
        _require(
            time.basis.sample_rate == source.recording.motion.sample_rate,
            "Time rate/value provenance differs from source",
        )


def _source(source: ImportSuccess, expected: ImportSuccess) -> None:
    """Compare content identity independently of a recording's filesystem path."""
    _typed(source, ImportSuccess)
    _require(
        (source.source_sha256, source.byte_count) == (expected.source_sha256, expected.byte_count),
        "Stage belongs to another source",
    )


def _quality(quality: AnalysisQuality, source: ImportSuccess) -> None:
    """Preserve typed scientific capabilities, diagnostics and source-bound results."""
    _typed(quality, AnalysisQuality)
    _typed(quality.capabilities, tuple)
    identifiers: set[str] = set()
    for item in quality.capabilities:
        _typed(item, tuple)
        _require(len(item) == 2, "Capabilities require identifier/state pairs")
        identifier, state = item
        _text(identifier)
        _typed(state, CapabilityState)
        _require(identifier not in identifiers, "Capability identifiers must be unique")
        identifiers.add(identifier)
    _typed(quality.diagnostics, tuple)
    for diagnostic in quality.diagnostics:
        _typed(diagnostic, AnalysisDiagnostic)
    _typed(quality.existing_results, tuple)
    for result in quality.existing_results:
        _typed(result, AnalysisResult)
        _source(result.source, source)


def _provenance(
    provenance: AnalysisProvenance | None,
    configuration: StageConfiguration,
    source: ImportSuccess,
) -> None:
    """Require calculation provenance to match the source and declared algorithm."""
    _typed(provenance, AnalysisProvenance)
    assert provenance is not None
    _require(
        (provenance.source.sha256, provenance.source.byte_count)
        == (source.source_sha256, source.byte_count),
        "Calculation provenance belongs to another source",
    )
    _require(
        provenance.algorithm == configuration.algorithm,
        "Calculation algorithm differs from stage configuration",
    )


def _stage(
    availability: StageAvailability,
    payload: object,
    quality: AnalysisQuality,
    provenance: AnalysisProvenance | None,
    configuration: StageConfiguration,
    source: ImportSuccess,
) -> bool:
    """Validate stage state/payload/provenance and return whether data is available."""
    _typed(availability, StageAvailability)
    _typed(availability.state, AvailabilityState)
    if availability.reason is not None:
        _typed(availability.reason, AnalysisDiagnostic)
    available = availability.state is AvailabilityState.AVAILABLE
    _require(
        available == (availability.reason is None),
        "Availability and exclusion reason disagree",
    )
    _require(available == (payload is not None), "Availability and payload disagree")
    _quality(quality, source)
    if available:
        _provenance(provenance, configuration, source)
    else:
        _require(provenance is None, "Unavailable stages have no calculation provenance")
    return available


def _samples(samples: SampleValues | None, count: int) -> None:
    """Require an existing immutable scalar buffer matching the source row count."""
    _typed(samples, SampleValues)
    assert samples is not None
    _require(samples.shape == (count,), "Sample buffer shape differs from the scalar source axis")


def _channels(channels: ForceChannels | None, count: int) -> None:
    """Require exactly three immutable scalar channels in the declared axis order."""
    _typed(channels, tuple)
    assert channels is not None
    _require(len(channels) == 3, "Forces require vertical, lateral and longitudinal channels")
    for samples in channels:
        _samples(samples, count)


def _events(
    events: EventAnalysis,
    configuration: StageConfiguration | None,
    source: ImportSuccess,
    count: int,
) -> None:
    """Validate event result representation, not event detection or duration rules."""
    _typed(events.status, EventEvaluationState)
    _require(events.configuration == configuration, "Event configuration differs from snapshot")
    _quality(events.quality, source)
    if events.status is EventEvaluationState.NOT_EVALUATED:
        _typed(events.reason, AnalysisDiagnostic)
        _require(
            events.events is None and events.provenance is None,
            "Unevaluated events cannot carry results or calculation provenance",
        )
        return
    _typed(configuration, StageConfiguration)
    assert configuration is not None
    _require(events.reason is None, "Evaluated events cannot have an exclusion reason")
    _require(
        events.input.availability.state is AvailabilityState.AVAILABLE,
        "Event evaluation requires available input",
    )
    _typed(events.events, tuple)
    assert events.events is not None
    _provenance(events.provenance, configuration, source)
    for event in events.events:
        _typed(event, AirtimeEvent)
        indices = (event.first_sample, event.minimum_sample, event.last_sample)
        for index in indices:
            _require(type(index) is int, "Event indices must be integers")
        _require(
            0 <= event.first_sample <= event.minimum_sample <= event.last_sample < count,
            "Event indices are outside their source interval",
        )
        channels = events.input.channels
        assert channels is not None
        _require(
            channels[0].valid_rows[event.minimum_sample],
            "Event minimum refers to a missing vertical sample",
        )
        for number in (event.duration_seconds, event.minimum_vertical_g):
            _require(
                type(number) in (int, float) and isfinite(number),
                "Event values must be finite numbers",
            )
        _require(event.duration_seconds >= 0, "Event duration must not be negative")
        if event.onset_g_per_second is not None:
            _require(
                type(event.onset_g_per_second) in (int, float)
                and isfinite(event.onset_g_per_second),
                "Event onset must be finite",
            )
        _typed(event.category, VerticalContext)
        _require(
            event.category
            in (
                VerticalContext.FLOATER_AIRTIME,
                VerticalContext.AIRTIME,
                VerticalContext.STRONG_AIRTIME,
                VerticalContext.EJECTOR_AIRTIME,
            ),
            "Airtime events require an airtime category",
        )
        _require(
            type(event.start_incomplete) is bool and type(event.end_incomplete) is bool,
            "Event completeness requires booleans",
        )
