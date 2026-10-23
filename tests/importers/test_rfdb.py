"""Explicit unversioned RFDB admission and complete source preservation."""

# cspell:words compressobj wbits

from dataclasses import replace
import json
from pathlib import Path
import zlib

import pytest

from ride_forces_analyzer.domain import RecordingFormat
from ride_forces_analyzer.importers import (
    ImportFailure,
    ImportSuccess,
    import_forces,
    import_forces_bytes,
)
from tests.support.recordings import RFDB_FIXTURE_DIRECTORY, RFDB_FIXTURES


def document(**overrides: object) -> bytes:
    root: dict[str, object] = {
        "device": "iPhone",
        "sampleRate": 50,
        "startIndex": 0,
        "endIndex": 2,
        "accelerationSequence": [
            {"x": "0", "y": "0", "z": "1"},
            {"x": "0.4", "y": "0.6", "z": "-0.5"},
            {"x": "-0.3", "y": "-0.2", "z": "2"},
        ],
        "xCalibrationVector": {"x": "1", "y": "0", "z": "0"},
        "yCalibrationVector": {"x": "0", "y": "0", "z": "1"},
        "zCalibrationVector": {"x": "0", "y": "1", "z": "0"},
        "unknownField": {"preserve": [True, None, "001"]},
    }
    root.update(overrides)
    return json.dumps(root).encode()


def test_authorized_rfdb_recording_retains_original_source_and_capabilities() -> None:
    name = next(iter(RFDB_FIXTURES))
    path = RFDB_FIXTURE_DIRECTORY / name
    original = path.read_bytes()
    modified = path.stat().st_mtime_ns
    result = import_forces(path)
    assert isinstance(result, ImportSuccess)
    assert (result.byte_count, result.source_sha256) == RFDB_FIXTURES[name]
    recording = result.recording
    assert recording.source_format is RecordingFormat.RFDB
    assert recording.schema_version is None
    assert recording.source.original_bytes == original
    assert recording.source.root is not None and "schemaVersion" not in recording.source.root
    assert len(recording.motion.acceleration) == 9242
    assert recording.motion.sample_rate.value == 50
    assert recording.motion.gravity is None
    assert recording.gps is None
    assert (recording.indices.start, recording.indices.end) == (4109, 7957)
    assert (recording.indices.gravity, recording.indices.incline) == (1024, 3658)
    assert recording.vectors.vertical_direction is None
    assert recording.vectors.y_calibration is not None
    assert path.read_bytes() == original and path.stat().st_mtime_ns == modified
    with pytest.raises(ValueError):
        replace(recording, schema_version="2.2.0")


@pytest.mark.parametrize("version", [None, "", "9.0.0", 2])
def test_rfdb_shape_never_overrides_an_explicit_invalid_version(version: object) -> None:
    result = import_forces_bytes(document(schemaVersion=version))
    assert isinstance(result, ImportFailure)


@pytest.mark.parametrize("key", ["sampleRate", "xCalibrationVector", "startIndex"])
def test_incomplete_rfdb_signature_does_not_admit_generic_unversioned_json(key: str) -> None:
    root = json.loads(document())
    del root[key]
    result = import_forces_bytes(json.dumps(root).encode())
    assert isinstance(result, ImportFailure)
    assert result.diagnostics[0].code == "INVALID_SCHEMA_VERSION"


@pytest.mark.parametrize(
    "overrides",
    [{"sampleRate": 0}, {"endIndex": 10}, {"accelerationSequence": []}],
)
def test_rfdb_still_requires_valid_core_motion(overrides: dict[str, object]) -> None:
    assert isinstance(import_forces_bytes(document(**overrides)), ImportFailure)


def test_rfdb_uses_the_existing_compressed_file_adapter(export_directory: Path) -> None:
    original = document()
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(original) + compressor.flush()
    path = export_directory / "example.zforces"
    path.write_bytes(compressed)
    result = import_forces(path)
    assert isinstance(result, ImportSuccess)
    assert result.recording.source_format is RecordingFormat.RFDB
    assert result.recording.source.original_bytes == compressed
    assert result.recording.source.root is not None
    assert result.recording.source.root["unknownField"] == {"preserve": (True, None, "001")}
    assert path.read_bytes() == compressed
