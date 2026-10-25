"""FR-028–030; AC-01–09: full offline imports, integrity and bounded diagnostics."""

# cspell:words WRONLY RDWR CREAT Seaworld

from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import cast

import pytest

from ride_forces_analyzer.domain import GpsStatus, SourceEnvelope, SourceNumber, ValueOrigin
from ride_forces_analyzer.importers import (
    DEFAULT_LIMITS,
    ImportFailure,
    ImportLimits,
    ImportSuccess,
    Severity,
    import_forces,
    import_forces_bytes,
    ordered_diagnostics,
    parse_motion,
)
from tests.importers.test_motion import EXPECTED, VECTORS
from tests.importers.test_optional import EXPECTED_GPS, GPS_FIELDS, NUMBER_FIELDS, TEXT_FIELDS
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


def _document(**extras: object) -> bytes:
    root = {
        "schemaVersion": "2.2.0",
        "device": "Apple Watch",
        "accelerationSequence": [{"x": "0.000", "y": "0", "z": "1.00"}],
        "startIndex": 0,
        "endIndex": 0,
        **extras,
    }
    return json.dumps(root, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@pytest.fixture
def import_directory() -> Iterator[Path]:
    root = Path(__file__).resolve().parents[2] / ".tmp"
    root.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="import-service-", dir=root) as directory:
        yield Path(directory)


@pytest.mark.parametrize("filename", REAL_FIXTURES, ids=lambda name: name.split("-", 1)[0])
def test_full_import_keeps_every_original_field_and_provenance(
    filename: str,
) -> None:
    """AC-01–04/06/07/08: compare complete arrays, all metadata and original bytes."""
    path = REAL_FIXTURE_DIRECTORY / filename
    modified = path.stat().st_mtime_ns
    original = path.read_bytes()
    assert (len(original), sha256(original).hexdigest()) == REAL_FIXTURES[filename]
    result = import_forces(path)
    assert isinstance(result, ImportSuccess)
    assert (result.byte_count, result.source_sha256) == REAL_FIXTURES[filename]
    assert result.schema_version == "2.2.0"
    recording = result.recording
    source = recording.source
    assert source.original_bytes == original and source.root is not None
    assert source.provenance.path == path
    root = source.root
    name = filename.split("-", 1)[0]
    acceleration, gravity, start, end, gravity_index, incline_index, rate_origin = EXPECTED[name]
    assert len(recording.motion.acceleration) == acceleration
    assert (
        recording.indices.start,
        recording.indices.end,
        recording.indices.gravity,
        recording.indices.incline,
    ) == (start, end, gravity_index, incline_index)
    assert (
        recording.motion.sample_rate.value == 50
        and recording.motion.sample_rate.origin is rate_origin
    )
    for key, sequence in (
        ("accelerationSequence", recording.motion.acceleration),
        ("gravitySequence", recording.motion.gravity),
    ):
        if sequence is None:
            assert gravity is None and key not in root
            continue
        raw = root[key]
        assert isinstance(raw, tuple) and len(raw) == len(sequence)
        for item, vector in zip(raw, sequence, strict=True):
            assert isinstance(item, Mapping)
            for axis in ("x", "y", "z"):
                component = item[axis]
                assert isinstance(component, str) and getattr(vector, axis) == float(component)
    for key, accessor in VECTORS:
        vector = getattr(recording.vectors, accessor)
        raw_vector = root[key]
        assert vector is not None and isinstance(raw_vector, Mapping)
        for axis in ("x", "y", "z"):
            assert getattr(vector, axis) == float(cast(str, raw_vector[axis]))
    for key, accessor in TEXT_FIELDS.items():
        assert getattr(recording.metadata, accessor) == root.get(key)
    for key, accessor in NUMBER_FIELDS.items():
        value = root.get(key)
        assert getattr(recording.metadata, accessor) == (
            float(value.value) if isinstance(value, SourceNumber) else None
        )
    assert recording.metadata.date is root["date"]
    assert recording.metadata.advanced_recording is root["advancedRecording"]
    for key, accessor in (
        ("smoothingFactor", "smoothing_factor"),
        ("maxForce", "max_force"),
        ("minForce", "min_force"),
    ):
        assert getattr(recording, accessor) is root[key]
    position = recording.metadata.riding_position
    assert position is not None and position.value == root.get("ridingPosition", "Seated")
    assert position.origin is (
        ValueOrigin.SOURCE if "ridingPosition" in root else ValueOrigin.DEFAULT
    )
    attributes = root["attributes"]
    assert isinstance(attributes, tuple) and len(attributes) == len(recording.attributes)
    for raw_attribute, attribute in zip(attributes, recording.attributes, strict=True):
        assert isinstance(raw_attribute, Mapping)
        assert (attribute.id, attribute.label, attribute.value) == (
            raw_attribute["id"],
            raw_attribute["label"],
            raw_attribute["value"],
        )
    if EXPECTED_GPS[name] is None:
        assert recording.gps is None and recording.gps_status is GpsStatus.ABSENT
        assert recording.motion.gravity is None and not recording.motion.paired_motion_available
        assert recording.metadata.latitude is recording.metadata.longitude is None
        assert not result.diagnostics
    else:
        gps = root["locationSequence"]
        assert isinstance(gps, tuple) and recording.gps is not None
        assert len(gps) == len(recording.gps.entries) == EXPECTED_GPS[name]
        assert recording.gps_status is GpsStatus.PRESENT
        for index, (raw_fix, entry) in enumerate(zip(gps, recording.gps.entries, strict=True)):
            assert isinstance(raw_fix, Mapping) and entry.fix is not None and entry.index == index
            for key, accessor in GPS_FIELDS.items():
                number = raw_fix[key]
                assert isinstance(number, SourceNumber)
                assert getattr(entry.fix, accessor) == float(number.value)
    if name == "Taron":
        assert recording.indices.gravity == 1513 < recording.indices.start == 2284
        assert [(a.label, a.value) for a in recording.attributes] == [("Row", "2"), ("Seat", "1")]
    if name == "Manta":
        assert recording.metadata.location == "Seaworld Orlando"
        assert recording.metadata.temperature == pytest.approx(27.68781089782715)
        assert recording.metadata.weather_conditions == "Clear"
    assert result.diagnostics == ordered_diagnostics(result.diagnostics)
    assert all(d.severity is not Severity.ERROR for d in result.diagnostics)
    assert path.read_bytes() == original and path.stat().st_mtime_ns == modified
    with pytest.raises(FrozenInstanceError):
        setattr(recording, "metadata", None)


