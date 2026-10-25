"""Keep shared validation rejection contracts stable across their consumers."""

import pytest

from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.validation.checks import (
    text_values,
    validate_diagnostic_code,
    validate_enum,
    validate_sample_range,
    validate_sha256,
    validate_text,
)


def test_blank_text_retains_field_specific_value_error() -> None:
    with pytest.raises(ValueError, match="^Profile must be nonempty text$"):
        validate_text(" ", "Profile")


def test_text_sequence_rejects_scalar_strings() -> None:
    with pytest.raises(TypeError, match="^Evidence requires a sequence of text values$"):
        text_values("evidence", "Evidence")


def test_enum_check_rejects_string_without_coercion() -> None:
    with pytest.raises(TypeError, match="^Expected Language$"):
        validate_enum("en", Language)


def test_digest_validation_preserves_original_string() -> None:
    digest = "0123456789abcdef" * 4
    assert validate_sha256(digest, "Invalid source") is digest


@pytest.mark.parametrize(
    "value",
    [None, 123, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n"],
)
def test_digest_validation_rejects_invalid_values_with_caller_message(value: object) -> None:
    with pytest.raises(ValueError, match="^Invalid source$"):
        validate_sha256(value, "Invalid source")


@pytest.mark.parametrize("code", ["A", "CODE_123"])
def test_diagnostic_code_accepts_stable_identifiers(code: str) -> None:
    validate_diagnostic_code(code)


@pytest.mark.parametrize("code", [None, "", "code", "1CODE", "_CODE", "CODE-1", "CODE\n", "Ä_CODE"])
def test_diagnostic_code_rejects_invalid_identifiers(code: object) -> None:
    with pytest.raises(ValueError, match="^Diagnostic code must be a stable uppercase identifier$"):
        validate_diagnostic_code(code)


@pytest.mark.parametrize(("first", "last", "count"), [(0, 0, 1), (0, 3, 4), (3, 3, 4)])
def test_sample_range_accepts_inclusive_boundaries(first: int, last: int, count: int) -> None:
    validate_sample_range(first, last, count, "Invalid interval")


@pytest.mark.parametrize(
    ("first", "last"),
    [(-1, 0), (2, 1), (0, 4), (False, 1), (0, True), (0.0, 1), (0, "1")],
)
def test_sample_range_preserves_default_value_error(first: int, last: int) -> None:
    with pytest.raises(ValueError, match="^Invalid interval$"):
        validate_sample_range(first, last, 4, "Invalid interval")


def test_sample_range_rejects_empty_source() -> None:
    with pytest.raises(ValueError, match="^Invalid interval$"):
        validate_sample_range(0, 0, 0, "Invalid interval")


@pytest.mark.parametrize(("first", "last"), [(True, 1), (0, False), (0.0, 1), (0, "1")])
def test_sample_range_preserves_separate_export_type_error(first: int, last: int) -> None:
    with pytest.raises(TypeError, match="^Integer indices required$"):
        validate_sample_range(
            first,
            last,
            4,
            "Invalid interval",
            type_message="Integer indices required",
        )
