import pytest
from pydantic import ValidationError

from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.i18n import Language


def test_default_settings() -> None:
    settings = AppSettings()
    assert settings.window_title == "Ride Forces Analyzer"
    assert (settings.window_width, settings.window_height) == (1280, 820)
    assert settings.language is Language.ENGLISH


def test_custom_settings_round_trip() -> None:
    settings = AppSettings(window_title="Custom window", window_width=800, window_height=500)
    assert AppSettings.model_validate_json(settings.model_dump_json()) == settings


@pytest.mark.parametrize("language", list(Language))
def test_language_members_preserve_json_codes_and_strict_python_validation(
    language: Language,
) -> None:
    settings = AppSettings(language=language)
    restored = AppSettings.model_validate_json(settings.model_dump_json())
    assert restored.language is language
    assert (
        AppSettings.model_validate_json(f'{{"language":"{language.value}"}}').language is language
    )
    assert settings.model_dump(mode="json")["language"] == language.value
    with pytest.raises(ValidationError):
        AppSettings.model_validate({"language": language.value})


@pytest.mark.parametrize("field", ["window_width", "window_height"])
@pytest.mark.parametrize(
    ("value", "error_type"),
    [
        (0, "greater_than"),
        (-1, "greater_than"),
        ("900", "int_type"),
        (900.0, "int_type"),
        (True, "int_type"),
        (None, "int_type"),
        (16_777_216, "less_than_equal"),
        (2**31, "less_than_equal"),
    ],
)
def test_invalid_dimensions(field: str, value: object, error_type: str) -> None:
    with pytest.raises(ValidationError) as error:
        AppSettings.model_validate({field: value})
    details = error.value.errors()
    assert len(details) == 1
    assert details[0]["loc"] == (field,)
    assert details[0]["type"] == error_type


@pytest.mark.parametrize("dimension", [1, 16_777_215])
def test_window_dimension_boundaries(dimension: int) -> None:
    settings = AppSettings(window_width=dimension, window_height=dimension)
    assert (settings.window_width, settings.window_height) == (dimension, dimension)


@pytest.mark.parametrize(("value", "error_type"), [("", "string_too_short"), (42, "string_type")])
def test_invalid_title(value: object, error_type: str) -> None:
    with pytest.raises(ValidationError) as error:
        AppSettings.model_validate({"window_title": value})
    assert error.value.errors()[0]["type"] == error_type


def test_unknown_settings_are_rejected() -> None:
    with pytest.raises(ValidationError) as error:
        AppSettings.model_validate({"unknown_setting": 1})
    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("field", "value"),
    [("window_title", "Changed window"), ("window_width", 800), ("window_height", 500)],
)
def test_settings_are_immutable(field: str, value: object) -> None:
    settings = AppSettings()
    original = settings.model_dump()
    with pytest.raises(ValidationError) as error:
        setattr(settings, field, value)
    assert error.value.errors()[0]["type"] == "frozen_instance"
    assert settings.model_dump() == original