def test_repeated_path_and_bytes_imports_are_equivalent() -> None:
    path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    raw = path.read_bytes()
    first = import_forces(path)
    assert isinstance(first, ImportSuccess) and first == import_forces(path)
    from_bytes = import_forces_bytes(raw)
    assert isinstance(from_bytes, ImportSuccess) and from_bytes == import_forces_bytes(raw)
    # Only the file adapter adds the path; all parsed data and diagnostics agree.
    assert first.recording.source.original_bytes == from_bytes.recording.source.original_bytes
    assert first.recording.source.root == from_bytes.recording.source.root
    assert replace(first.recording, source=from_bytes.recording.source) == from_bytes.recording
    assert first.diagnostics == from_bytes.diagnostics
    assert first.recording.source.provenance.path == path
    assert from_bytes.recording.source.provenance.path is None


def test_concurrent_calls_have_no_shared_recording_or_diagnostic_state() -> None:
    raw = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")).read_bytes()
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(import_forces_bytes, [raw] * 3))
    assert all(isinstance(result, ImportSuccess) for result in results)
    assert results[0] == results[1] == results[2]
    first, second = results[0], results[1]
    assert isinstance(first, ImportSuccess) and isinstance(second, ImportSuccess)
    assert (
        first.recording is not second.recording
        and first.recording.source is not second.recording.source
    )


def test_unknown_fields_and_original_token_types_survive_full_import() -> None:
    raw = (
        b"\xef\xbb\xbf "
        + _document()[:-1]
        + (
            b',"extension":{"number":1.000e+2,"text":"1.000e+2","huge":1e9999,"flags":[true,null]},'
            b'"attributes":[{"id":"arbitrary","label":"Any","value":{"n":-0.00},"future":false}],'
            b'"locationSequence":[{"latitude":1.00,"longitude":2.00,"future":["0",0]}]}\r\n'
        )
    )
    result = import_forces_bytes(raw)
    assert isinstance(result, ImportSuccess) and result.recording.source.original_bytes == raw
    root = result.recording.source.root
    assert root is not None
    extension = root["extension"]
    assert isinstance(extension, Mapping)
    assert extension["number"] == SourceNumber("1.000e+2") and extension["text"] == "1.000e+2"
    assert extension["huge"] == SourceNumber("1e9999") and extension["flags"] == (True, None)
    attribute = result.recording.attributes[0]
    assert isinstance(attribute.value, Mapping) and attribute.value["n"] == SourceNumber("-0.00")
    gps = root["locationSequence"]
    assert isinstance(gps, tuple) and isinstance(gps[0], Mapping)
    assert gps[0]["future"] == ("0", SourceNumber("0"))
    assert "ridingPosition" not in root and "sampleRate" not in root
    assert result.recording.metadata.riding_position is not None
    assert result.recording.metadata.riding_position.origin is ValueOrigin.DEFAULT
    assert result.recording.motion.sample_rate.origin is ValueOrigin.DEFAULT
    with pytest.raises(TypeError):
        cast(dict[str, object], extension)["number"] = "changed"


