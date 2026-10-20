"""Stage 2: FR-001/003–010/024/026 strict source decoding and bounded I/O."""

# cspell:words fstat truefalse

from collections.abc import Iterator, Mapping
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256
import json
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import MagicMock
import urllib.request

import pytest

from ride_forces_analyzer.domain import SourceEnvelope, SourceNumber
from ride_forces_analyzer.importers import (
    DEFAULT_LIMITS,
    DecodeSuccess,
    ImportFailure,
    ImportLimits,
    decode_forces,
    decode_forces_bytes,
)
from ride_forces_analyzer.importers import decoder
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

_BASE = {
    "schemaVersion": "2.2.0",
    "accelerationSequence": [{"x": "0.000", "y": "0", "z": "1.00"}],
    "startIndex": 0,
    "endIndex": 0,
}


def _document(**extras: object) -> bytes:
    return json.dumps({**_BASE, **extras}, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8",
    )


def _failure(raw: bytes, code: str, *, limits: ImportLimits = DEFAULT_LIMITS) -> ImportFailure:
    result = decode_forces_bytes(raw, limits=limits)
    assert isinstance(result, ImportFailure)
    assert len(result.diagnostics) == 1 and result.diagnostics[0].code == code
    assert result.recording is None
    assert result == decode_forces_bytes(raw, limits=limits)
    return result


@pytest.fixture
def decoder_directory() -> Iterator[Path]:
    root = Path(__file__).resolve().parents[2] / ".tmp"
    root.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="decoder-", dir=root) as directory:
        yield Path(directory)


@pytest.mark.parametrize("filename", REAL_FIXTURES, ids=lambda name: name.split("-", 1)[0])
def test_all_five_files_decode_losslessly_without_source_changes(filename: str) -> None:
    path = REAL_FIXTURE_DIRECTORY / filename
    modified = path.stat().st_mtime_ns
    original = path.read_bytes()
    assert (len(original), sha256(original).hexdigest()) == REAL_FIXTURES[filename]
    result = decode_forces(path)
    assert isinstance(result, DecodeSuccess)
    assert result.schema_version == "2.2.0" and result.diagnostics == ()
    assert result.source.original_bytes == original
    assert result.source.provenance.path == path
    assert (result.byte_count, result.source_sha256) == REAL_FIXTURES[filename]
    bytes_result = decode_forces_bytes(original)
    assert isinstance(bytes_result, DecodeSuccess)
    assert bytes_result.source.root == result.source.root
    assert bytes_result.source.provenance.path is None
    assert path.read_bytes() == original and path.stat().st_mtime_ns == modified
    assert not hasattr(result, "recording")


@pytest.mark.parametrize("raw", [b"", b" \t\r\n", b"\xef\xbb\xbf", b"\xef\xbb\xbf \n"])
def test_empty_input_retains_known_bytes(raw: bytes) -> None:
    result = _failure(raw, "EMPTY_INPUT")
    assert result.source is not None and result.source.original_bytes == raw
    assert result.byte_count == len(raw) and result.source_sha256 == sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b'"\xc0\xaf"',
        b'"\xed\xa0\x80"',
        b'"\xf0\x9f"',
        '{"schemaVersion":"2.2.0"}'.encode("utf-16"),
        '{"schemaVersion":"2.2.0"}'.encode("utf-32"),
    ],
)
def test_invalid_utf8_and_other_encodings_are_not_guessed(raw: bytes) -> None:
    result = _failure(raw, "INVALID_UTF8")
    assert result.source is not None and result.source.root is None
    assert result.source.original_bytes == raw


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"{]",
        b'{"x":}',
        b"[1,]",
        b'{"x":1,}',
        b"{}{}",
        b"//comment\n{}",
        b"{'x':1}",
        b'{"x":01}',
        b'{"x":1.}',
        b'{"x":+1}',
        b'{"x":.1}',
        b'{"x":1e}',
        b'"bad\\q"',
        b'"bad\\u12xz"',
        b'"bad\\u123"',
        b'"bad\x00"',
        b'"unterminated',
        b'"escape\\',
        b"\xef\xbb\xbf\xef\xbb\xbf{}",
        b"{}\xef\xbb\xbf",
        b'{"x":truefalse}',
    ],
)
def test_malformed_json_has_safe_deterministic_errors(raw: bytes) -> None:
    result = _failure(raw, "INVALID_JSON")
    assert result.source is not None and result.source.root is None
    assert result.source.original_bytes == raw
    assert result.diagnostics[0].message == "Invalid JSON syntax"


