"""Compressed recordings use the same strict import pipeline and retain their source."""

# cspell:words compressobj wbits

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import zlib

import pytest

from ride_forces_analyzer.importers import (
    DEFAULT_LIMITS,
    DecodeSuccess,
    ImportFailure,
    ImportSuccess,
    decode_forces,
    import_forces,
)
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def _compress(document: bytes) -> bytes:
    stream = zlib.compressobj(wbits=-15)
    return stream.compress(document) + stream.flush()


_DOCUMENT = (
    b'{"schemaVersion":"2.2.0","accelerationSequence":[{"x":"0","y":"0","z":"1"}],'
    b'"extension":"' + b"a" * 1024 + b'"}'
)


def test_manta_compressed_import_retains_original_and_matches_plain_recording() -> None:
    path = REAL_FIXTURE_DIRECTORY / "Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.zforces"
    original = path.read_bytes()
    modified = path.stat().st_mtime_ns
    assert len(original) == 91361
    assert sha256(original).hexdigest() == (
        "005ce708ec946bcf4dbe0163fc2fb23c629b65c1ed11706000c130855c4ba1e5"
    )
    compressed = import_forces(path)
    plain = import_forces(path.with_suffix(".forces"))
    assert isinstance(compressed, ImportSuccess)
    assert isinstance(plain, ImportSuccess)
    assert compressed.recording.source.root == plain.recording.source.root
    assert compressed.diagnostics == plain.diagnostics
    assert compressed.recording.metadata == plain.recording.metadata
    assert compressed.recording.indices == plain.recording.indices
    assert tuple(compressed.recording.motion.acceleration) == tuple(
        plain.recording.motion.acceleration,
    )
    assert compressed.recording.gps is not None and plain.recording.gps is not None
    assert compressed.recording.gps == plain.recording.gps
    assert len(compressed.recording.gps.entries) == 145
    assert compressed.recording.source.original_bytes == original
    assert compressed.source_sha256 == sha256(original).hexdigest()
    assert compressed.byte_count == len(original)
    assert compressed.recording.source.provenance.path == path
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == modified


def test_expanded_byte_limit_is_inclusive_and_extension_is_case_insensitive(
    export_directory: Path,
) -> None:
    path = export_directory / "recording.ZFORCES"
    data = _compress(_DOCUMENT)
    path.write_bytes(data)
    assert len(data) < len(_DOCUMENT)
    result = decode_forces(path, limits=replace(DEFAULT_LIMITS, max_bytes=len(_DOCUMENT)))
    assert isinstance(result, DecodeSuccess)
    assert result.source.original_bytes == data
    assert result.source.root is not None and result.source.root["extension"] == "a" * 1024
    too_small = decode_forces(path, limits=replace(DEFAULT_LIMITS, max_bytes=len(_DOCUMENT) - 1))
    assert isinstance(too_small, ImportFailure)
    assert too_small.diagnostics[0].code == "RESOURCE_LIMIT_EXCEEDED"
    assert too_small.source is None
    compressed_limit = decode_forces(path, limits=replace(DEFAULT_LIMITS, max_bytes=len(data) - 1))
    assert isinstance(compressed_limit, ImportFailure)
    assert compressed_limit.diagnostics[0].code == "RESOURCE_LIMIT_EXCEEDED"
    assert compressed_limit.source is None


@pytest.mark.parametrize(
    "data",
    [
        b"\x06",
        _compress(_DOCUMENT)[:-1],
        _compress(_DOCUMENT) + b"trailing",
        _compress(_DOCUMENT) + _compress(_DOCUMENT),
        zlib.compress(_DOCUMENT),
        zlib.compress(_DOCUMENT, wbits=31),
        _DOCUMENT,
    ],
    ids=["invalid", "truncated", "trailing", "concatenated", "zlib", "gzip", "plain-json"],
)
def test_invalid_compressed_streams_fail_with_original_provenance(
    export_directory: Path,
    data: bytes,
) -> None:
    path = export_directory / "invalid.zforces"
    path.write_bytes(data)
    result = import_forces(path)
    assert isinstance(result, ImportFailure)
    assert result.diagnostics[0].code == "INVALID_COMPRESSION"
    assert result.source is not None and result.source.original_bytes == data
    assert result.source_sha256 == sha256(data).hexdigest()
    assert result.source.root is None


@pytest.mark.parametrize(
    ("document", "code"),
    [
        (b"\xff", "INVALID_UTF8"),
        (b'{"schemaVersion":"2.2.0",}', "INVALID_JSON"),
        (b'{"schemaVersion":"2.2.0","schemaVersion":"2.2.0"}', "DUPLICATE_JSON_KEY"),
        (b'{"schemaVersion":"9.0.0"}', "UNSUPPORTED_SCHEMA_VERSION"),
        (b'{"schemaVersion":"2.2.0"}', "MISSING_REQUIRED_FIELD"),
        (b"", "EMPTY_INPUT"),
    ],
)
def test_decompressed_content_uses_existing_strict_validation(
    export_directory: Path,
    document: bytes,
    code: str,
) -> None:
    path = export_directory / "invalid.zforces"
    data = _compress(document)
    path.write_bytes(data)
    result = import_forces(path)
    assert isinstance(result, ImportFailure)
    assert result.diagnostics[0].code == code
    assert result.source is not None and result.source.original_bytes == data
