"""The OS display-language fallback never overrides a saved user choice."""

from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
import sqlite3

import pytest

from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.presentation import translation


@pytest.mark.parametrize(
    "languages,expected",
    [
        (["de-DE"], "de"),
        (["de-CH"], "de"),
        (["en-US", "de-DE"], "en"),
        (["fr-FR"], "fr"),
        (["fr_CA"], "fr"),
        (["es-ES", "fr-FR"], "en"),
        ([], "en"),
    ],
)
def test_system_language_uses_preferred_display_language(
    monkeypatch: pytest.MonkeyPatch,
    languages: list[str],
    expected: str,
) -> None:
    class SystemLocale:
        def uiLanguages(self) -> list[str]:
            return languages

    class Locale:
        @staticmethod
        def system() -> SystemLocale:
            return SystemLocale()

    monkeypatch.setattr(translation, "QLocale", Locale)
    assert translation.system_ui_language() is Language(expected)


def test_saved_language_takes_priority_over_os_fallback() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        preferences = Preferences(Path(temporary) / "preferences.sqlite3")
        assert preferences.language(Language.GERMAN) == "de"
        preferences.remember_language(Language.ENGLISH)
        assert preferences.language(Language.GERMAN) == "en"
        preferences.remember_language(Language.GERMAN)
        assert preferences.language(Language.ENGLISH) == "de"
        preferences.remember_language(Language.FRENCH)
        assert Preferences(preferences.path).language(Language.ENGLISH) is Language.FRENCH
        with closing(sqlite3.connect(preferences.path)) as connection, connection:
            assert connection.execute(
                "SELECT value FROM preferences WHERE key = 'language'",
            ).fetchone() == ("fr",)
            connection.execute("UPDATE preferences SET value = 'de' WHERE key = 'language'")
        assert Preferences(preferences.path).language() is Language.GERMAN
