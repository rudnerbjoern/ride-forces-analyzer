"""Offline presentation text; source data, identifiers and clocks stay unchanged.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Literal

from .translations import DIAGNOSTIC_GERMAN, GERMAN

Language = Literal["en", "de"]
_language: Language = "en"


def get_language() -> Language:
    return _language


def set_language(language: Language) -> None:
    global _language
    if language not in ("en", "de"):
        raise ValueError("Unsupported application language")
    _language = language


class _Number:
    def __init__(self, value: int | float) -> None:
        self.value = value

    def __format__(self, specification: str) -> str:
        return format(self.value, specification).translate(str.maketrans(".,", ",."))


def _render(source: str, values: tuple[object, ...], language: Language) -> str:
    template = GERMAN.get(source, source) if language == "de" else source
    arguments = tuple(
        _Number(value)
        if language == "de" and type(value) in (int, float) and isinstance(value, (int, float))
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
    return DIAGNOSTIC_GERMAN.get(code, original) if get_language() == "de" else original
