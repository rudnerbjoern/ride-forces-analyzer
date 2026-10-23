"""Content-bound reference preferences admit valid choices and preserve source evidence."""

from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from ride_forces_analyzer.analysis.calibration import (
    CalibrationOverrides,
    CalibrationReferenceError,
)
from ride_forces_analyzer.analysis.recording import source_app_configuration
from ride_forces_analyzer.storage.preferences import Preferences
from tests.analysis.test_recording_preparation import NOW, synthetic_source


def test_references_survive_restart_preserve_bounds_and_reject_invalid_replacement(
    tmp_path: Path,
) -> None:
    source = synthetic_source(accelerationSequence=[{"x": "0", "y": "1", "z": "1"}] * 7)
    preferences = Preferences(tmp_path / "references.sqlite3")
    key = source.source_sha256
    original = source.recording.source.original_bytes
    assert preferences.recording_calibration(key) is None
    assert preferences.remember_recording_bounds(key, (1, 5))
    choice = CalibrationOverrides(gravity_index=3)
    assert preferences.remember_recording_calibration(source, choice)
    restored = Preferences(preferences.path)
    assert restored.recording_calibration(key) == choice
    assert restored.recording_calibration("a" * 64) is None
    with pytest.raises(CalibrationReferenceError):
        restored.remember_recording_calibration(source, CalibrationOverrides(gravity_index=7))
    assert restored.recording_calibration(key) == choice
    assert restored.recording_bounds(key) == (1, 5)
    assert restored.remember_recording_calibration(source, CalibrationOverrides())
    assert restored.recording_calibration(key) is None
    assert restored.recording_bounds(key) == (1, 5)
    assert source.recording.source.original_bytes == original


@pytest.mark.parametrize(
    "column,value",
    (
        ("algorithm_version", "unsupported"),
        ("window_samples", 11),
        ("gravity_index", -1),
        ("gravity_index", 100),
    ),
)
def test_invalid_stored_references_keep_valid_bounds_and_original_calibration(
    tmp_path: Path,
    column: str,
    value: str | int,
) -> None:
    source = synthetic_source(accelerationSequence=[{"x": "0", "y": "1", "z": "1"}] * 7)
    preferences = Preferences(tmp_path / "references.sqlite3")
    assert preferences.remember_recording_bounds(source.source_sha256, (1, 5))
    assert preferences.remember_recording_calibration(source, CalibrationOverrides(gravity_index=3))
    with closing(sqlite3.connect(preferences.path)) as connection, connection:
        connection.execute(f"UPDATE recording_calibration SET {column} = ?", (value,))
    before = preferences.path.read_bytes()
    configuration = preferences.recording_configuration(
        source,
        source_app_configuration(),
        calculation_time=NOW,
    )
    assert configuration.ride_bounds == (1, 5)
    assert not configuration.calibration.active
    assert preferences.path.read_bytes() == before


def test_unavailable_calibration_storage_does_not_prevent_opening(tmp_path: Path) -> None:
    source = synthetic_source(accelerationSequence=[{"x": "0", "y": "1", "z": "1"}] * 7)
    preferences = Preferences(tmp_path)
    assert preferences.recording_calibration(source.source_sha256) is None
    assert not preferences.remember_recording_calibration(
        source,
        CalibrationOverrides(gravity_index=3),
    )
    assert (
        preferences.recording_configuration(
            source,
            source_app_configuration(),
            calculation_time=NOW,
        )
        == source_app_configuration()
    )
