"""RFDB uses the normal asynchronous open path and unified snapshot."""

from ride_forces_analyzer.domain import RecordingFormat
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.support.recordings import RFDB_FIXTURE_DIRECTORY, RFDB_FIXTURES
from tests.ui.helpers import wait_until


def test_open_rfdb_recording_prepares_calibrated_view(explorer_window: ExplorerWindow) -> None:
    explorer_window.open_path(RFDB_FIXTURE_DIRECTORY / next(iter(RFDB_FIXTURES)))
    wait_until(explorer_window.open_action.isEnabled)
    data = explorer_window.data
    assert data is not None
    assert data.source.recording.source_format is RecordingFormat.RFDB
    assert data.analysis is not None
    assert data.analysis.sample(4109).smoothed is not None
    assert data.analysis.sample(4109).context is not None
    assert data.analysis.sample(4109).orientation_degrees is None
    assert data.ride_bounds == (4109, 7957)
