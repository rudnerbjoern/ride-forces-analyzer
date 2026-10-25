"""FR-004/005/006/027: immutable ownership and exact source representations."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from ride_forces_analyzer.domain import SourceEnvelope, SourceNumber, SourceValue


def test_source_envelope_copies_all_nested_inputs() -> None:
    raw = bytearray(b' {"unknown":{"items":[{"number":1.00,"text":"1.00"}]}}\r\n')
    original = bytes(raw)
    leaf: dict[str, object] = {"number": SourceNumber("1.00"), "text": "1.00"}
    items = [leaf]
    unknown = {"items": items}
    root: dict[str, object] = {"unknown": unknown}
    source = SourceEnvelope(raw, root)
    raw[:] = b"changed"
    leaf["text"] = "changed"
    items.clear()
    unknown.clear()
    root.clear()
    assert source.original_bytes == original
    assert source.provenance.byte_count == len(original)
    assert source.provenance.sha256 == sha256(original).hexdigest()
    assert source.root is not None
    branch = source.root["unknown"]
    assert isinstance(branch, Mapping)
    sequence = branch["items"]
    assert isinstance(sequence, tuple) and len(sequence) == 1
    nested = sequence[0]
    assert isinstance(nested, Mapping)
    assert nested["number"] == SourceNumber("1.00")
    assert nested["text"] == "1.00"
    with pytest.raises(TypeError):
        cast(dict[str, SourceValue], nested)["text"] = "changed"
    with pytest.raises(FrozenInstanceError):
        setattr(source, "original_bytes", b"changed")


def test_source_scalars_keep_number_string_boolean_null_and_absence_distinct() -> None:
    source = SourceEnvelope(
        b'{"number":0,"text":"0","boolean":false,"null":null,"array":[]}',
        {"number": SourceNumber("0"), "text": "0", "boolean": False, "null": None, "array": []},
    )
    assert source.root is not None
    assert isinstance(source.root["number"], SourceNumber)
    assert source.root["text"] == "0"
    assert source.root["boolean"] is False
    assert source.root["null"] is None
    assert source.root["array"] == ()
    assert "absent" not in source.root


@pytest.mark.parametrize("token", ["0", "-0", "1.000", "1e+2", "0.12345678901234567890123456789"])
def test_source_number_keeps_exact_lexeme_and_precision(token: str) -> None:
    number = SourceNumber(token)
    assert number.token == token
    assert number.value == Decimal(token)
    with pytest.raises(FrozenInstanceError):
        setattr(number, "token", "changed")


def test_number_equality_retains_spelling() -> None:
    assert SourceNumber("1") != SourceNumber("1.0")
    assert SourceNumber("-0").value.is_signed()


@pytest.mark.parametrize("token", ["NaN", "Infinity", "01", "+1", "1.", " 1", "1\n"])
def test_source_number_rejects_non_json_tokens(token: str) -> None:
    with pytest.raises(ValueError):
        SourceNumber(token)


@pytest.mark.parametrize("value", [1, 1.0, float("nan"), bytearray(b"x"), {1: "x"}, object()])
def test_source_tree_rejects_unsupported_or_lossy_values(value: object) -> None:
    with pytest.raises(TypeError):
        SourceEnvelope(b"retained", {"value": value})


def test_source_tree_rejects_cycles_but_copies_repeated_branches() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="acyclic"):
        SourceEnvelope(b"retained", {"cycle": cyclic})
    shared = {"value": "original"}
    source = SourceEnvelope(b"retained", {"a": shared, "b": shared})
    shared.clear()
    assert source.root is not None and source.root["a"] == source.root["b"]


def test_source_path_is_provenance_only_without_file_io() -> None:
    path = Path("a-path-that-does-not-exist.forces")
    source = SourceEnvelope(b"raw input bytes", source_path=path)
    assert source.provenance.path == path
    assert source.original_bytes == b"raw input bytes"
    assert source.root is None
    assert "raw input bytes" not in repr(source)


def test_source_envelope_equality_is_deterministic_and_byte_sensitive() -> None:
    first = SourceEnvelope(b'{"n":1.00}', {"n": SourceNumber("1.00")})
    assert first == SourceEnvelope(b'{"n":1.00}', {"n": SourceNumber("1.00")})
    assert first != SourceEnvelope(b' {"n":1.00}', {"n": SourceNumber("1.00")})


def test_valid_numeric_token_with_unsupported_decimal_exponent_is_rejected() -> None:
    from decimal import InvalidOperation, localcontext

    with localcontext() as context:
        context.traps[InvalidOperation] = False
        with pytest.raises(ValueError, match="finite decimal value"):
            SourceNumber("1e" + "9" * 30)


def test_invalid_provenance_and_envelope_types_cannot_lose_source_identity() -> None:
    from ride_forces_analyzer.domain.source import SourceProvenance

    for count in (-1, True):
        with pytest.raises(ValueError, match="nonnegative integer"):
            SourceProvenance(count, "a" * 64)
    with pytest.raises(TypeError, match="Source path must be a Path"):
        SourceProvenance(1, "a" * 64, cast(Path, "ride.forces"))
    with pytest.raises(TypeError, match="Source bytes must be bytes"):
        SourceEnvelope(cast(bytes, "retained"))
    with pytest.raises(TypeError, match="Source root must be an object mapping"):
        SourceEnvelope(b"retained", cast(Mapping[str, object], []))
