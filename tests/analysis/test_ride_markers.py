"""Effective ride markers retain original evidence and shared numerical stages."""

from dataclasses import replace
from typing import cast
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.analysis import recording
from ride_forces_analyzer.analysis.recording import AnalysisConfiguration
from ride_forces_analyzer.analysis.service import AnalysisService
from tests.analysis.test_recording_preparation import NOW, prepare_snapshot
from tests.analysis.test_recording_preparation import configuration as configuration


def test_marker_request_reuses_stages_and_updates_replay_without_changing_source(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prepare_snapshot(configuration)
    before = original.source.recording.source.original_bytes
    for name in ("project_directions", "centered_mean", "orientation_degrees"):
        monkeypatch.setattr(
            recording,
            name,
            Mock(side_effect=AssertionError("Repeated preparation")),
        )
    service = AnalysisService(original)
    deliveries: list[object] = []
    service.subscribe(deliveries.append)
    service.request_configuration(replace(configuration, ride_bounds=(1, 3)), calculation_time=NOW)
    changed = service.get_state().snapshot
    assert changed is not None and changed is not original
    assert changed.ride_bounds == (1, 3) and changed.replay_origin == 1
    assert changed.sample(1).replay_seconds == 0
    assert changed.sample(0).replay_seconds < 0
    assert changed.forces is original.forces
    assert changed.forces.projected is original.forces.projected
    assert changed.forces.smoothed is original.forces.smoothed
    assert changed.context is original.context and changed.events is original.events
    assert changed.orientation is original.orientation and changed.time is original.time
    assert changed.source is original.source
    assert changed.source.recording.source.original_bytes == before
    assert len(deliveries) == 3
    service.request_configuration(configuration, calculation_time=NOW)
    restored = service.get_state().snapshot
    assert restored is not None and restored.ride_bounds == original.ride_bounds


@pytest.mark.parametrize("bounds", ((-1, 2), (3, 1), (0, 999), (True, 2), (1.0, 2), (1,)))
def test_invalid_marker_overrides_are_rejected(
    bounds: object,
    configuration: AnalysisConfiguration,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        prepare_snapshot(replace(configuration, ride_bounds=cast(tuple[int, int], bounds)))
