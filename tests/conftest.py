"""Shared data fixtures; native GUI state is isolated in ui/conftest.py."""

import pytest
from collections.abc import Iterator
from tempfile import TemporaryDirectory
from pathlib import Path

from ride_forces_analyzer.domain import (
    MotionSequence,
    Recording,
    RecordingIndices,
    RecordingMetadata,
    SourceEnvelope,
    SourceNumber,
    Vector3,
)


@pytest.fixture
def synthetic_recording() -> Recording:
    raw = (
        b' {"schemaVersion":"2.2.0","device":"Apple Watch","advancedRecording":false,'
        b'"accelerationSequence":[{"x":"0.000","y":"0","z":"1.000"},'
        b'{"x":"1.000","y":"0","z":"0"}],"startIndex":0,"endIndex":1}\r\n'
    )
    root: dict[str, object] = {
        "schemaVersion": "2.2.0",
        "device": "Apple Watch",
        "advancedRecording": False,
        "accelerationSequence": [
            {"x": "0.000", "y": "0", "z": "1.000"},
            {"x": "1.000", "y": "0", "z": "0"},
        ],
        "startIndex": SourceNumber("0"),
        "endIndex": SourceNumber("1"),
    }
    return Recording(
        "2.2.0",
        SourceEnvelope(raw, root),
        MotionSequence([Vector3(0, 0, 1), Vector3(1, 0, 0)]),
        RecordingIndices(0, 1),
        metadata=RecordingMetadata(device="Apple Watch", advanced_recording=False),
    )


@pytest.fixture
def export_directory() -> Iterator[Path]:
    with TemporaryDirectory(dir=".tmp") as directory:
        yield Path(directory)
