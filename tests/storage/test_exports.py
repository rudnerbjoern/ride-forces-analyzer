"""Saved export definitions reject stale edits without damaging stored snapshots."""

from pathlib import Path
import json

from pydantic import ValidationError
import pytest

from ride_forces_analyzer.analysis.preparation import source_app_configuration
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.rendering.model import ExportSettings
from ride_forces_analyzer.storage.export_models import (
    BatchJob,
    SavedBatch,
    SavedPreset,
    make_preset,
)
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError


def test_stale_edits_and_invalid_rows_preserve_saved_batch(export_directory: Path) -> None:
    store = ExportStore(export_directory / "exports.sqlite3")
    chosen = make_preset("Preset", ExportSettings(), 11, "markers", source_app_configuration())
    job = BatchJob(
        recording_path=(export_directory / "ride.forces").resolve(),
        source_sha256="a" * 64,
        ride="Ride",
        preset=chosen,
        range_mode="selection",
        first_sample=0,
        last_sample=1,
    )
    store.save_preset(chosen)
    original = SavedBatch(name="Batch", schema_version=1, jobs=(job, job))
    store.save_batch(original)
    updated = original.model_copy(update={"jobs": (job,)})
    store.save_batch(updated, overwrite=True)
    assert ExportStore(store.path).batch("Batch") == updated
    with pytest.raises(ValueError, match="Invalid batch row"):
        store.remove_jobs("Batch", (1,))
    assert store.batch("Batch") == updated
    store.delete_preset(chosen.name)
    store.delete_batch(original.name)
    with pytest.raises(ExportStoreError, match="preset no longer exists"):
        store.save_preset(chosen, overwrite=True)
    with pytest.raises(ExportStoreError, match="batch no longer exists"):
        store.save_batch(updated, overwrite=True)
    with pytest.raises(ExportStoreError, match="batch no longer exists"):
        store.batch("Batch")
    with pytest.raises(ExportStoreError, match="Choose or create a batch"):
        store.append_jobs("Batch", (job,))
    with pytest.raises(ExportStoreError, match="batch no longer exists"):
        store.remove_jobs("Batch", (0,))
    assert store.presets() == store.batches() == ()


def test_batch_jobs_reject_reversed_ranges_and_relative_paths(export_directory: Path) -> None:
    chosen = make_preset("Preset", ExportSettings(), 11, "markers", source_app_configuration())
    for path, first, last, message in (
        ((export_directory / "ride.forces").resolve(), 2, 1, "Last sample"),
        (Path("ride.forces"), 0, 1, "absolute file paths"),
    ):
        with pytest.raises(ValidationError, match=message):
            BatchJob(
                recording_path=path,
                source_sha256="a" * 64,
                ride="Ride",
                preset=chosen,
                range_mode="selection",
                first_sample=first,
                last_sample=last,
            )


def test_python_recipe_mapping_requires_typed_configuration_without_coercion() -> None:
    configuration = source_app_configuration()
    recipe = {name: getattr(configuration, name) for name in configuration.__dataclass_fields__}
    with pytest.raises(ValidationError, match="instance of AnalysisConfiguration"):
        SavedPreset.model_validate(
            {
                "schema_version": 1,
                "name": "Preset",
                "settings": ExportSettings(),
                "smoothing_window": 11,
                "range_mode": "markers",
                "analysis_configuration": recipe,
            },
        )


def test_partial_calibration_retains_explicit_indices_and_fills_defaults() -> None:
    chosen = make_preset("Preset", ExportSettings(), 11, "markers", source_app_configuration())
    payload = json.loads(chosen.model_dump_json())
    payload["analysis_configuration"]["calibration"] = {"gravity_index": 42}
    restored = SavedPreset.model_validate_json(json.dumps(payload))
    assert restored.analysis_configuration.calibration == CalibrationOverrides(gravity_index=42)
    serialized = json.loads(restored.model_dump_json())
    assert serialized["analysis_configuration"]["calibration"]["incline_index"] is None
    payload["analysis_configuration"]["calibration"]["gravity_index"] = "42"
    with pytest.raises(ValidationError):
        SavedPreset.model_validate_json(json.dumps(payload))
