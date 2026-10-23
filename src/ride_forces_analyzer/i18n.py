"""Offline presentation text; source data, identifiers and clocks stay unchanged.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from typing import Literal

from .translations_de import DIAGNOSTIC_GERMAN, GERMAN
from .translations_fr import DIAGNOSTIC_FRENCH, FRENCH

Language = Literal["en", "de", "fr"]


@dataclass(frozen=True, slots=True)
class LanguageDefinition:
    """Presentation settings shared by UI, persistence and offline rendering."""

    name: str
    locale: str
    decimal_separator: str
    group_separator: str
    catalog: dict[str, str]
    diagnostics: dict[str, str]


LANGUAGES: dict[Language, LanguageDefinition] = {
    "en": LanguageDefinition("English", "en_US", ".", ",", {}, {}),
    "de": LanguageDefinition("Deutsch", "de_DE", ",", ".", GERMAN, DIAGNOSTIC_GERMAN),
    "fr": LanguageDefinition("Français", "fr_FR", ",", "\u202f", FRENCH, DIAGNOSTIC_FRENCH),
}
LANGUAGE_CHOICES = tuple(LANGUAGES)
_language: Language = "en"


def get_language() -> Language:
    return _language


def set_language(language: Language) -> None:
    global _language
    if language not in LANGUAGES:
        raise ValueError("Unsupported application language")
    _language = language


class _Number:
    def __init__(self, value: int | float, language: Language) -> None:
        self.value = value
        self.definition = LANGUAGES[language]

    def __format__(self, specification: str) -> str:
        return format(self.value, specification).translate(
            str.maketrans(
                ".,",
                self.definition.decimal_separator + self.definition.group_separator,
            ),
        )


def _render(source: str, values: tuple[object, ...], language: Language) -> str:
    template = LANGUAGES[language].catalog.get(source, source)
    arguments = tuple(
        _Number(value, language)
        if language != "en" and type(value) in (int, float) and isinstance(value, (int, float))
        else value
        for value in values
    )
    return template.format(*arguments) if values else template


class Text(str):
    """Retain a template and opaque values for safe, repeatable UI retranslation."""

    source: str
    values: tuple[object, ...]
    language: Language | None

    def __new__(
        cls,
        source: str,
        values: tuple[object, ...],
        language: Language | None = None,
    ) -> "Text":
        instance = super().__new__(cls, _render(source, values, language or get_language()))
        instance.source, instance.values, instance.language = source, values, language
        return instance

    def __str__(self) -> str:
        return _render(self.source, self.values, self.language or get_language())

    def __format__(self, specification: str) -> str:
        return format(str(self), specification)


def tr(source: str, *values: object, language: Language | None = None) -> Text:
    return Text(source, values, language)


def diagnostic_message(code: str, original: str) -> str:
    return LANGUAGES[get_language()].diagnostics.get(code, original)