@pytest.mark.parametrize("literal", [b"NaN", b"Infinity", b"-Infinity"])
def test_non_json_numeric_constants_fail_even_in_unknown_nested_fields(literal: bytes) -> None:
    result = _failure(b'{"extension":[{"value":' + literal + b"}]}", "NON_JSON_NUMBER")
    assert result.diagnostics[0].json_path == "/extension/0/value"


@pytest.mark.parametrize("raw", [b"[]", b"[{}]", b"null", b"false", b'"2.2.0"', b"0"])
def test_root_must_be_an_object(raw: bytes) -> None:
    _failure(raw, "INVALID_ROOT")


@pytest.mark.parametrize(
    "raw, pointer",
    [
        (b'{"x":1,"x":2}', "/x"),
        (b'{"nested":{"a/b~c":1,"a/b~c":2}}', "/nested/a~1b~0c"),
        (b'{"array":[{"x":1,"x":2}]}', "/array/0/x"),
        (b'{"x":1,"\\u0078":2}', "/x"),
        (b'{"\\ud83d\\ude00":1,"\xf0\x9f\x98\x80":2}', "/😀"),
    ],
)
def test_duplicate_members_are_rejected_at_all_depths(raw: bytes, pointer: str) -> None:
    result = _failure(raw, "DUPLICATE_JSON_KEY")
    assert result.diagnostics[0].json_path == pointer
    assert result.source is not None and result.source.root is None


def test_identical_member_names_in_distinct_objects_are_valid() -> None:
    result = decode_forces_bytes(_document(extension=[{"x": 1}, {"x": 2}]))
    assert isinstance(result, DecodeSuccess)


@pytest.mark.parametrize("version", [None, False, 2.2, [], {}, ""])
def test_schema_version_requires_a_nonempty_string(version: object) -> None:
    result = _failure(_document(schemaVersion=version), "INVALID_SCHEMA_VERSION")
    assert result.diagnostics[0].json_path == "/schemaVersion"
    assert result.schema_version is None


def test_missing_version_is_distinct_from_supported_schema() -> None:
    raw = json.dumps(
        {key: value for key, value in _BASE.items() if key != "schemaVersion"},
    ).encode()
    _failure(raw, "INVALID_SCHEMA_VERSION")


@pytest.mark.parametrize("version", ["2.1.0", "2.2.1", "3.0.0", " 2.2.0", "2.2.0 ", "future"])
def test_dispatch_accepts_only_literal_220(version: str) -> None:
    result = _failure(_document(schemaVersion=version), "UNSUPPORTED_SCHEMA_VERSION")
    assert result.schema_version == version and result.source is not None
    assert result.source.root is not None


@pytest.mark.parametrize("field", ["accelerationSequence"])
def test_missing_core_fields_are_not_successful_decodes(field: str) -> None:
    raw = json.dumps({key: value for key, value in _BASE.items() if key != field}).encode()
    result = _failure(raw, "MISSING_REQUIRED_FIELD")
    assert result.schema_version == "2.2.0"
    assert result.diagnostics[0].json_path == "/" + field


@pytest.mark.parametrize(
    "value",
    [None, False, {}, "[]", [], [None], [{"x": None, "y": "0", "z": "1"}]],
)
def test_invalid_required_motion_shapes_fail_without_conversion(value: object) -> None:
    _failure(_document(accelerationSequence=value), "INVALID_REQUIRED_FIELD")


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_missing_required_component_is_targeted(axis: str) -> None:
    vector = {key: "0" for key in ("x", "y", "z") if key != axis}
    result = _failure(_document(accelerationSequence=[vector]), "MISSING_REQUIRED_FIELD")
    assert result.diagnostics[0].json_path == "/accelerationSequence/0/" + axis


@pytest.mark.parametrize("field", ["startIndex", "endIndex"])
@pytest.mark.parametrize("value", [None, False, "0", [], {}, 0.5])
def test_required_index_json_shape_is_checked(field: str, value: object) -> None:
    _failure(_document(**{field: value}), "INVALID_REQUIRED_FIELD")


def test_no_motion_conversion_defaults_gps_or_time_interpretation_occurs() -> None:
    raw = _document(
        accelerationSequence=[{"x": "NaN", "y": " 0 ", "z": "invalid"}],
        endIndex=999,
        gravitySequence="defective",
        sampleRate=0,
        ridingPosition=None,
        locationSequence=[{"timestamp": -1, "speed": -1}],
        device="Apple Watch",
    )
    result = decode_forces_bytes(raw)
    assert isinstance(result, DecodeSuccess)  # Valid schema shape, not valid measured motion.
    root = result.source.root
    assert root is not None and root["sampleRate"] == SourceNumber("0")
    assert root["ridingPosition"] is None and root["gravitySequence"] == "defective"
    assert root["endIndex"] == SourceNumber("999")


