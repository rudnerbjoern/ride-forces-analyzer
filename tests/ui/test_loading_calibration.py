"""Import workers restore references by source content while retaining original evidence."""

from pathlib import Path

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.explorer.loading import LoadWorker
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_worker_restores_calibration_after_rename_but_not_for_changed_content(
    tmp_path: Path,
) -> None:
    original_path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    original_bytes = original_path.read_bytes()
    source = import_forces(original_path)
    assert isinstance(source, ImportSuccess)
    choice = CalibrationOverrides(
        source.recording.indices.gravity,
        source.recording.indices.incline,
    )
    preferences = Preferences()
    assert preferences.remember_recording_bounds(source.source_sha256, (3600, 3700))
    assert preferences.remember_recording_calibration(source, choice)
    renamed = tmp_path / "renamed.forces"
    renamed.write_bytes(original_bytes)

    def load() -> ExplorerData:
        outcomes: list[object] = []
        failures: list[str] = []
        worker = LoadWorker(renamed)

        def completed(generation: int, data: object) -> None:
            outcomes.append(data)

        def failed(generation: int, error: str) -> None:
            failures.append(error)

        worker.signals.completed.connect(completed)
        worker.signals.failed.connect(failed)
        worker.run()
        assert not failures and len(outcomes) == 1
        data = outcomes[0]
        assert isinstance(data, ExplorerData)
        return data

    restored = load()
    assert restored.analysis is not None and restored.analysis.calibration is not None
    assert restored.analysis.configuration.calibration == choice
    assert restored.ride_bounds == (3600, 3700)
    assert restored.source.recording.indices == source.recording.indices
    assert restored.source.recording.vectors == source.recording.vectors
    assert restored.source.recording.source.original_bytes == original_bytes
    renamed.write_bytes(original_bytes + b" ")
    different = load()
    assert different.analysis is not None and different.analysis.calibration is None
    assert different.ride_bounds == (source.recording.indices.start, source.recording.indices.end)
    assert original_path.read_bytes() == original_bytes
