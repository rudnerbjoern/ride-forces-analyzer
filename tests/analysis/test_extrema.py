"""Analytic selected-range extrema and complete original-recording contracts."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
import json

import pytest

from ride_forces_analyzer.analysis.models import SampleValues
from ride_forces_analyzer.analysis.recording import AvailabilityState, StageAvailability
from ride_forces_analyzer.explorer import present_recording
from ride_forces_analyzer.analysis.extrema import calculate_extrema
from ride_forces_analyzer.importers import ImportSuccess, import_forces, import_forces_bytes
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def sample_source() -> ImportSuccess:
    source = import_forces_bytes(
        json.dumps(
            {
                "schemaVersion": "2.2.0",
                "sampleRate": 25,
                "accelerationSequence": [
                    {"x": x, "y": y, "z": z}
                    for x, y, z in ((99, 99, 99), (-2, 0, 3), (4, 0, -5), (-2, 0, -5), (99, 99, 99))
                ],
                "verticalDirectionVector": {"x": 0, "y": 1, "z": 0},
                "lateralDirectionVector": {"x": 0, "y": 0, "z": 1},
                "longitudinalDirectionVector": {"x": 1, "y": 0, "z": 0},
            },
        ).encode(),
    )
    assert isinstance(source, ImportSuccess)
    return source


def test_inclusive_extrema_ties_time_and_immutable_provenance() -> None:
    source = sample_source()
    result = calculate_extrema(source, 1, 3, calculation_time=NOW)
    assert (result.first, result.last, result.count) == (1, 3, 3)
    assert (result.sample_rate, result.mode, result.unit, result.smoothing_window) == (
        25,
        "raw",
        "unknown",
        1,
    )
    assert result.source_sha256 == source.source_sha256
    assert result.calculation_time == NOW and result.time_basis == "INFERRED_UNIFORM"
    assert result.source_algorithm == "source-acceleration-v1"
    x, y, z = result.channels
    assert (x.minimum.value, x.minimum.index, x.minimum.recording_seconds) == (-2, 1, 0.04)
    assert (x.maximum.value, x.maximum.index) == (4, 2)
    assert y.minimum.value == y.maximum.value == 0
    assert y.minimum.index == y.maximum.index == 1
    assert (z.minimum.value, z.minimum.index, z.maximum.value) == (-5, 2, 3)
    with pytest.raises(FrozenInstanceError):
        setattr(result, "first", 0)
    with pytest.raises(FrozenInstanceError):
        setattr(x.minimum, "value", 7)
    one = calculate_extrema(source, 2, 2)
    assert one.count == 1
    assert all(axis.minimum == axis.maximum for axis in one.channels)


@pytest.mark.parametrize("first,last", [(-1, 1), (0, 5), (3, 2), (True, 2), (0, False)])
def test_invalid_selection_is_rejected(first: int, last: int) -> None:
    with pytest.raises(ValueError, match="sample indices"):
        calculate_extrema(sample_source(), first, last)


def test_stage_binding_shape_missingness_and_timestamp_guards() -> None:
    import numpy as np

    source = sample_source()
    view = present_recording(source)
    assert view.analysis is not None
    stage = view.analysis.forces.smoothed
    assert stage.channels is not None
    for bad in (
        replace(stage, projection=replace(stage.projection, source=sample_source())),
        replace(
            stage,
            projection=replace(
                stage.projection,
                time=replace(stage.projection.time, source_indices=(0,)),
            ),
        ),
        replace(stage, availability=StageAvailability(AvailabilityState.UNAVAILABLE)),
        replace(stage, channels=None),
        replace(stage, provenance=None),
        replace(stage, channels=(SampleValues(np.zeros(1)),) * 3),
        replace(stage, channels=(SampleValues(np.full(5, np.nan), valid_rows=(False,) * 5),) * 3),
    ):
        with pytest.raises(ValueError):
            calculate_extrema(source, 0, 4, forces=bad)
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_extrema(source, 0, 1, calculation_time=datetime(2026, 10, 17))
    result = calculate_extrema(source, 0, 4, forces=stage, calculation_time=NOW)
    assert result.quality is stage.quality and result.provenance is stage.provenance
    assert result.capability == "PROVISIONAL"
    assert result.source_algorithm == "source-direction-unit-projection-centered-mean-11-v1"


def test_rich_extrema_keep_values_times_and_source_details() -> None:
    view = present_recording(sample_source()).with_calibration(True)
    context, rows = view.extrema_text(1, 1, rich=True)
    assert context == view.extrema_text(1, 1)[0]
    result = view.selection_extrema(1, 1)
    for row, channel in zip(rows, result.channels, strict=True):
        assert row.startswith('<table width="100%"')
        assert f">{channel.name}</th>" in row
        assert ">Replay</td>" in row
        for point in (channel.minimum, channel.maximum):
            assert f"{point.value:+.2f} g" in row
            assert view.replay_text(point.index) in row
            assert f"Sample {point.index}" in row
            assert f"Recording {point.recording_seconds:.3f} s" in row
    raw_rows = view.with_calibration(False).extrema_text(1, 1, rich=True)[1]
    assert all(" g" not in row for row in raw_rows)


def test_selection_does_not_filter_again_at_edges() -> None:
    source = sample_source()
    view = present_recording(source).with_calibration(True)
    assert view.analysis is not None and view.analysis.forces.smoothed.channels is not None
    result = view.selection_extrema(1, 1)
    assert tuple(axis.minimum.value for axis in result.channels) == tuple(
        axis.values[1] for axis in view.analysis.forces.smoothed.channels
    )
    assert result.smoothing_window == 11
    context, rows = view.extrema_text(1, 1)
    assert "Calibrated" in context and "11 samples" in context
    assert all(" g" in row and "Sample 1" in row and "Recording 0.040 s" in row for row in rows)
    unfiltered = view.with_smoothing(1).selection_extrema(1, 1)
    assert unfiltered.channels != result.channels
    raw = view.with_calibration(False)
    assert raw.selection_extrema(1, 1).unit == "unknown"
    assert "Unit unknown" in raw.extrema_text(1, 1)[0]


@pytest.mark.parametrize("filename", REAL_FIXTURES)
def test_originals_all_modes_windows_and_selections(filename: str) -> None:
    path = REAL_FIXTURE_DIRECTORY / filename
    before, mtime = path.read_bytes(), path.stat().st_mtime_ns
    source = import_forces(path)
    assert isinstance(source, ImportSuccess)
    view = present_recording(source)
    for window in (1, 11, 51):
        smoothed = view.with_smoothing(window)
        for active in (False, True):
            current = smoothed.with_calibration(active)
            for first, last in (
                (0, current.count - 1),
                (current.count // 2, current.count // 2 + 7),
            ):
                result = current.selection_extrema(first, last)
                for axis, values in zip(result.channels, current.plotted_channels, strict=True):
                    selected = tuple(values[first : last + 1])
                    assert axis.minimum.value == min(selected)
                    assert axis.maximum.value == max(selected)
                    assert axis.minimum.index == first + selected.index(min(selected))
                    assert axis.maximum.index == first + selected.index(max(selected))
                    assert (
                        axis.maximum.recording_seconds == axis.maximum.index / current.sample_rate
                    )
                assert result.unit == ("g" if active else "unknown")
                assert result.smoothing_window == (window if active else 1)
                assert result.source_sha256 == source.source_sha256
    assert path.read_bytes() == before and path.stat().st_mtime_ns == mtime
    assert source.recording.source.original_bytes == before