def test_source_bytes_number_lexemes_strings_extensions_and_absence_are_lossless() -> None:
    raw = b"\xef\xbb\xbf \r\n" + _document().replace(b'"startIndex":0', b'"startIndex":-0')[:-1]
    raw += b',"extension":{"n":1.000e+2,"s":"1.000e+2","tiny":1e-9999,"huge":1e9999,"flags":[true,null]},"url":"https://example.invalid/"}\r\n'
    result = decode_forces_bytes(raw)
    assert isinstance(result, DecodeSuccess)
    assert result.source.original_bytes == raw and result.source_sha256 == sha256(raw).hexdigest()
    root = result.source.root
    assert root is not None and "sampleRate" not in root and "ridingPosition" not in root
    extension = root["extension"]
    assert isinstance(extension, Mapping)
    assert extension["n"] == SourceNumber("1.000e+2") and extension["s"] == "1.000e+2"
    assert extension["tiny"] == SourceNumber("1e-9999") and extension["huge"] == SourceNumber(
        "1e9999",
    )
    assert extension["flags"] == (True, None)
    with pytest.raises(TypeError):
        cast(dict[str, object], extension)["n"] = "changed"
    with pytest.raises(FrozenInstanceError):
        setattr(result, "source", SourceEnvelope(b"changed"))


