"""The OS display-language fallback never overrides a saved user choice."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui import translation


@pytest.mark.parametrize(
    "languages,expected",
    [
        (["de-DE"], "de"),
        (["de-CH"], "de"),
        (["en-US", "de-DE"], "en"),
        (["fr-FR"], "en"),
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
    assert translation.system_ui_language() == expected


def test_saved_language_takes_priority_over_os_fallback() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        preferences = Preferences(Path(temporary) / "preferences.sqlite3")
        assert preferences.language("de") == "de"
        preferences.remember_language("en")
        assert preferences.language("de") == "en"
        preferences.remember_language("de")
        assert preferences.language("en") == "de"
