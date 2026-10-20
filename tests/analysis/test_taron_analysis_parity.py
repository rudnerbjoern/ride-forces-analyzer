"""Exact migration parity against the existing Taron analysis pipeline."""

from datetime import UTC, datetime
from hashlib import sha256

import pytest

from ride_forces_analyzer.analysis import airtime
from ride_forces_analyzer.analysis.models import AnalysisProfile, ProfileName, UnitLabel
from ride_forces_analyzer.analysis.orientation import orientation_degrees
from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    AvailabilityState,
    StageConfiguration,
    VerticalContext,
    prepare_recording_analysis,
)
from ride_forces_analyzer.explorer import present_recording
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

NOW = datetime(2026, 10, 20, tzinfo=UTC)
PENDING = "Recording analysis preparation and sample access are not implemented"


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PENDING)
def test_taron_matches_current_analysis_for_every_sample() -> None:
    """Require exact legacy parity for all Taron samples, including recording edges.

    Compare the existing explorer/reference and export-orientation paths with
    new preparation and sample access. No new results are fabricated from the
    reference: only the existing path produces expected values. The test remains
    pending while new operations raise NotImplementedError; other failures are
    real failures. Remove the strict xfail marker when implementation passes.
    """
    filename = next(name for name in REAL_FIXTURES if name.startswith("Taron-"))
    path = REAL_FIXTURE_DIRECTORY / filename
    original = path.read_bytes()
    modified = path.stat().st_mtime_ns
    assert (len(original), sha256(original).hexdigest()) == REAL_FIXTURES[filename]
    try:
        source = import_forces(path)
        assert isinstance(source, ImportSuccess)
        legacy = present_recording(source)
        reference = legacy.reference
        old_context = legacy.airtime_context
        assert reference is not None and old_context is not None
        old_orientation = orientation_degrees(source.recording)
        expected_context = tuple(
            VerticalContext(label.lower().replace(" ", "_")) for label in old_context.labels
        )
        assert len(old_orientation) == len(expected_context) == legacy.count
        configuration = AnalysisConfiguration(
            profile=AnalysisProfile(
                name=ProfileName.RIDER_CALIBRATED,
                policy_references=("ADR-0006: source-app projection and centered mean",),
                assumptions=(
                    "Source acceleration interpreted as g under the owner-adopted policy",
                ),
                allow_provisional=True,
            ),
            projection=StageConfiguration("source-direction-unit-projection", "1"),
            smoothing=StageConfiguration(
                "centered-mean",
                "1",
                (("window_samples", reference.smoothing_window),),
            ),
            orientation=StageConfiguration("source-gravity-tilt", "1"),
            context=StageConfiguration(
                "vertical-context",
                "1",
                (
                    ("floater_bound_g", airtime.FLOATER_BOUND_G),
                    ("strong_bound_g", airtime.STRONG_BOUND_G),
                    ("onset_window_seconds", airtime.ONSET_WINDOW_SECONDS),
                    ("ejector_onset_g_per_second", airtime.EJECTOR_ONSET_G_PER_SECOND),
                    ("onset_memory_seconds", airtime.ONSET_MEMORY_SECONDS),
                    ("context_confirm_seconds", airtime.CONTEXT_CONFIRM_SECONDS),
                    ("floater_exit_bound_g", airtime.FLOATER_EXIT_BOUND_G),
                    ("strong_exit_bound_g", airtime.STRONG_EXIT_BOUND_G),
                ),
            ),
        )
        current = prepare_recording_analysis(
            source,
            configuration,
            revision=1,
            calculation_time=NOW,
        )
        current.validate()
        assert current.source.source_sha256 == source.source_sha256
        assert current.source.recording.source.original_bytes == original
        assert current.source.recording.metadata == source.recording.metadata
        assert current.source.recording.attributes == source.recording.attributes
        assert current.time.source_indices == tuple(range(legacy.count))
        assert current.time.basis.sample_rate == source.recording.motion.sample_rate
        assert current.time.replay_origin == source.recording.indices.start
        assert current.forces.projected.unit.label is UnitLabel.DIMENSIONLESS
        for index in range(legacy.count):
            sample = current.sample(index)
            where = f"Taron sample {index}"
            assert sample.index == index, where
            assert sample.raw == source.recording.motion.acceleration[index], where
            assert sample.recording_seconds == legacy.time_at(index), where
            assert (
                sample.replay_seconds
                == (index - source.recording.indices.start) / legacy.sample_rate
            ), where
            assert sample.projected is not None, where
            assert sample.smoothed is not None, where
            assert (
                sample.projected.vertical,
                sample.projected.lateral,
                sample.projected.longitudinal,
            ) == tuple(axis[index] for axis in reference.raw_projection), (
                f"{where}: projected forces"
            )
            assert (
                sample.smoothed.vertical,
                sample.smoothed.lateral,
                sample.smoothed.longitudinal,
            ) == tuple(axis[index] for axis in reference.channels), f"{where}: smoothed forces"
            assert sample.orientation_degrees == old_orientation[index], f"{where}: orientation"
            assert sample.context is expected_context[index], f"{where}: vertical context"
            for availability in (
                sample.projection_availability,
                sample.smoothing_availability,
                sample.orientation_availability,
                sample.context_availability,
            ):
                assert availability.state is AvailabilityState.AVAILABLE, where
    finally:
        assert path.read_bytes() == original
        assert path.stat().st_mtime_ns == modified
