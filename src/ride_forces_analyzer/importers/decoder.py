"""Stage 2: bounded read-only inputs and strict schema-aware JSON decoding.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words fstat decompressobj wbits

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import InvalidOperation
import json
import os
from pathlib import Path, PureWindowsPath
import stat
from typing import Literal, cast
import zlib

from ride_forces_analyzer.domain import RecordingFormat, SourceEnvelope, SourceNumber, SourceValue
from ride_forces_analyzer.validation.checks import has_type

from ._json_preflight import DecodeProblem, preflight
from .diagnostics import ImportDiagnostic, Severity
from .limits import DEFAULT_LIMITS, ImportLimits
from .result import ImportFailure


@dataclass(frozen=True, slots=True)
class DecodeSuccess:
    """A supported immutable source object, not a complete canonical recording.

    Attributes:
        source: Retained input identity or image; its original representation remains
            owned.
        source_format: Admitted recording profile, kept separate from scientific
            qualification.
        success: Discriminator identifying whether the import stage succeeded.
        diagnostics: Structured diagnostics retaining stable codes and source locations.
    """

    source: SourceEnvelope = field(repr=False)
    source_format: RecordingFormat = RecordingFormat.RIDE_FORCES
    success: Literal[True] = field(default=True, init=False)
    diagnostics: tuple[ImportDiagnostic, ...] = field(default=(), init=False)

    @property
    def schema_version(self) -> str | None:
        """Return the retained declared or admitted source schema version.

        Returns:
            The retained declared or admitted source schema version.
        """
        version = self.source.root.get("schemaVersion") if self.source.root is not None else None
        return version if isinstance(version, str) else None

    @property
    def byte_count(self) -> int:
        """Return the original supplied source byte count.

        Returns:
            The original supplied source byte count.
        """
        return self.source.provenance.byte_count

    @property
    def source_sha256(self) -> str:
        """Return the SHA-256 identity of the original supplied source bytes.

        Returns:
            The sha-256 identity of the original supplied source bytes.
        """
        return self.source.provenance.sha256


type DecodeResult = DecodeSuccess | ImportFailure


def _failure(
    code: str,
    message: str,
    *,
    source: SourceEnvelope | None = None,
) -> ImportFailure:
    return ImportFailure([ImportDiagnostic(code, Severity.ERROR, "", message)], source=source)


def _members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DecodeProblem("DUPLICATE_JSON_KEY", (), "Duplicate object member")
        result[key] = value
    return result


def _constant(_token: str) -> object:
    raise DecodeProblem("NON_JSON_NUMBER", (), "Non-JSON numeric constant")


def _decode_tree(text: str) -> object:
    return json.loads(
        text,
        parse_int=SourceNumber,
        parse_float=SourceNumber,
        parse_constant=_constant,
        object_pairs_hook=_members,
    )


def _validate_core_shape(source: SourceEnvelope) -> None:
    root = source.root
    assert root is not None
    for key in ("accelerationSequence",):
        if key not in root:
            raise DecodeProblem("MISSING_REQUIRED_FIELD", (key,), "Required core field is absent")
    acceleration = root["accelerationSequence"]
    if not isinstance(acceleration, tuple) or not acceleration:
        raise DecodeProblem(
            "INVALID_REQUIRED_FIELD",
            ("accelerationSequence",),
            "Acceleration must be a nonempty array",
        )
    for index, vector in enumerate(acceleration):
        if not isinstance(vector, Mapping):
            raise DecodeProblem(
                "INVALID_REQUIRED_FIELD",
                ("accelerationSequence", index),
                "Motion sample must be an object",
            )
        for axis in ("x", "y", "z"):
            if axis not in vector:
                raise DecodeProblem(
                    "MISSING_REQUIRED_FIELD",
                    ("accelerationSequence", index, axis),
                    "Required component is absent",
                )
            component: SourceValue = vector[axis]
            if not isinstance(component, (str, SourceNumber)):
                raise DecodeProblem(
                    "INVALID_REQUIRED_FIELD",
                    ("accelerationSequence", index, axis),
                    "Component must be a string or JSON number",
                )
    for key in ("startIndex", "endIndex"):
        if key not in root:
            continue
        value = root[key]
        if not isinstance(value, SourceNumber) or value.value != value.value.to_integral_value():
            raise DecodeProblem(
                "INVALID_REQUIRED_FIELD",
                (key,),
                "Index must be an integer JSON number",
            )
    # Component interpretation, rates, bounds and scientific meaning belong to Stage 3.


def _schema_220(source: SourceEnvelope) -> DecodeSuccess:
    _validate_core_shape(source)
    return DecodeSuccess(source)


def _rfdb_shape(root: Mapping[str, SourceValue]) -> bool:
    """Recognize the observed unversioned RFDB layout, not arbitrary missing versions."""
    return {
        "accelerationSequence",
        "sampleRate",
        "startIndex",
        "endIndex",
        "xCalibrationVector",
        "yCalibrationVector",
        "zCalibrationVector",
    }.issubset(root) and not {
        "verticalDirectionVector",
        "lateralDirectionVector",
        "longitudinalDirectionVector",
    }.intersection(root)


_SCHEMAS = {"2.2.0": _schema_220}


def _decode(data: bytes, limits: ImportLimits, path: Path | None = None) -> DecodeResult:
    if len(data) > limits.max_bytes:
        return _failure("RESOURCE_LIMIT_EXCEEDED", "Resource budget exceeded: max_bytes")
    source = SourceEnvelope(data, source_path=path)
    if not data:
        return _failure("EMPTY_INPUT", "Source input is empty", source=source)
    document = data
    if path is not None and path.suffix.lower() == ".zforces":
        try:
            stream = zlib.decompressobj(wbits=-15)
            document = stream.decompress(data, limits.max_bytes + 1)
        except zlib.error:
            return _failure("INVALID_COMPRESSION", "Invalid compressed recording", source=source)
        if len(document) > limits.max_bytes:
            return _failure("RESOURCE_LIMIT_EXCEEDED", "Resource budget exceeded: max_bytes")
        if not stream.eof or stream.unused_data:
            return _failure("INVALID_COMPRESSION", "Invalid compressed recording", source=source)
    try:
        text = document.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        return _failure("INVALID_UTF8", "Source must use valid UTF-8", source=source)
    if not text.strip(" \t\r\n"):
        return _failure("EMPTY_INPUT", "Source contains no JSON document", source=source)
    version: str | None = None
    try:
        preflight(text, limits)
        tree = _decode_tree(text)
        if not isinstance(tree, Mapping):
            raise DecodeProblem("INVALID_ROOT", (), "JSON root must be an object")
        source = SourceEnvelope(data, cast(Mapping[str, object], tree), source_path=path)
        assert source.root is not None
        if "schemaVersion" not in source.root and _rfdb_shape(source.root):
            _validate_core_shape(source)
            return DecodeSuccess(source, RecordingFormat.RFDB)
        raw_version = source.root.get("schemaVersion")
        if not isinstance(raw_version, str) or not raw_version:
            raise DecodeProblem(
                "INVALID_SCHEMA_VERSION",
                ("schemaVersion",),
                "Schema version must be a nonempty string",
            )
        version = raw_version
        adapter = _SCHEMAS.get(version)
        if adapter is None:
            raise DecodeProblem(
                "UNSUPPORTED_SCHEMA_VERSION",
                ("schemaVersion",),
                "Schema version is unsupported",
            )
        return adapter(source)
    except DecodeProblem as problem:
        return ImportFailure([problem.diagnostic], source=source, schema_version=version)
    except json.JSONDecodeError, ValueError, InvalidOperation:
        return _failure("INVALID_JSON", "Invalid JSON document", source=source)
    except RecursionError:
        return _failure(
            "RESOURCE_LIMIT_EXCEEDED",
            "Decoder runtime nesting budget exceeded",
            source=source,
        )


def decode_forces_bytes(data: bytes, *, limits: ImportLimits = DEFAULT_LIMITS) -> DecodeResult:
    """Decode exact immutable bytes without any path access or motion conversion.

    Args:
        data: Input data in the representation declared by the parameter type.
        limits: Resource limits applied to the operation.

    Returns:
        Decoded source envelope or structured failure with bounded diagnostics.

    Raises:
        ValueError: limits must be an ImportLimits instance.
        TypeError: data must be immutable bytes.
    """
    if not has_type(limits, ImportLimits):
        raise ValueError("limits must be an ImportLimits instance")
    if not has_type(data, bytes):
        raise TypeError("data must be immutable bytes")
    return _decode(data, limits)


def decode_forces(path: Path, *, limits: ImportLimits = DEFAULT_LIMITS) -> DecodeResult:
    """Read a local regular file in binary mode with at most max_bytes + 1 bytes.

    Args:
        path: Filesystem path read or written by this operation.
        limits: Resource limits applied to the operation.

    Returns:
        Decoded source envelope or structured file/decode failure.

    Raises:
        ValueError: limits must be an ImportLimits instance.
        TypeError: path must be a Path.
    """
    if not has_type(limits, ImportLimits):
        raise ValueError("limits must be an ImportLimits instance")
    if not has_type(path, Path):
        raise TypeError("path must be a Path")
    if PureWindowsPath(str(path)).drive.startswith("\\\\"):
        return _failure("INVALID_SOURCE_PATH", "Network and device paths are unsupported")
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            return _failure("INVALID_SOURCE_PATH", "Source path must be a regular file")
        with path.open("rb", buffering=0) as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return _failure("INVALID_SOURCE_PATH", "Opened source must be a regular file")
            remaining = limits.max_bytes + 1
            chunks: list[bytes] = []
            while remaining:
                chunk = stream.read(min(remaining, 65_536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
    except FileNotFoundError:
        return _failure("SOURCE_NOT_FOUND", "Source file was not found")
    except OSError:
        return _failure("SOURCE_UNREADABLE", "Unable to read source file")
    except ValueError:
        return _failure("INVALID_SOURCE_PATH", "Source path is invalid")
    return _decode(data, limits, path)