@pytest.mark.parametrize("name", [definition.name for definition in fields(ImportLimits)])
@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, "1", None, sys.maxsize])
def test_limits_reject_invalid_configuration(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        ImportLimits(**cast(dict[str, int], {name: value}))


def test_supported_depth_ceiling_and_limits_immutability() -> None:
    assert replace(DEFAULT_LIMITS, max_depth=128).max_depth == 128
    with pytest.raises(ValueError):
        replace(DEFAULT_LIMITS, max_depth=129)
    with pytest.raises(FrozenInstanceError):
        setattr(DEFAULT_LIMITS, "max_bytes", 1)


@pytest.mark.parametrize("depth", [32, 128])
def test_exact_configured_nesting_is_accepted(depth: int) -> None:
    base = _document()[:-1]
    raw = base + b',"extension":' + b"[" * (depth - 1) + b"0" + b"]" * (depth - 1) + b"}"
    assert isinstance(
        decode_forces_bytes(raw, limits=replace(DEFAULT_LIMITS, max_depth=depth)),
        DecodeSuccess,
    )
    _failure(raw, "RESOURCE_LIMIT_EXCEEDED", limits=replace(DEFAULT_LIMITS, max_depth=depth - 1))


def test_exact_byte_limit_is_accepted_and_excess_not_retained() -> None:
    raw = _document()
    assert isinstance(
        decode_forces_bytes(raw, limits=replace(DEFAULT_LIMITS, max_bytes=len(raw))),
        DecodeSuccess,
    )
    result = _failure(
        raw,
        "RESOURCE_LIMIT_EXCEEDED",
        limits=replace(DEFAULT_LIMITS, max_bytes=len(raw) - 1),
    )
    assert result.source is None and result.byte_count is None and result.source_sha256 is None


@pytest.mark.parametrize(
    "name, extras, accepted, rejected",
    [
        ("max_sequence_length", {"extension": [0, 1, 2]}, 3, 2),
        ("max_depth", {"extension": {"a": []}}, 3, 2),
        ("max_object_members", {}, 4, 3),
        ("max_string_length", {"extension": "x" * 21}, 21, 20),
        ("max_number_length", {"extension": 1234}, 4, 3),
        ("max_nodes", {}, 9, 8),
    ],
)
def test_each_shape_limit_accepts_boundary_and_rejects_excess_before_tree_allocation(
    name: str,
    extras: dict[str, object],
    accepted: int,
    rejected: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _document(**extras)
    limits = replace(DEFAULT_LIMITS, **{name: accepted})
    assert isinstance(decode_forces_bytes(raw, limits=limits), DecodeSuccess)
    calls = MagicMock(side_effect=AssertionError("Full tree allocation must not start"))
    monkeypatch.setattr(decoder, "_decode_tree", calls)
    result = _failure(raw, "RESOURCE_LIMIT_EXCEEDED", limits=replace(limits, **{name: rejected}))
    assert name in result.diagnostics[0].message
    assert result.source is not None and result.source.root is None
    calls.assert_not_called()


def test_member_and_key_limits_apply_inside_unknown_extensions() -> None:
    _failure(
        _document(extension={str(i): i for i in range(5)}),
        "RESOURCE_LIMIT_EXCEEDED",
        limits=replace(DEFAULT_LIMITS, max_object_members=4),
    )
    _failure(
        _document(**{"a" * 21: None}),
        "RESOURCE_LIMIT_EXCEEDED",
        limits=replace(DEFAULT_LIMITS, max_string_length=20),
    )


def test_brackets_quotes_escapes_and_unicode_do_not_distort_budgets() -> None:
    raw = _document(extension='[}\\"{}[]', unicode="😀", flags=[True, None])
    assert isinstance(
        decode_forces_bytes(raw, limits=replace(DEFAULT_LIMITS, max_depth=3)),
        DecodeSuccess,
    )
    base = _document()[:-1]
    for token in (b'"\\ud83d\\ude00"', b'"\\u0041"', b'"\\ud800"', b'"\\\\"', b'"\\""'):
        raw = base + b',"unicode":' + token + b"}"
        assert isinstance(decode_forces_bytes(raw), DecodeSuccess)
    # All required member names fit 20 characters; exact decoded length counts.
    raw = base + b',"unicode":"' + b"\\ud83d\\ude00" * 20 + b'"}'
    assert isinstance(
        decode_forces_bytes(raw, limits=replace(DEFAULT_LIMITS, max_string_length=20)),
        DecodeSuccess,
    )
    _failure(raw, "RESOURCE_LIMIT_EXCEEDED", limits=replace(DEFAULT_LIMITS, max_string_length=19))
    raw = base + b',"unicode":"' + b"\\ud83d\\ude00" * 21 + b'"}'
    result = _failure(
        raw,
        "RESOURCE_LIMIT_EXCEEDED",
        limits=replace(DEFAULT_LIMITS, max_string_length=20),
    )
    assert result.diagnostics[0].json_path == "/unicode"


def test_adversarial_depth_is_rejected_without_changing_python_recursion_settings() -> None:
    recursion_limit = sys.getrecursionlimit()
    raw = b'{"extension":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"
    _failure(raw, "RESOURCE_LIMIT_EXCEEDED")
    assert sys.getrecursionlimit() == recursion_limit


def test_unrepresentable_number_is_structured_and_does_not_leak_token() -> None:
    result = _failure(b'{"x":1e9999999999999999999}', "INVALID_JSON_NUMBER")
    assert result.diagnostics[0].json_path == "/x"
    assert "999999" not in result.diagnostics[0].message


def test_diagnostic_budget_one_still_returns_a_fatal_error() -> None:
    result = _failure(
        b'{"a":1,"a":2}',
        "DUPLICATE_JSON_KEY",
        limits=replace(DEFAULT_LIMITS, max_diagnostics=1),
    )
    assert len(result.diagnostics) == 1


def test_path_errors_are_safe_and_never_invent_provenance(decoder_directory: Path) -> None:
    missing = decoder_directory / "missing.forces"
    for path, code in ((missing, "SOURCE_NOT_FOUND"), (decoder_directory, "INVALID_SOURCE_PATH")):
        result = decode_forces(path)
        assert isinstance(result, ImportFailure) and result.diagnostics[0].code == code
        assert result.source is None and result.schema_version is None
        assert str(path) not in result.diagnostics[0].message


@pytest.mark.parametrize(
    "error",
    [PermissionError("sensitive source path"), OSError("sensitive payload")],
)
def test_unreadable_paths_report_sanitized_errors(
    error: OSError,
    decoder_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = decoder_directory / "source.forces"
    path.write_bytes(_document())
    monkeypatch.setattr(Path, "open", MagicMock(side_effect=error))
    result = decode_forces(path)
    assert isinstance(result, ImportFailure) and result.diagnostics[0].code == "SOURCE_UNREADABLE"
    assert result.source is None and "sensitive" not in result.diagnostics[0].message


def test_path_read_is_bounded_even_when_stat_reports_smaller_file(
    decoder_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = decoder_directory / "source.forces"
    path.write_bytes(b"x")
    with path.open("rb") as real:
        stream = MagicMock(wraps=real)
        stream.__enter__.return_value = stream
        stream.__exit__.return_value = False
        stream.read.return_value = b"x" * 17
        monkeypatch.setattr(Path, "open", MagicMock(return_value=stream))
        result = decode_forces(path, limits=replace(DEFAULT_LIMITS, max_bytes=16))
        assert isinstance(result, ImportFailure) and result.source is None
        stream.read.assert_called_once_with(17)


def test_short_reads_are_joined_until_eof_without_truncating_source(
    decoder_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = decoder_directory / "source.forces"
    raw = _document()
    path.write_bytes(raw)
    with path.open("rb") as real:
        stream = MagicMock(wraps=real)
        stream.__enter__.return_value = stream
        stream.__exit__.return_value = False
        stream.read.side_effect = [raw[:7], raw[7:], b""]
        opened = MagicMock(return_value=stream)
        monkeypatch.setattr(Path, "open", opened)
        result = decode_forces(path, limits=replace(DEFAULT_LIMITS, max_bytes=len(raw)))
        assert isinstance(result, DecodeSuccess) and result.source.original_bytes == raw
        opened.assert_called_once_with("rb", buffering=0)
        assert [call.args[0] for call in stream.read.call_args_list] == [
            len(raw) + 1,
            len(raw) - 6,
            1,
        ]


def test_read_failure_never_reports_partial_bytes_as_complete_provenance(
    decoder_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = decoder_directory / "source.forces"
    path.write_bytes(_document())
    with path.open("rb") as real:
        stream = MagicMock(wraps=real)
        stream.__enter__.return_value = stream
        stream.__exit__.return_value = False
        stream.read.side_effect = [b"{", OSError("sensitive details")]
        monkeypatch.setattr(Path, "open", MagicMock(return_value=stream))
        result = decode_forces(path)
        assert (
            isinstance(result, ImportFailure) and result.diagnostics[0].code == "SOURCE_UNREADABLE"
        )
        assert result.source is None and result.byte_count is None


def test_non_regular_opened_handle_is_rejected_before_reading(
    decoder_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = decoder_directory / "source.forces"
    path.write_bytes(_document())
    with path.open("rb") as real:
        stream = MagicMock(wraps=real)
        stream.__enter__.return_value = stream
        stream.__exit__.return_value = False
        monkeypatch.setattr(Path, "open", MagicMock(return_value=stream))
        directory_stat = decoder_directory.stat()
        monkeypatch.setattr(decoder.os, "fstat", MagicMock(return_value=directory_stat))
        result = decode_forces(path)
        assert (
            isinstance(result, ImportFailure)
            and result.diagnostics[0].code == "INVALID_SOURCE_PATH"
        )
        stream.read.assert_not_called()


def test_invalid_path_is_a_structured_failure() -> None:
    result = decode_forces(Path("invalid\x00source.forces"))
    assert isinstance(result, ImportFailure) and result.diagnostics[0].code == "INVALID_SOURCE_PATH"


def test_network_paths_and_invalid_limits_are_rejected_before_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = MagicMock(side_effect=AssertionError("No filesystem access allowed"))
    monkeypatch.setattr(Path, "stat", calls)
    result = decode_forces(Path(r"\\server\share\source.forces"))
    assert isinstance(result, ImportFailure) and result.diagnostics[0].code == "INVALID_SOURCE_PATH"
    with pytest.raises(ValueError):
        decode_forces(Path("unused"), limits=cast(ImportLimits, object()))
    calls.assert_not_called()


def test_programmer_types_fail_explicitly_without_coercion() -> None:
    with pytest.raises(TypeError):
        decode_forces_bytes(cast(bytes, bytearray(_document())))
    with pytest.raises(ValueError):
        decode_forces_bytes(_document(), limits=cast(ImportLimits, None))
    with pytest.raises(TypeError):
        decode_forces(cast(Path, "source.forces"))


def test_bytes_api_never_touches_files_or_fetches_embedded_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = MagicMock(side_effect=AssertionError("No I/O allowed in bytes decoder"))
    monkeypatch.setattr(Path, "open", calls)
    monkeypatch.setattr(Path, "stat", calls)
    monkeypatch.setattr(socket, "create_connection", calls)
    monkeypatch.setattr(urllib.request, "urlopen", calls)
    result = decode_forces_bytes(
        _document(url="https://example.invalid/location", location="optional"),
    )
    assert isinstance(result, DecodeSuccess)
    calls.assert_not_called()


def test_decoder_internal_failures_stay_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    for error in (RecursionError(), json.JSONDecodeError("unsafe data", "unsafe data", 0)):
        monkeypatch.setattr(decoder, "_decode_tree", MagicMock(side_effect=error))
        result = decode_forces_bytes(_document())
        assert isinstance(result, ImportFailure)
        assert result.source is not None and result.source.root is None
        assert "unsafe" not in result.diagnostics[0].message
