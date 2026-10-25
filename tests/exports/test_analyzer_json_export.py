"""Structured JSON preserves sample values while sharing time and quality data."""

from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from ride_forces_analyzer.analysis.preparation import (
    prepare_recording_analysis,
    source_app_configuration,
)
from ride_forces_analyzer.domain import SourceNumber
from ride_forces_analyzer.domain.models import Attribute
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from ride_forces_analyzer.exports.json import (
    JsonExportCancelled,
    export_analyzer_json,
    export_json,
)
from tests.exports.test_csv_export import snapshot
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_custom_calibration_exports_keep_original_and_effective_evidence(
    export_directory: Path,
) -> None:
    from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
    from tests.analysis.test_recording_preparation import NOW, prepare_snapshot, synthetic_source
    from ride_forces_analyzer.analysis.preparation import (
        source_app_configuration,
    )

    source = synthetic_source(accelerationSequence=[{"x": "1", "y": "1", "z": "1"}] * 7)
    analysis = prepare_snapshot(
        replace(source_app_configuration(), calibration=CalibrationOverrides(incline_index=3)),
        source,
    )
    app_path, analyzer_path = (
        export_directory / "references.json",
        export_directory / "references-analyzer.json",
    )
    export_json(analysis, app_path, 0, 6)
    export_analyzer_json(analysis, analyzer_path, 0, 6)
    app = json.loads(app_path.read_text())
    analyzer = json.loads(analyzer_path.read_text())
    evidence = app["metadata"]["calibration"]
    assert evidence == analyzer["analysis"]["calibration"]
    assert evidence["recipe"] == {
        "gravity_index": None,
        "incline_index": 3,
        "algorithm_version": "1",
        "window_samples": 5,
    }
    assert evidence["source_directions"]["longitudinal"] == {"x": 0, "y": 1, "z": 0}
    assert (
        evidence["effective_directions"]["longitudinal"]
        != evidence["source_directions"]["longitudinal"]
    )
    assert evidence["reference_support"] == {"gravity": None, "incline": [1, 5]}
    assert evidence["provenance"]["source_sha256"] == source.source_sha256
    assert evidence["provenance"]["calculation_time"] == NOW.isoformat()
    assert analyzer["recording"]["indices"]["incline"] is None


def test_effective_markers_keep_original_indices_and_share_replay_zero(
    export_directory: Path,
) -> None:
    original = snapshot()
    analysis = original.with_configuration(
        replace(original.configuration, ride_bounds=(1, 3)),
        revision=1,
        calculation_time=datetime.now(UTC),
    )
    app_path, analyzer_path = (
        export_directory / "markers.json",
        export_directory / "markers-analyzer.json",
    )
    export_json(analysis, app_path, 1, 3)
    export_analyzer_json(analysis, analyzer_path, 1, 3)
    app = json.loads(app_path.read_text())
    analyzer = json.loads(analyzer_path.read_text())
    assert app["Timestamp"][0] == "00:00.00" and app["replay_seconds"][0] == 0
    assert app["metadata"]["effective_ride_bounds"] == [1, 3]
    assert app["metadata"]["source_indices"]["start"] == original.source.recording.indices.start
    assert analyzer["recording"]["effective_ride_bounds"] == [1, 3]
    assert analyzer["time"]["replay_origin"] == 1


@pytest.mark.parametrize("calibrated", [True, False])
@pytest.mark.parametrize("rate", [25.0, 50.0, 59.94])
def test_schema_preserves_prepared_values_time_quality_and_missingness(
    export_directory: Path,
    calibrated: bool,
    rate: float,
) -> None:
    analysis = snapshot(calibrated=calibrated, rate=rate)
    path = export_directory / "selection.analyzer.json"
    progress: list[int] = []
    assert export_analyzer_json(analysis, path, 1, 4, progress=progress.append) == 4
    content = json.loads(path.read_bytes())
    assert list(content) == [
        "schema_version",
        "recording",
        "analysis",
        "time",
        "samples",
        "quality",
    ]
    assert content["schema_version"] == 1
    assert progress == [4]
    time = content["time"]
    assert (time["first_sample"], time["sample_count"], time["replay_origin"]) == (1, 4, 2)
    assert time["basis"] == "inferred_uniform" and time["sample_rate_hz"] == rate
    assert analysis.time.basis.sample_rate is not None
    assert time["sample_rate_origin"] == analysis.time.basis.sample_rate.origin.value
    samples = content["samples"]
    quality = content["quality"]
    for offset in range(time["sample_count"]):
        index = time["first_sample"] + offset
        sample = analysis.sample(index)
        assert index / time["sample_rate_hz"] == sample.recording_seconds
        assert (index - time["replay_origin"]) / time["sample_rate_hz"] == sample.replay_seconds
        for axis in ("x", "y", "z"):
            assert samples["raw"][axis][offset] == getattr(sample.raw, axis)
        for group in ("projected", "smoothed"):
            force = getattr(sample, group)
            for axis in ("vertical", "lateral", "longitudinal"):
                assert samples[group][axis][offset] == (getattr(force, axis) if force else None)
                assert len(samples[group][axis]) == 4
        assert samples["smoothed"]["combined"][offset] == sample.combined_g
        assert samples["orientation"][offset] == sample.orientation_degrees
        assert samples["vertical_context"][offset] == (
            sample.context.value if sample.context is not None else None
        )
        assert quality["capabilities"] == {
            name: state.value for name, state in sample.quality.capabilities
        }
        diagnostics = [*quality["diagnostics"], *quality["sample_diagnostics"].get(str(index), [])]
        assert sorted(d["code"] for d in diagnostics) == sorted(
            d.code for d in sample.quality.diagnostics
        )
    assert samples["raw"]["x"] == [0.0] * 4
    assert samples["orientation"][1] is None
    if calibrated:
        assert "2" in quality["sample_diagnostics"]
    if not calibrated:
        assert samples["smoothed"]["vertical"] == [None] * 4
        assert content["analysis"]["availability"]["projection"]["state"] == "unavailable"
        assert content["analysis"]["availability"]["projection"]["reason"]
    assert content["analysis"]["units"] == {"raw": "unknown", "forces": "g", "orientation": "deg"}
    profile = content["analysis"]["profile"]
    assert profile["assumptions"] == list(analysis.configuration.profile.assumptions)
    assert profile["policy_references"] == list(analysis.configuration.profile.policy_references)


