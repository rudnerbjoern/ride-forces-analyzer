"""Source-app evidence for unified snapshots, retaining documented scientific limits."""

from datetime import UTC, datetime
import csv

import numpy as np
import pytest

from ride_forces_analyzer.analysis.models import CapabilityState, EvidenceState, UnitLabel
from ride_forces_analyzer.analysis.recording import (
    RecordingAnalysis,
    prepare_recording_analysis,
    source_app_configuration,
)
from ride_forces_analyzer.importers import ImportSuccess, import_forces, import_forces_bytes
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

NOW = datetime(2026, 10, 17, tzinfo=UTC)
MANTA = next(name for name in REAL_FIXTURES if name.startswith("Manta-"))
KRAKEN = next(name for name in REAL_FIXTURES if name.startswith("Kraken-"))
VOLTRON = next(name for name in REAL_FIXTURES if name.startswith("VoltronNevera-"))


def prepared(filename: str) -> RecordingAnalysis:
    source = import_forces(REAL_FIXTURE_DIRECTORY / filename)
    assert isinstance(source, ImportSuccess)
    assert (source.byte_count, source.source_sha256) == REAL_FIXTURES[filename]
    return prepare_recording_analysis(
        source,
        source_app_configuration(),
        revision=1,
        calculation_time=NOW,
    )


@pytest.mark.parametrize("filename", REAL_FIXTURES)
def test_same_projection_cross_checks_all_source_extrema(filename: str) -> None:
    snapshot = prepared(filename)
    recording = snapshot.source.recording
    projected, smoothed = snapshot.forces.projected, snapshot.forces.smoothed
    assert projected.channels is not None and smoothed.channels is not None
    vertical = smoothed.channels[0].values
    selected = vertical[recording.indices.start : recording.indices.end + 1]
    assert recording.min_force and recording.max_force
    # Regression ceiling from the observed corpus, not a certified physical tolerance.
    assert abs(min(selected) - float(recording.min_force.value)) < 0.0002
    assert abs(max(selected) - float(recording.max_force.value)) < 0.0002
    assert projected.unit.label is UnitLabel.DIMENSIONLESS
    assert projected.unit.state is EvidenceState.ASSUMED
    assert smoothed.provenance is not None and smoothed.provenance.calculation_time == NOW
    assert smoothed.quality.capabilities == (("smoothing", CapabilityState.PROVISIONAL),)
    if filename == MANTA:
        assert min(vertical) == pytest.approx(-3.5571391829748977, abs=1e-12)
        assert max(vertical) == pytest.approx(2.6382813183644176, abs=1e-12)
        assert not np.allclose(projected.channels[0].values, vertical)


def test_source_app_policy_is_available_for_an_unrecognized_source_hash() -> None:
    raw = (REAL_FIXTURE_DIRECTORY / MANTA).read_bytes()
    modified = import_forces_bytes(raw + b" ")
    assert isinstance(modified, ImportSuccess)
    snapshot = prepare_recording_analysis(
        modified,
        source_app_configuration(),
        revision=1,
        calculation_time=NOW,
    )
    assert snapshot.source is modified
    assert snapshot.source.source_sha256 != REAL_FIXTURES[MANTA][1]
    assert snapshot.forces.smoothed.channels is not None
    assert snapshot.forces.smoothed.quality.capabilities == (
        ("smoothing", CapabilityState.PROVISIONAL),
    )


def test_independent_owner_csv_replay_samples() -> None:
    snapshot = prepared(MANTA)
    recording = snapshot.source.recording
    reference = (REAL_FIXTURE_DIRECTORY / MANTA).with_suffix(".csv")
    with reference.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == recording.indices.end - recording.indices.start + 1 == 6888
    for offset in (500, 2000, 2032, 3600, 6887):
        row = rows[offset]
        index = recording.indices.start + offset
        sample = snapshot.sample(index)
        assert sample.smoothed is not None
        values = (sample.smoothed.vertical, sample.smoothed.lateral, sample.smoothed.longitudinal)
        # The source app exports rounded values; it does not establish physical accuracy.
        expected = tuple(
            float(row[f"{channel} Forces (g)"])
            for channel in (
                "Vertical",
                "Lateral",
                "Longitudinal",
            )
        )
        assert tuple(round(value, 2) for value in values) == expected
        assert sample.combined_g is not None
        assert round(sample.combined_g, 2) == float(
            row["Combined Forces (g)"],
        )
        seconds, frame = divmod(offset, 50)
        minutes, seconds = divmod(seconds, 60)
        assert row["Timestamp"] == f"{minutes:02d}:{seconds:02d}.{frame:02d}"
        assert sample.replay_seconds == offset / 50
        assert sample.orientation_degrees is not None
        assert round(sample.orientation_degrees, 2) == float(
            row["Tilt Angle Orientation (degrees)"],
        )
    # The app's first exported force differs; keep the discrepancy rather than fitting an edge rule.
    first = snapshot.sample(recording.indices.start).smoothed
    assert first is not None
    assert float(rows[0]["Vertical Forces (g)"]) == 1.00
    assert round(first.vertical, 2) == 1.01


def test_kraken_replay_sample_counter_and_documented_start_discrepancy() -> None:
    from math import sqrt

    snapshot = prepared(KRAKEN)
    recording = snapshot.source.recording
    for seconds, frame, forces, combined, orientation in (
        (0, 0, (0.98, -0.01, -0.10), 0.99, 6),
        (54, 25, (0.93, 0.00, 0.35), 0.99, 20),
        (76, 28, (2.21, -0.08, -0.36), 2.24, 72),
        (91, 47, (4.02, 0.09, -0.15), 4.02, 29),
        (108, 13, (3.59, 0.04, -0.02), 3.59, 34),
        (112, 4, (3.43, 0.05, -0.05), 3.43, 0),
        (122, 3, (1.24, 0.34, -0.96), 1.61, 136),
        (128, 16, (1.00, -0.08, -0.90), 1.35, 2),
    ):
        # Replay suffix is a sample counter at 50 Hz, not hundredths of a second.
        index = recording.indices.start + seconds * 50 + frame
        sample = snapshot.sample(index)
        assert sample.smoothed is not None
        values = (sample.smoothed.vertical, sample.smoothed.lateral, sample.smoothed.longitudinal)
        assert sample.replay_seconds == seconds + frame / 50
        actual = tuple(round(value, 2) for value in values)
        magnitude = round(sqrt(sum(value * value for value in values)), 2)
        if seconds == 0 and frame == 0:
            # Preserve the observed mismatch; do not fit an unverified edge rule.
            assert forces == (0.98, -0.01, -0.10) and combined == 0.99
            assert actual == (1.00, 0.00, -0.10) and magnitude == 1.00
        else:
            assert actual == forces and magnitude == combined
        assert sample.orientation_degrees is not None
        assert round(sample.orientation_degrees) == orientation


def test_voltron_screenshot_extrema_and_display_rounding_difference() -> None:
    snapshot = prepared(VOLTRON)
    recording = snapshot.source.recording
    channels = snapshot.forces.smoothed.channels
    assert channels is not None
    selected = tuple(
        channel.values[recording.indices.start : recording.indices.end + 1] for channel in channels
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
