"""Preparation contracts, independent stages and raw-capable sample access."""

from dataclasses import replace
from datetime import UTC, datetime
import json
from math import sqrt
from unittest.mock import Mock

import numpy as np
import pytest

from ride_forces_analyzer.analysis import airtime, recording
from ride_forces_analyzer.analysis.models import (
    AnalysisProfile,
    CapabilityState,
    ProfileName,
    SampleValues,
    TimeBasis,
)
from ride_forces_analyzer.analysis.orientation import orientation_degrees
from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    AnalysisStage,
    AvailabilityState,
    EventEvaluationState,
    RecordingAnalysis,
    StageConfiguration,
    VerticalContext,
    prepare_recording_analysis,
)
from ride_forces_analyzer.analysis.projection import project_directions
from ride_forces_analyzer.analysis.smoothing import centered_mean
from ride_forces_analyzer.importers import ImportSuccess, import_forces_bytes


def test_combined_uses_device_axes_and_is_prepared_with_the_smoothing_snapshot(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = synthetic_source(
        accelerationSequence=[
            {"x": 3, "y": 4, "z": 0},
            {"x": -3, "y": -4, "z": 0},
            {"x": 0, "y": 0, "z": 12},
        ],
        gravitySequence=[{"x": 0, "y": 0, "z": 1}] * 3,
        endIndex=2,
        verticalDirectionVector={"x": 0.001, "y": 0, "z": 1},
    )
    configuration = replace(
        configuration,
        smoothing=replace(configuration.smoothing, parameters=(("window_samples", 3),)),
    )
    snapshot = prepare_snapshot(configuration, source)
    assert snapshot.forces.smoothed.combined is not None
    assert tuple(snapshot.forces.smoothed.combined.values) == (0, 4, 6.5)
    assert snapshot.sample(2).combined_g == 6.5
    forces = snapshot.sample(2).smoothed
    assert forces is not None
    assert snapshot.sample(2).combined_g != sqrt(
        forces.vertical**2 + forces.lateral**2 + forces.longitudinal**2,
    )
    changed = snapshot.with_smoothing(1, revision=4, calculation_time=NOW)
    assert changed.forces.projected is snapshot.forces.projected
    assert changed.forces.smoothed.combined is not snapshot.forces.smoothed.combined
    assert changed.sample(2).combined_g == 12
    assert snapshot.sample(2).combined_g == 6.5
    with pytest.raises(ValueError):
        snapshot.forces.smoothed.combined.values.setflags(write=True)
    monkeypatch.setattr(
        recording,
        "combined_force",
        Mock(side_effect=AssertionError("Repeated Combined")),
    )
    assert snapshot.sample(2).combined_g == 6.5


def test_combined_failure_preserves_directional_results_and_marks_missing_samples(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = synthetic_source()
    expected = prepare_snapshot(configuration, source)
    monkeypatch.setattr(recording, "combined_force", Mock(side_effect=ValueError("Invalid norm")))
    snapshot = prepare_snapshot(configuration, source)
    smoothed = snapshot.forces.smoothed
    assert smoothed.availability.state is AvailabilityState.AVAILABLE
    assert smoothed.combined is not None
    count = len(source.recording.motion.acceleration)
    assert smoothed.combined.valid_rows == (False,) * count
    assert {
        diagnostic.source_index
        for diagnostic in smoothed.quality.diagnostics
        if diagnostic.code == "COMBINED_SAMPLE_UNAVAILABLE"
    } == set(range(count))
    for index in range(count):
        sample = snapshot.sample(index)
        previous = expected.sample(index)
        assert sample.combined_g is None
        assert sample.smoothed is not None and sample.smoothed == previous.smoothed
        assert sample.raw == previous.raw
        assert sample.orientation_degrees == previous.orientation_degrees
        assert sample.context == previous.context


NOW = datetime(2026, 10, 20, tzinfo=UTC)


def synthetic_source(**overrides: object) -> ImportSuccess:
    payload: dict[str, object] = {
        "schemaVersion": "2.2.0",
        "device": "iPhone",
        "sampleRate": 25,
        "startIndex": 2,
        "accelerationSequence": [
            {"x": "0.2", "y": "-0.3", "z": str(value)}
            for value in (1.0, 0.8, 0.0, -0.9, -0.8, 0.0, 1.0)
        ],
        "gravitySequence": [{"x": "0", "y": "0", "z": "1"}] * 7,
        "verticalDirectionVector": {"x": "0", "y": "0", "z": "1"},
        "lateralDirectionVector": {"x": "1", "y": "0", "z": "0"},
        "longitudinalDirectionVector": {"x": "0", "y": "1", "z": "0"},
        "unknownAnalysisField": {"retain": True},
    }
    payload.update(overrides)
    source = import_forces_bytes(
        json.dumps({key: value for key, value in payload.items() if value is not None}).encode(),
    )
    assert isinstance(source, ImportSuccess)
    return source


@pytest.fixture
def configuration() -> AnalysisConfiguration:
    return AnalysisConfiguration(
        AnalysisProfile(
            ProfileName.RIDER_CALIBRATED,
            policy_references=("Synthetic source-app policy",),
            assumptions=("Synthetic loading-ratio scale",),
            allow_provisional=True,
        ),
        StageConfiguration("source-direction-unit-projection", "1"),
        StageConfiguration("centered-mean", "1"),
        StageConfiguration("source-gravity-tilt", "1"),
        StageConfiguration("vertical-context", "1"),
    )


def prepare_snapshot(
    configuration: AnalysisConfiguration,
    source: ImportSuccess | None = None,
) -> RecordingAnalysis:
    return prepare_recording_analysis(
        synthetic_source() if source is None else source,
        configuration,
        revision=3,
        calculation_time=NOW,
    )


@pytest.mark.parametrize("window", (1, 5, 11, 51))
def test_prepared_stages_match_existing_functions_and_keep_source(
    configuration: AnalysisConfiguration,
    window: int,
) -> None:
    source = synthetic_source()
    configuration = replace(
        configuration,
        smoothing=replace(
            configuration.smoothing,
            parameters=(("window_samples", window),),
        ),
    )
    snapshot = prepare_snapshot(configuration, source)
    snapshot.validate()
    assert snapshot.source is source
    assert snapshot.source.recording.source.original_bytes is source.recording.source.original_bytes
    assert snapshot.time.basis.sample_rate is source.recording.motion.sample_rate
    assert snapshot.revision == 3
    directions = source.recording.vectors
    assert directions.vertical_direction is not None
    assert directions.lateral_direction is not None
    assert directions.longitudinal_direction is not None
    raw = project_directions(
        source.recording.motion.acceleration,
        (
            directions.vertical_direction,
            directions.lateral_direction,
            directions.longitudinal_direction,
        ),
    )
    assert snapshot.forces.projected.channels is not None
    assert snapshot.forces.smoothed.channels is not None
    for expected, projected, smoothed in zip(
        raw,
        snapshot.forces.projected.channels,
        snapshot.forces.smoothed.channels,
        strict=True,
    ):
        assert tuple(projected.values) == expected
        assert tuple(smoothed.values) == centered_mean(expected, window)
        with pytest.raises(ValueError):
            smoothed.values.setflags(write=True)
    assert snapshot.orientation.values is not None
    assert tuple(snapshot.orientation.values.values) == orientation_degrees(source.recording)
    assert snapshot.forces.smoothed.projection is snapshot.forces.projected
    assert snapshot.context.input is snapshot.forces.smoothed
    assert snapshot.events.input is snapshot.forces.smoothed
    assert snapshot.events.status is EventEvaluationState.NOT_EVALUATED
    assert snapshot.events.events is None and snapshot.events.reason is not None
    for stage in (
        snapshot.forces.projected,
        snapshot.forces.smoothed,
        snapshot.orientation,
        snapshot.context,
    ):
        assert stage.provenance is not None
        assert stage.provenance.source is source.recording.source.provenance
        assert stage.provenance.calculation_time == NOW
        assert stage.provenance.algorithm == stage.configuration.algorithm
        assert np.__version__ in stage.provenance.engine_version
    assert all(state is CapabilityState.PROVISIONAL for _, state in snapshot.quality.capabilities)


def test_default_window_and_context_input_are_explicit(
    configuration: AnalysisConfiguration,
) -> None:
    snapshot = prepare_snapshot(configuration)
    reference = prepare_snapshot(
        replace(
            configuration,
            smoothing=replace(
                configuration.smoothing,
                parameters=(("window_samples", 11),),
            ),
        ),
    )
    assert snapshot.forces.smoothed.channels == reference.forces.smoothed.channels
    projected = prepare_snapshot(
        replace(
            configuration,
            context_input=AnalysisStage.PROJECTION,
            events_input=AnalysisStage.PROJECTION,
            events=StageConfiguration("airtime-events", "1"),
        ),
    )
    assert projected.context.input is projected.forces.projected
    assert projected.events.input is projected.forces.projected
    assert projected.events.configuration is projected.configuration.events
    assert projected.events.status is EventEvaluationState.EVALUATED
    channels = projected.forces.projected.channels
    assert channels is not None and projected.context.labels is not None
    expected = airtime.AirtimeContext.prepare(tuple(channels[0].values), 25).labels
    assert tuple(label.value for label in projected.context.labels) == tuple(
        label.lower().replace(" ", "_") for label in expected
    )


def test_sample_access_does_not_repeat_preparation(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = prepare_snapshot(configuration)

    def unexpected(*args: object, **kwargs: object) -> None:
        pytest.fail("Sample access must read prepared values without recalculating")

    for name in ("project_directions", "centered_mean", "orientation_degrees"):
        monkeypatch.setattr(recording, name, unexpected)
    monkeypatch.setattr(airtime.AirtimeContext, "prepare", unexpected)
    for index in (0, 6, 2, 6):
        assert snapshot.sample(index).raw is snapshot.source.recording.motion.acceleration[index]


@pytest.mark.parametrize("defect", ("missing_direction", "invalid_basis", "zero_vertical"))
def test_orientation_is_independent_of_projection(
    configuration: AnalysisConfiguration,
    defect: str,
) -> None:
    if defect == "missing_direction":
        source = synthetic_source(lateralDirectionVector=None)
    elif defect == "invalid_basis":
        source = synthetic_source(lateralDirectionVector={"x": "0", "y": "1", "z": "0"})
    else:
        source = synthetic_source(verticalDirectionVector={"x": "0", "y": "0", "z": "0"})
    snapshot = prepare_snapshot(configuration, source)
    sample = snapshot.sample(0)
    assert sample.projected is sample.smoothed is sample.context is None
    assert sample.raw is source.recording.motion.acceleration[0]
    assert sample.projection_availability.reason is not None
    assert sample.smoothing_availability.reason is not None
    assert sample.context_availability.reason is not None
    assert (sample.orientation_degrees is None) == (defect == "zero_vertical")
    snapshot.validate()


@pytest.mark.parametrize("missing", ("gravitySequence", "verticalDirectionVector"))
def test_missing_orientation_prerequisites_are_explained(
    configuration: AnalysisConfiguration,
    missing: str,
) -> None:
    snapshot = prepare_snapshot(configuration, synthetic_source(**{missing: None}))
    assert snapshot.orientation.values is None
    sample = snapshot.sample(0)
    assert sample.orientation_degrees is None
    assert sample.orientation_availability.reason is not None
    if missing == "gravitySequence":
        assert sample.projected is not None and sample.smoothed is not None


def test_zero_gravity_is_a_missing_row_with_indexed_diagnostics(
    configuration: AnalysisConfiguration,
) -> None:
    gravity = [{"x": "0", "y": "0", "z": str(value)} for value in (1, 0, 1, 1, 1, 1, 1)]
    snapshot = prepare_snapshot(configuration, synthetic_source(gravitySequence=gravity))
    assert snapshot.orientation.availability.state is AvailabilityState.AVAILABLE
    assert snapshot.orientation.values is not None
    assert snapshot.orientation.values.valid_rows == (True, False, True, True, True, True, True)
    assert np.isnan(snapshot.orientation.values.values[1])
    assert snapshot.sample(1).orientation_degrees is None
    assert snapshot.sample(0).orientation_degrees == 0
    assert any(item.source_index == 1 for item in snapshot.sample(1).quality.diagnostics)
    assert not any(item.source_index == 1 for item in snapshot.sample(0).quality.diagnostics)


def test_raw_profile_retains_samples_without_fabricated_derived_values(
    configuration: AnalysisConfiguration,
) -> None:
    snapshot = prepare_snapshot(replace(configuration, profile=AnalysisProfile()))
    sample = snapshot.sample(1)
    assert sample.raw is snapshot.source.recording.motion.acceleration[1]
    assert (
        sample.projected is sample.smoothed is sample.context is sample.orientation_degrees is None
    )
    assert sample.recording_seconds == 1 / 25
    assert sample.replay_seconds == -1 / 25
    assert all(state is CapabilityState.UNAVAILABLE for _, state in sample.quality.capabilities)


@pytest.mark.parametrize("stage", ("projection", "smoothing", "orientation", "context"))
@pytest.mark.parametrize("field,value", (("algorithm", "unknown"), ("version", "2")))
def test_unsupported_algorithms_never_produce_mislabeled_data(
    configuration: AnalysisConfiguration,
    stage: str,
    field: str,
    value: str,
) -> None:
    changed = replace(getattr(configuration, stage), **{field: value})
    with pytest.raises(ValueError, match="algorithm/version"):
        prepare_snapshot(replace(configuration, **{stage: changed}))


@pytest.mark.parametrize(
    "stage,parameters",
    (
        ("projection", (("unknown", 1),)),
        ("orientation", (("unknown", 1),)),
        ("smoothing", (("unknown", 1),)),
        ("context", (("unknown", 1),)),
        ("context", (("floater_bound_g", airtime.FLOATER_BOUND_G * 2),)),
        ("context", (("floater_bound_g", True),)),
    ),
)
def test_unsupported_parameters_are_rejected(
    configuration: AnalysisConfiguration,
    stage: str,
    parameters: tuple[tuple[str, float], ...],
) -> None:
    with pytest.raises(ValueError, match="parameters"):
        prepare_snapshot(
            replace(
                configuration,
                **{stage: replace(getattr(configuration, stage), parameters=parameters)},
            ),
        )


@pytest.mark.parametrize("window", (0, 2, 53, True, 3.0, None))
def test_invalid_windows_are_rejected(
    configuration: AnalysisConfiguration,
    window: int | float | None,
) -> None:
    with pytest.raises(ValueError, match="odd integer"):
        prepare_snapshot(
            replace(
                configuration,
                smoothing=replace(
                    configuration.smoothing,
                    parameters=(("window_samples", window),),
                ),
            ),
        )


def test_profile_opt_in_and_supported_policy_are_required(
    configuration: AnalysisConfiguration,
) -> None:
    for profile in (
        replace(configuration.profile, allow_provisional=False),
        AnalysisProfile(ProfileName.DEVICE_VECTORS, policy_references=("Other policy",)),
    ):
        with pytest.raises(ValueError, match="permission|profile"):
            prepare_snapshot(replace(configuration, profile=profile))


@pytest.mark.parametrize("revision,time", ((-1, NOW), (True, NOW), (1, NOW.replace(tzinfo=None))))
def test_invalid_request_metadata_is_rejected(
    configuration: AnalysisConfiguration,
    revision: int,
    time: datetime,
) -> None:
    with pytest.raises(ValueError):
        prepare_recording_analysis(
            synthetic_source(),
            configuration,
            revision=revision,
            calculation_time=time,
        )


@pytest.mark.parametrize(
    "index,error",
    ((True, TypeError), (1.0, TypeError), (-1, IndexError), (7, IndexError)),
)
def test_sample_index_validation(
    configuration: AnalysisConfiguration,
    index: int,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        prepare_snapshot(configuration).sample(index)


def test_sample_does_not_invent_seconds_without_rate(configuration: AnalysisConfiguration) -> None:
    snapshot = prepare_snapshot(configuration)
    snapshot = replace(snapshot, time=replace(snapshot.time, basis=TimeBasis()))
    snapshot = replace(
        snapshot,
        forces=replace(
            snapshot.forces,
            projected=replace(snapshot.forces.projected, time=snapshot.time),
        ),
    )
    with pytest.raises(ValueError, match="sample rate"):
        snapshot.sample(0)


def test_missing_force_row_stays_missing_in_sample_view(
    configuration: AnalysisConfiguration,
) -> None:
    snapshot = prepare_snapshot(configuration)
    channels = snapshot.forces.smoothed.channels
    assert channels is not None
    missing = SampleValues(np.full(7, np.nan), valid_rows=(False,) * 7)
    smoothed = replace(snapshot.forces.smoothed, channels=(missing, channels[1], channels[2]))
    snapshot = replace(
        snapshot,
        forces=replace(snapshot.forces, smoothed=smoothed),
        context=replace(
            snapshot.context,
            input=smoothed,
            labels=(VerticalContext.UNAVAILABLE,) * 7,
        ),
        events=replace(snapshot.events, input=smoothed),
    )
    snapshot.validate()
    assert snapshot.sample(0).projected is not None
    assert snapshot.sample(0).smoothed is None
    assert snapshot.sample(0).context is VerticalContext.UNAVAILABLE


@pytest.mark.parametrize("failure", ("projection", "smoothing"))
def test_numerical_range_failures_preserve_raw_and_independent_orientation(
    configuration: AnalysisConfiguration,
    failure: str,
) -> None:
    overrides: dict[str, object] = {
        "accelerationSequence": [{"x": "1.7e308", "y": "1.7e308", "z": "1.7e308"}] * 7,
    }
    if failure == "projection":
        overrides.update(
            verticalDirectionVector={"x": "0.707", "y": "0.707", "z": "0"},
            lateralDirectionVector={"x": "-0.707", "y": "0.707", "z": "0"},
            longitudinalDirectionVector={"x": "0", "y": "0", "z": "1"},
        )
    with np.errstate(over="ignore", invalid="ignore"):
        snapshot = prepare_snapshot(configuration, synthetic_source(**overrides))
    assert snapshot.sample(0).raw.x == 1.7e308
    assert snapshot.sample(0).orientation_degrees is not None
    assert snapshot.sample(0).smoothed is None
    assert snapshot.sample(0).context is None
    assert snapshot.sample(0).projection_availability.state is (
        AvailabilityState.UNAVAILABLE if failure == "projection" else AvailabilityState.AVAILABLE
    )