@pytest.mark.parametrize(
    "extras, code",
    [
        ({"sampleRate": 0}, "INVALID_SAMPLE_RATE"),
        ({"sampleRate": None}, "INVALID_SAMPLE_RATE"),
        ({"sampleRate": "Infinity"}, "INVALID_SAMPLE_RATE"),
        ({"accelerationSequence": [{"x": "NaN", "y": "0", "z": "1"}]}, "INVALID_NUMERIC_COMPONENT"),
        ({"accelerationSequence": []}, "INVALID_REQUIRED_FIELD"),
        ({"gravitySequence": []}, "INVALID_MOTION_SEQUENCE"),
        ({"gravitySequence": [{"x": "0", "y": "0", "z": "1"}] * 2}, "MOTION_LENGTH_MISMATCH"),
        ({"endIndex": 1}, "INDEX_OUT_OF_RANGE"),
        ({"startIndex": True}, "INVALID_REQUIRED_FIELD"),
        ({"gravityIndex": -1}, "INDEX_OUT_OF_RANGE"),
        ({"schemaVersion": "2.3.0"}, "UNSUPPORTED_SCHEMA_VERSION"),
    ],
)
def test_core_failure_never_becomes_partial_success_and_next_call_recovers(
    extras: dict[str, object],
    code: str,
) -> None:
    raw = _document(**extras)
    result = import_forces_bytes(raw)
    assert isinstance(result, ImportFailure) and result.recording is None
    assert any(d.code == code and d.severity is Severity.ERROR for d in result.diagnostics)
    assert result.source is not None and result.source.original_bytes == raw
    assert result.byte_count == len(raw) and result.source_sha256 == sha256(raw).hexdigest()
    assert result == import_forces_bytes(raw)
    valid = import_forces_bytes(_document())
    assert isinstance(valid, ImportSuccess) and not valid.diagnostics


@pytest.mark.parametrize(
    "raw, code",
    [
        (b"", "EMPTY_INPUT"),
        (b"\xff", "INVALID_UTF8"),
        (b"{", "INVALID_JSON"),
        (b"[]", "INVALID_ROOT"),
        (b' {"n":1,"n":2}', "DUPLICATE_JSON_KEY"),
        (b'{"n":NaN}', "NON_JSON_NUMBER"),
        (b"{}", "INVALID_SCHEMA_VERSION"),
    ],
)
def test_decoder_failures_keep_their_structured_provenance(raw: bytes, code: str) -> None:
    result = import_forces_bytes(raw)
    assert isinstance(result, ImportFailure) and result.diagnostics[0].code == code
    assert result.byte_count == len(raw) and result.source_sha256 == sha256(raw).hexdigest()
    assert result == import_forces_bytes(raw)
    assert isinstance(import_forces_bytes(_document()), ImportSuccess)


@pytest.mark.parametrize(
    "extras, limit, maximum",
    [
        ({"extension": [0] * 4}, "max_sequence_length", 3),
        ({"extension": [[[0]]]}, "max_depth", 3),
        ({"extension": [0] * 20}, "max_nodes", 10),
        ({"extension": {str(i): i for i in range(6)}}, "max_object_members", 5),
        ({"extension": "x" * 65}, "max_string_length", 64),
        ({"extension": 1234}, "max_number_length", 3),
    ],
)
def test_global_decoder_budgets_apply_to_unknown_extensions(
    extras: dict[str, object],
    limit: str,
    maximum: int,
) -> None:
    raw = _document(**extras)
    result = import_forces_bytes(raw, limits=ImportLimits(**{limit: maximum}))
    assert (
        isinstance(result, ImportFailure)
        and result.diagnostics[0].code == "RESOURCE_LIMIT_EXCEEDED"
    )
    assert limit in result.diagnostics[0].message and result.recording is None
    assert isinstance(import_forces_bytes(raw), ImportSuccess)


