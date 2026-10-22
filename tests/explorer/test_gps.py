"""GPS geometry is independent of motion, with explicit missing-fix boundaries."""

from dataclasses import replace

import pytest

from ride_forces_analyzer.domain import GpsEntry, GpsFix, GpsSequence, GpsStatus, Recording
from ride_forces_analyzer.gps_overview import prepare_gps_overview
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


@pytest.mark.parametrize("filename", REAL_FIXTURES)
def test_original_gps_availability_and_preservation(filename: str) -> None:
    path = REAL_FIXTURE_DIRECTORY / filename
    before = path.read_bytes()
    result = import_forces(path)
    assert isinstance(result, ImportSuccess)
    overview = prepare_gps_overview(result.recording)
    if result.recording.gps is None:
        assert overview is None
    else:
        assert overview is not None
        assert overview.count == overview.total == len(result.recording.gps.entries)
        assert overview.points[0] == (0, 0)
    assert path.read_bytes() == before


def test_gps_gaps_bad_positions_and_north_up(synthetic_recording: Recording) -> None:
    fixes = (
        GpsFix(48, 7, timestamp=0),
        GpsFix(48.001, 7.001, timestamp=1),
        None,
        GpsFix(48, 7, timestamp=2),
        GpsFix(48, 7.001, timestamp=5),
        GpsFix(100, 7, timestamp=6),
        GpsFix(48, 7, timestamp=None),
    )
    recording = replace(
        synthetic_recording,
        gps_status=GpsStatus.PRESENT,
        gps=GpsSequence([GpsEntry(i, f) for i, f in enumerate(fixes)]),
    )
    overview = prepare_gps_overview(recording)
    assert overview is not None
    assert overview.count == 5 and overview.total == 7
    assert [len(segment) for segment in overview.segments] == [2, 1, 1, 1]
    assert overview.geographic_segments == (
        ((48, 7), (48.001, 7.001)),
        ((48, 7),),
        ((48, 7.001),),
        ((48, 7),),
    )
    assert overview.points[1][0] > 0 and overview.points[1][1] < 0
    empty = replace(recording, gps=GpsSequence([GpsEntry(0, None)]))
    assert prepare_gps_overview(empty) is None
