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
    """Presentation settings shared by UI, persistence and offline rendering.

    Attributes:
        name: Stable identifier or displayed name for this model or view.
        locale: Locale identifier used for text and number formatting.
        decimal_separator: Character separating integer and fractional digits.
        group_separator: Character separating digit groups.
        catalog: Translation messages for the language.
        diagnostics: Structured diagnostics retaining stable codes and source locations.
    """

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
    """Return the active interface language.

    Returns:
        The active interface language.
    """
    return _language


def set_language(language: Language) -> None:
    """Select a registered interface language.

    Args:
        language: Registered language used to translate presentation text and numbers.

    Returns:
        None.

    Raises:
        ValueError: Unsupported application language.
    """
    global _language
    if language not in LANGUAGES:
        raise ValueError("Unsupported application language")
    _language = language


class _Number:
    """Number contract and owned data.

    Attributes:
        value: Candidate value to validate, format or store.
        definition: Language definition used for numeric formatting.
    """

    def __init__(self, value: int | float, language: Language) -> None:
        """Initialize number and its owned state.

        Args:
            value: Candidate value to validate, format or store.
            language: Registered language used to translate presentation text and numbers.

        Returns:
            None.
        """
        self.value = value
        self.definition = LANGUAGES[language]

    def __format__(self, specification: str) -> str:
        """Format the retained value using the requested presentation specification.

        Args:
            specification: Format or analysis specification to apply.

        Returns:
            Text formatted using the supplied presentation specification.
        """
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
    """Retain a template and opaque values for safe, repeatable UI retranslation.

    Attributes:
        source: Retained input identity or image; its original representation remains
            owned.
        values: Retained or prepared values in the owning object's declared units.
        language: Registered language used to translate presentation text and numbers.
    """

    source: str
    values: tuple[object, ...]
    language: Language | None

    def __new__(
        cls,
        source: str,
        values: tuple[object, ...],
        language: Language | None = None,
    ) -> "Text":
        """Construct the immutable value and retain its formatting context.

        Args:
            source: Untranslated source message template.
            values: Values to format, validate or add in their supplied order.
            language: Registered language used to translate presentation text and numbers.

        Returns:
            New immutable value retaining its formatting context.
        """
        instance = super().__new__(cls, _render(source, values, language or get_language()))
        instance.source, instance.values, instance.language = source, values, language
        return instance

    def __str__(self) -> str:
        """Return the current textual representation.

        Returns:
            The current textual representation.
        """
        return _render(self.source, self.values, self.language or get_language())

    def __format__(self, specification: str) -> str:
        """Format the retained value using the requested presentation specification.

        Args:
            specification: Format or analysis specification to apply.

        Returns:
            Text formatted using the supplied presentation specification.
        """
        return format(str(self), specification)


def tr(source: str, *values: object, language: Language | None = None) -> Text:
    """Bind a message template and opaque formatting values to an interface language.

    Args:
        source: Untranslated source message template.
        language: Registered language used to translate presentation text and numbers.
        *values: Opaque formatting values substituted when the text is rendered.

    Returns:
        Deferred localized text with opaque formatting values retained.
    """
    return Text(source, values, language)


def diagnostic_message(code: str, original: str) -> str:
    """Return a localized diagnostic explanation, preserving the original fallback.

    Args:
        code: Stable diagnostic code used to select its localized explanation.
        original: Original diagnostic text retained as the untranslated fallback.

    Returns:
        A localized diagnostic explanation, preserving the original fallback.
    """
    return LANGUAGES[get_language()].diagnostics.get(code, original)