@pytest.mark.parametrize("adapter", ["path", "bytes"])
def test_exact_byte_limit_passes_and_oversize_has_no_partial_provenance(
    import_directory: Path,
    adapter: str,
) -> None:
    raw = _document()
    path = import_directory / "synthetic.forces"
    path.write_bytes(raw)
    equal = ImportLimits(max_bytes=len(raw))
    excess = replace(equal, max_bytes=len(raw) - 1)
    valid = (
        import_forces(path, limits=equal)
        if adapter == "path"
        else import_forces_bytes(raw, limits=equal)
    )
    invalid = (
        import_forces(path, limits=excess)
        if adapter == "path"
        else import_forces_bytes(raw, limits=excess)
    )
    assert isinstance(valid, ImportSuccess) and isinstance(invalid, ImportFailure)
    assert invalid.source is None and invalid.byte_count is invalid.source_sha256 is None
    assert invalid.diagnostics[0].code == "RESOURCE_LIMIT_EXCEEDED"


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_one_diagnostic_budget_spans_motion_metadata_and_gps(limit: int) -> None:
    raw = _document(
        device="Future",
        location=None,
        locationSequence=[{"latitude": 1, "longitude": 2, "speed": -2}],
    )
    result = import_forces_bytes(raw, limits=ImportLimits(max_diagnostics=limit))
    assert len(result.diagnostics) == limit
    if limit == 3:
        assert isinstance(result, ImportSuccess)
        assert {d.code for d in result.diagnostics} == {
            "UNKNOWN_DEVICE_PROFILE",
            "INVALID_OPTIONAL_METADATA",
            "GPS_NEGATIVE_VALUE",
        }
    else:
        assert isinstance(result, ImportFailure) and result.recording is None
        assert result.diagnostics[0].code == "RESOURCE_LIMIT_EXCEEDED"
        assert result.diagnostics[0].json_path == (
            "/location" if limit == 1 else "/locationSequence/0/speed"
        )
        assert result.source is not None and result.source.original_bytes == raw
    assert result.diagnostics == ordered_diagnostics(result.diagnostics)
    assert result == import_forces_bytes(raw, limits=ImportLimits(max_diagnostics=limit))


def test_warning_budget_can_be_exactly_full_before_a_clean_optional_stage() -> None:
    result = import_forces_bytes(_document(device="Future"), limits=ImportLimits(max_diagnostics=1))
    assert isinstance(result, ImportSuccess) and len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "UNKNOWN_DEVICE_PROFILE"


def test_motion_diagnostic_generation_is_bounded_before_optional_parsing() -> None:
    raw = _document(
        accelerationSequence=[{"x": "bad", "y": "bad", "z": "bad"}] * 1000,
        endIndex=999,
    )
    result = import_forces_bytes(raw, limits=ImportLimits(max_diagnostics=2))
    assert isinstance(result, ImportFailure) and len(result.diagnostics) == 2
    fatal = next(d for d in result.diagnostics if d.code == "RESOURCE_LIMIT_EXCEEDED")
    assert fatal.json_path == "/accelerationSequence/0/z"
    assert result.diagnostics == ordered_diagnostics(result.diagnostics)
    # Standalone callers receive the same guard without needing a full import.
    source = SourceEnvelope(
        b"synthetic",
        {"accelerationSequence": [{"x": "bad", "y": "bad", "z": "bad"}]},
    )
    subset = parse_motion(source, limits=ImportLimits(max_diagnostics=2))
    assert isinstance(subset, ImportFailure) and len(subset.diagnostics) == 2


def test_optional_defects_survive_full_import_with_usable_core_motion() -> None:
    raw = _document(
        device="iPhone",
        ridingPosition=None,
        temperature="bad",
        attributes=[None, {"id": "id", "label": "Row", "value": "1"}],
        locationSequence=[{}, {"latitude": 1, "longitude": 2, "speed": -1}],
    )
    result = import_forces_bytes(raw)
    assert isinstance(result, ImportSuccess) and len(result.recording.motion.acceleration) == 1
    assert (
        result.recording.metadata.riding_position is result.recording.metadata.temperature is None
    )
    assert [a.label for a in result.recording.attributes] == ["Row"]
    gps = result.recording.gps
    assert gps is not None and gps.entries[0].fix is None and gps.entries[1].fix is not None
    assert gps.entries[1].fix.speed == -1
    assert {d.code for d in result.diagnostics} >= {
        "GRAVITY_UNAVAILABLE",
        "INVALID_OPTIONAL_METADATA",
        "INVALID_ATTRIBUTE",
        "INVALID_GPS_FIX",
        "GPS_NEGATIVE_VALUE",
    }
    assert not any(d.severity is Severity.ERROR for d in result.diagnostics)


