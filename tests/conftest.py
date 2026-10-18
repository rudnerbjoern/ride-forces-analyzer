"""Synthetic Stage 1 models; no original recording is decoded here."""

# cspell:words autouse LOCALAPPDATA

import pytest
from collections.abc import Iterator
from tempfile import TemporaryDirectory
from pathlib import Path

from ride_forces_analyzer.i18n import get_language, set_language

from ride_forces_analyzer.domain import (
    MotionSequence,
    Recording,
    RecordingIndices,
    RecordingMetadata,
    SourceEnvelope,
    SourceNumber,
    Vector3,
)


@pytest.fixture(autouse=True)
def isolated_user_preferences(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Iterator[None]:
    """GUI tests and their subprocesses never read or overwrite user preferences."""
    if "gui" not in request.path.stem:
        yield
        return
    with TemporaryDirectory(dir=".tmp") as directory:
        monkeypatch.setenv("LOCALAPPDATA", str(Path(directory).resolve()))
        original_language = get_language()
        try:
            yield
        finally:
            set_language(original_language)


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