def test_metadata_retains_markers_weather_attributes_and_source_number_tokens(
    export_directory: Path,
) -> None:
    analysis = snapshot()
    recording = analysis.source.recording
    modified = replace(
        recording,
        metadata=replace(
            recording.metadata,
            name="Café",
            location="Park",
            temperature=12.5,
            date=SourceNumber("123.4500"),
        ),
        attributes=(
            Attribute("row", "Row", SourceNumber("2")),
            Attribute("seat", "Seat", "Left"),
            Attribute("train", "Train", {"slots": [SourceNumber("1.0"), None, True]}),
        ),
    )
    analysis = replace(analysis, source=replace(analysis.source, recording=modified))
    path = export_directory / "metadata.json"
    export_analyzer_json(analysis, path, 0, 0)
    result = json.loads(path.read_bytes())
    assert result["recording"]["name"] == "Café"
    assert result["recording"]["location"] == "Park"
    assert result["recording"]["temperature"] == 12.5
    assert result["recording"]["date"] == "123.4500"
    assert result["recording"]["indices"] == {
        "start": 2,
        "end": 5,
        "gravity": None,
        "incline": None,
    }
    assert result["recording"]["attributes"] == [
        {"id": "row", "label": "Row", "value": {"number_token": "2"}},
        {"id": "seat", "label": "Seat", "value": "Left"},
        {
            "id": "train",
            "label": "Train",
            "value": {"slots": [{"number_token": "1.0"}, None, True]},
        },
    ]
    assert modified.source.original_bytes == recording.source.original_bytes


def test_all_manta_samples_match_app_shaped_export_with_less_repeated_data(
    export_directory: Path,
) -> None:
    path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    imported = import_forces(path)
    assert isinstance(imported, ImportSuccess)
    analysis = prepare_recording_analysis(
        imported,
        source_app_configuration(),
        revision=0,
        calculation_time=datetime(2026, 10, 21, tzinfo=UTC),
    )
    first, last = imported.recording.indices.start, imported.recording.indices.end
    app_path, structured_path = export_directory / "app.json", export_directory / "analyzer.json"
    export_json(analysis, app_path, first, last)
    export_analyzer_json(analysis, structured_path, first, last)
    app = json.loads(app_path.read_bytes())
    structured = json.loads(structured_path.read_bytes())
    for group, prefix in (("raw", "raw"), ("projected", "projected")):
        for axis in ("x", "y", "z") if group == "raw" else ("vertical", "lateral", "longitudinal"):
            key = f"{prefix}_{axis}_{'source' if group == 'raw' else 'g'}"
            assert structured["samples"][group][axis] == app[key]
    for axis in ("vertical", "lateral", "longitudinal", "combined"):
        assert structured["samples"]["smoothed"][axis] == app[f"{axis.title()} Forces (g)"]
    assert structured["samples"]["orientation"] == app["Tilt Angle Orientation (degrees)"]
    assert structured["samples"]["vertical_context"] == app["vertical_context"]
    assert structured["time"]["sample_count"] == len(app["sample_index"]) == 6888
    assert all(row == structured["quality"]["capabilities"] for row in app["capabilities"])
    assert structured_path.stat().st_size < app_path.stat().st_size


@pytest.mark.parametrize("first,last", [(-1, 0), (3, 1), (0, 6), (True, 2)])
def test_invalid_intervals_do_not_write_output(
    export_directory: Path,
    first: int,
    last: int,
) -> None:
    path = export_directory / "invalid.json"
    with pytest.raises((TypeError, ValueError)):
        export_analyzer_json(snapshot(), path, first, last)
    assert not path.exists()


@pytest.mark.parametrize("after", [0, 250, 600])
def test_cancel_removes_incomplete_output(export_directory: Path, after: int) -> None:
    path = export_directory / "cancelled.json"
    count = 0

    def progress(value: int) -> None:
        nonlocal count
        count = value

    with pytest.raises(JsonExportCancelled):
        export_analyzer_json(
            snapshot(count=600),
            path,
            0,
            599,
            progress=progress,
            cancelled=lambda: count >= after,
        )
    assert not path.exists()