def test_path_errors_recover_without_global_state(
    import_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = import_directory / "synthetic.forces"
    missing = import_forces(path)
    assert isinstance(missing, ImportFailure) and missing.diagnostics[0].code == "SOURCE_NOT_FOUND"
    assert missing.byte_count is missing.source_sha256 is None
    assert isinstance(import_forces(import_directory), ImportFailure)
    path.write_bytes(_document())
    with monkeypatch.context() as context:

        def denied(_path: Path, *args: object, **kwargs: object) -> object:
            raise PermissionError("controlled source permission failure")

        context.setattr(Path, "open", denied)
        result = import_forces(path)
        assert (
            isinstance(result, ImportFailure) and result.diagnostics[0].code == "SOURCE_UNREADABLE"
        )
    assert isinstance(import_forces(path), ImportSuccess)


@pytest.mark.parametrize("adapter", ["path", "bytes"])
def test_invalid_caller_limits_fail_before_path_access(
    import_directory: Path,
    adapter: str,
) -> None:
    with pytest.raises(ValueError, match="limits"):
        if adapter == "path":
            import_forces(import_directory / "nonexistent", limits=cast(ImportLimits, None))
        else:
            import_forces_bytes(_document(), limits=cast(ImportLimits, None))


def test_public_argument_types_are_not_silently_coerced() -> None:
    with pytest.raises(TypeError, match="path"):
        import_forces(cast(Path, "not-a-path"))
    with pytest.raises(TypeError, match="data"):
        import_forces_bytes(cast(bytes, bytearray(_document())))
    assert DEFAULT_LIMITS == ImportLimits()


@pytest.mark.parametrize("adapter", ["path", "bytes"])
def test_fresh_process_imports_are_qt_free_offline_and_never_write(
    import_directory: Path,
    adapter: str,
) -> None:
    """AC-03/08: reject Qt loading, any network activity and filesystem mutations."""
    path = import_directory / "synthetic.forces"
    raw = _document(extension={"url": "https://example.invalid/", "unknown": [False, None]})
    path.write_bytes(raw)
    modified = path.stat().st_mtime_ns
    script = r"""
import importlib.abc
import os
from pathlib import Path
import sys

class NoQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("PySide6", "PyQt6", "PyQt5"):
            raise AssertionError("Qt dependency in importer")
        return None

sys.dont_write_bytecode = True
sys.meta_path.insert(0, NoQt())
from ride_forces_analyzer.importers import ImportFailure, ImportSuccess, import_forces, import_forces_bytes
path = Path(sys.argv[2])
raw = path.read_bytes()
adapter = sys.argv[1]

def audit(event, args):
    if event.startswith("socket.") or event == "urllib.Request":
        raise AssertionError("Importer attempted network activity")
    if event in ("os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.chmod", "os.utime", "os.truncate"):
        raise AssertionError("Importer attempted filesystem mutation")
    if event == "open":
        filename, mode, flags = args
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise AssertionError("Importer attempted write access")
        if adapter == "bytes" or Path(filename) != path:
            raise AssertionError("Unexpected filesystem access")

sys.addaudithook(audit)
assert isinstance(import_forces_bytes(b"{"), ImportFailure)
first = import_forces(path) if adapter == "path" else import_forces_bytes(raw)
second = import_forces(path) if adapter == "path" else import_forces_bytes(raw)
assert isinstance(first, ImportSuccess) and first == second
assert first.recording.source.original_bytes == raw
assert not any(name.startswith(("PySide6", "PyQt")) for name in sys.modules)
print("Qt-free offline read-only import verified")
"""
    root = Path(__file__).resolve().parents[2]
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    # Instrumentation itself reads source and writes coverage data; keep the
    # audited child pristine while measuring importer behavior in the other tests.
    environment.pop("COVERAGE_PROCESS_CONFIG", None)
    environment.pop("COVERAGE_PROCESS_START", None)
    process = subprocess.run(
        [sys.executable, "-c", script, adapter, str(path)],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert process.stdout.strip() == "Qt-free offline read-only import verified"
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == modified


def test_full_import_propagates_an_explicit_optional_stage_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.importers import ImportDiagnostic, service

    failure = ImportFailure(
        (ImportDiagnostic("INVALID_OPTIONAL", Severity.ERROR, "", "Invalid optional data"),),
    )

    def failed_optional(source: SourceEnvelope, diagnostics: object) -> ImportFailure:
        return failure

    monkeypatch.setattr(service, "validate_optional_data", failed_optional)
    assert import_forces_bytes(_document()) is failure
