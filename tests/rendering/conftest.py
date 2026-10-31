"""Immutable reference data shared by the rendering test session."""

import pytest

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


@pytest.fixture(scope="session")
def manta() -> ExplorerData:
    """Prepare once; tests derive their own snapshots, settings and renderers."""
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    assert isinstance(data, ExplorerData)
    return data
