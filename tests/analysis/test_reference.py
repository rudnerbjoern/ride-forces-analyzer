"""Analytic and original-file evidence for the source-bound Manta reconstruction."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from ride_forces_analyzer.analysis.reference import (
    MANTA_SHA256,
    centered_mean_11,
    project_directions,
    reconstruct_app_reference,
)
from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.importers import ImportSuccess, import_forces, import_forces_bytes
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def test_projection_and_explicit_rounded_direction_normalization() -> None:
    directions = (Vector3(0, 0.999, 0), Vector3(0, 0, 1), Vector3(1, 0, 0))
    values = project_directions((Vector3(2, -3, 4),), directions)
    assert values == ((-3.0,), (4.0,), (2.0,))
    with pytest.raises(ValueError):
        project_directions((Vector3(1, 2, 3),), (directions[0], directions[0], directions[2]))
    with pytest.raises(ValueError):
        project_directions((Vector3(1, 2, 3),), (Vector3(0, -1, 0), directions[1], directions[2]))


def test_centered_mean_constant_impulse_and_explicit_edge_policy() -> None:
    assert centered_mean_11((2.0,) * 21) == (2.0,) * 21
    impulse = (0.0,) * 10 + (11.0,) + (0.0,) * 10
    assert centered_mean_11(impulse) == (0.0,) * 5 + (1.0,) * 11 + (0.0,) * 5
    ramp = centered_mean_11(tuple(float(i) for i in range(21)))
    assert ramp[0] == 2.5 and ramp[10] == 10 and ramp[-1] == 17.5
    assert centered_mean_11((1.0, 3.0)) == (2.0, 2.0)
    assert centered_mean_11((7.0,)) == (7.0,)
    with pytest.raises(ValueError):
        centered_mean_11(())


@pytest.mark.parametrize("filename", REAL_FIXTURES)
def test_same_projection_cross_checks_all_source_extrema(filename: str) -> None:
    source = import_forces(REAL_FIXTURE_DIRECTORY / filename)
    assert isinstance(source, ImportSuccess)
    recording = source.recording
    v = recording.vectors
    assert v.vertical_direction and v.lateral_direction and v.longitudinal_direction
    raw = project_directions(
        recording.motion.acceleration,
        (v.vertical_direction, v.lateral_direction, v.longitudinal_direction),
    )
    filtered = centered_mean_11(raw[0])
    selected = filtered[recording.indices.start : recording.indices.end + 1]
    assert recording.min_force and recording.max_force
    # Regression ceiling from the observed corpus, not a certified physical tolerance.
    assert abs(min(selected) - float(recording.min_force.value)) < 0.0002
    assert abs(max(selected) - float(recording.max_force.value)) < 0.0002
    reference = reconstruct_app_reference(source, calculation_time=NOW)
    assert reference is not None
    assert reference.source_sha256 == source.source_sha256
    if source.source_sha256 == MANTA_SHA256:
        assert reference.capability == "VERIFIED" and reference.calculation_time == NOW
        assert reference.source_sha256 == source.source_sha256
        assert min(reference.channels[0]) == pytest.approx(-3.7208311929212843, abs=1e-12)
        assert max(reference.channels[0]) == pytest.approx(2.614460771187888, abs=1e-12)
        assert reference.channels[0][2013] == pytest.approx(0.9989, abs=0.0001)
        assert reference.channels[2][3370] == pytest.approx(0.6736, abs=0.0001)
        assert not np.allclose(raw[0], reference.channels[0])


def test_reference_accepts_modified_source_bytes_without_allowlist() -> None:
    raw = next(Path(REAL_FIXTURE_DIRECTORY).glob("Manta-*.forces")).read_bytes()
    modified = import_forces_bytes(raw + b" ")
    assert isinstance(modified, ImportSuccess)
    reference = reconstruct_app_reference(modified, calculation_time=NOW)
    assert reference is not None and reference.source_sha256 == modified.source_sha256


def test_missing_optional_numpy_keeps_reference_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.analysis import reference

    source = import_forces(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    assert isinstance(source, ImportSuccess)

    def unavailable(name: str) -> None:
        return None

    monkeypatch.setattr(reference, "find_spec", unavailable)
    assert reconstruct_app_reference(source, calculation_time=NOW) is None


@pytest.mark.parametrize(
    "seconds,forces,combined,orientation",
    [
        (0, ("-0.04", "-0.01", "0.99"), "0.99", 92),
        (10, ("1.00", "0.01", "-0.01"), "1.00", 0),
        (67, ("0.52", "-0.02", "-0.08"), "0.52", 47),
        (72, ("-3.44", "0.07", "0.35"), "3.46", 120),
        (86, ("1.96", "-0.21", "0.41"), "2.02", 77),
    ],
)
def test_independent_owner_replay_snapshots(
    seconds: int,
    forces: tuple[str, str, str],
    combined: str,
    orientation: int,
) -> None:
    from math import acos, degrees, sqrt

    source = import_forces(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    assert isinstance(source, ImportSuccess)
    reference = reconstruct_app_reference(source, calculation_time=NOW)
    assert reference is not None
    recording = source.recording
    index = recording.indices.start + round(seconds * recording.motion.sample_rate.value)
    values = tuple(channel[index] for channel in reference.channels)
    # Screenshots supply two decimal places, not full-precision measurements.
    assert tuple(f"{value:.2f}" for value in values) == forces
    assert f"{sqrt(sum(value * value for value in values)):.2f}" == combined
    # This tests a confirmed Manta orientation contract, not a production orientation API.
    assert recording.motion.gravity is not None and recording.vectors.vertical_direction is not None
    gravity = recording.motion.gravity[index]
    vertical = recording.vectors.vertical_direction
    dot = gravity.x * vertical.x + gravity.y * vertical.y + gravity.z * vertical.z
    length = sqrt(gravity.x**2 + gravity.y**2 + gravity.z**2) * sqrt(
        vertical.x**2 + vertical.y**2 + vertical.z**2,
    )
    assert round(degrees(acos(max(-1.0, min(1.0, dot / length))))) == orientation


@pytest.mark.parametrize(
    "seconds,frame,forces,combined,orientation",
    [
        (0, 0, (0.98, -0.01, -0.10), 0.99, 6),
        (54, 25, (0.93, 0.00, 0.35), 0.99, 20),
        (76, 28, (2.21, -0.08, -0.36), 2.24, 72),
        (91, 47, (4.02, 0.09, -0.15), 4.02, 29),
        (108, 13, (3.59, 0.04, -0.02), 3.59, 34),
        (112, 4, (3.43, 0.05, -0.05), 3.43, 0),
        (122, 3, (1.24, 0.34, -0.96), 1.61, 136),
        (128, 16, (1.00, -0.08, -0.90), 1.35, 2),
    ],
)
def test_kraken_replay_sample_counter_and_documented_start_discrepancy(
    seconds: int,
    frame: int,
    forces: tuple[float, float, float],
    combined: float,
    orientation: int,
) -> None:
    from math import acos, degrees, sqrt

    source = import_forces(next(REAL_FIXTURE_DIRECTORY.glob("Kraken-*.forces")))
    assert isinstance(source, ImportSuccess)
    recording = source.recording
    vectors = recording.vectors
    vertical, lateral, longitudinal = (
        vectors.vertical_direction,
        vectors.lateral_direction,
        vectors.longitudinal_direction,
    )
    assert vertical is not None and lateral is not None and longitudinal is not None
    channels = tuple(
        centered_mean_11(channel)
        for channel in project_directions(
            recording.motion.acceleration,
            (vertical, lateral, longitudinal),
        )
    )
    # Replay suffix is a sample counter at 50 Hz, not hundredths of a second.
    index = recording.indices.start + seconds * 50 + frame
    values = tuple(channel[index] for channel in channels)
    actual = tuple(round(value, 2) for value in values)
    magnitude = round(sqrt(sum(value * value for value in values)), 2)
    if seconds == 0 and frame == 0:
        # Preserve the observed mismatch; do not fit an unverified edge rule.
        assert forces == (0.98, -0.01, -0.10) and combined == 0.99
        assert actual == (1.00, 0.00, -0.10) and magnitude == 1.00
    else:
        assert actual == forces and magnitude == combined
    assert recording.motion.gravity is not None
    gravity = recording.motion.gravity[index]
    dot = gravity.x * vertical.x + gravity.y * vertical.y + gravity.z * vertical.z
    length = sqrt(gravity.x**2 + gravity.y**2 + gravity.z**2) * sqrt(
        vertical.x**2 + vertical.y**2 + vertical.z**2,
    )
    assert round(degrees(acos(max(-1.0, min(1.0, dot / length))))) == orientation


def test_voltron_screenshot_extrema_and_display_rounding_difference() -> None:
    source = import_forces(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    assert isinstance(source, ImportSuccess)
    recording = source.recording
    vectors = recording.vectors
    vertical, lateral, longitudinal = (
        vectors.vertical_direction,
        vectors.lateral_direction,
        vectors.longitudinal_direction,
    )
    assert vertical is not None and lateral is not None and longitudinal is not None
    raw = project_directions(recording.motion.acceleration, (vertical, lateral, longitudinal))
    selected = tuple(
        centered_mean_11(channel)[recording.indices.start : recording.indices.end + 1]
        for channel in raw
    )
    assert round(min(selected[0]), 2) == -1.60
    assert round(min(selected[1]), 2) == -1.26
    assert round(max(selected[1]), 2) == 0.92
    assert round(min(selected[2]), 2) == -1.21
    assert round(max(selected[2]), 2) == 1.07
    combined = tuple(
        sum(value**2 for value in sample) ** 0.5 for sample in zip(*selected, strict=True)
    )
    assert round(min(combined), 2) == 0.09
    assert round(max(combined), 2) == 4.44
    # Source screenshot says 4.36; retain the discrepancy instead of changing rounding.
    assert max(selected[0]) == pytest.approx(4.365497903276147, abs=1e-12)
    assert round(max(selected[0]), 2) == 4.37


@pytest.mark.parametrize("window", range(1, 52, 2))
def test_configurable_mean_matches_direct_available_neighbor_average(window: int) -> None:
    from ride_forces_analyzer.analysis.reference import centered_mean

    values = (0.0, 1.0, 4.0, 9.0, 16.0, 0.0, -3.0)
    half = window // 2
    expected = tuple(
        sum(neighbors) / len(neighbors)
        for i in range(len(values))
        for neighbors in (values[max(0, i - half) : i + half + 1],)
    )
    assert centered_mean(values, window) == expected


@pytest.mark.parametrize("window", [0, -1, 2, 52, True])
def test_configurable_mean_rejects_invalid_windows(window: int) -> None:
    from ride_forces_analyzer.analysis.reference import centered_mean

    with pytest.raises(ValueError, match="odd integer"):
        centered_mean((1.0,), window)
