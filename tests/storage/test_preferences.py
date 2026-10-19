"""Local folder preferences survive restart and tolerate missing storage."""

# cspell:words executemany

from pathlib import Path
from tempfile import TemporaryDirectory
from collections.abc import Callable
from typing import cast

import pytest

from ride_forces_analyzer.storage.preferences import Preferences


@pytest.mark.parametrize(
    ("method", "invalid"),
    [
        ("remember_language", "fr"),
        ("remember_language", b"de"),
        ("remember_language", None),
        ("remember_appearance", "blue"),
        ("remember_appearance", b"dark"),
        ("remember_automatic_updates", "false"),
        ("remember_automatic_updates", "true"),
        ("remember_automatic_updates", 0),
        ("remember_automatic_updates", 1),
        ("remember_automatic_updates", None),
        ("remember_export_fps", True),
        ("remember_export_fps", 50.0),
        ("remember_export_fps", "50"),
        ("remember_export_fps", 0),
        ("remember_update_check", "100000"),
        ("remember_update_check", True),
        ("remember_update_check", float("nan")),
        ("remember_update_check", float("inf")),
        ("remember_update_check", -float("inf")),
        ("skip_update", 123),
        ("skip_update", b"v0.2.0"),
        ("skip_update", None),
        ("remember_recording", "ride.forces"),
        ("remember_recording", None),
        ("remember_export", "ride.mov"),
        ("remember_export", 123),
        ("language", "fr"),
        ("update_check_due", "100000"),
        ("update_check_due", float("nan")),
    ],
)
def test_invalid_preference_inputs_are_rejected_without_changing_storage(
    method: str,
    invalid: object,
) -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        database = Path(temporary) / "preferences.sqlite3"
        preferences = Preferences(database)
        preferences.remember_language("de")
        before = database.read_bytes()
        call = cast(Callable[[object], object], getattr(preferences, method))
        with pytest.raises(ValueError):
            call(invalid)
        assert database.read_bytes() == before
        assert Preferences(database).language() == "de"


def test_database_path_requires_a_path_object() -> None:
    with pytest.raises(ValueError):
        Preferences(cast(Path, "preferences.sqlite3"))


def test_invalid_stored_preferences_keep_safe_defaults() -> None:
    from contextlib import closing
    import sqlite3

    with TemporaryDirectory(dir=".tmp") as temporary:
        database = Path(temporary) / "preferences.sqlite3"
        preferences = Preferences(database)
        preferences.remember_language("de")
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.executemany(
                "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
                [
                    ("language", "fr"),
                    ("appearance", "blue"),
                    ("automatic_updates", "1"),
                    ("export_fps", "NaN"),
                    ("update_checked_at", "invalid"),
                ],
            )
        assert preferences.language() == "en"
        assert preferences.language("de") == "de"
        assert preferences.appearance() == "system"
        assert preferences.export_fps() == 50
        assert not preferences.automatic_updates()
        preferences.remember_automatic_updates(True)
        assert preferences.update_check_due(100000)
        preferences.remember_automatic_updates(False)
        assert not Preferences(database).automatic_updates()


def test_language_and_appearance_survive_restart_with_safe_defaults() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        database = Path(temporary) / "preferences.sqlite3"
        preferences = Preferences(database)
        assert preferences.language() == "en" and preferences.appearance() == "system"
        preferences.remember_language("de")
        preferences.remember_appearance("light")
        restored = Preferences(database)
        assert restored.language() == "de" and restored.appearance() == "light"


def test_folder_survives_restart_and_missing_directory_falls_back() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        root = Path(temporary)
        folder = root / "rides"
        folder.mkdir()
        database = root / "preferences.sqlite3"
        preferences = Preferences(database)
        assert preferences.recording_directory() == ""
        preferences.remember_recording(folder / "ride.forces")
        assert Preferences(database).recording_directory() == str(folder.resolve())
        folder.rmdir()
        assert Preferences(database).recording_directory() == ""


def test_corrupt_or_blocked_preferences_do_not_block_imports() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        root = Path(temporary)
        database = root / "preferences.sqlite3"
        database.write_bytes(b"invalid database")
        preferences = Preferences(database)
        assert preferences.recording_directory() == ""
        preferences.remember_recording(root / "ride.forces")
        assert database.read_bytes() == b"invalid database"
        blocked = Preferences(database / "preferences.sqlite3")
        blocked.remember_recording(root / "ride.forces")
        assert blocked.recording_directory() == ""


def test_export_folder_is_persistent_and_independent_of_recording_folder() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        root = Path(temporary)
        exports = root / "videos"
        exports.mkdir()
        database = root / "preferences.sqlite3"
        preferences = Preferences(database)
        preferences.remember_recording(root / "ride.forces")
        preferences.remember_export(exports / "ride.mov")
        restored = Preferences(database)
        assert restored.export_directory() == str(exports.resolve())
        assert restored.recording_directory() == str(root.resolve())
        exports.rmdir()
        assert restored.export_directory() == ""


def test_default_export_rate_survives_restart_and_invalid_storage_falls_back() -> None:
    from contextlib import closing
    import sqlite3

    with TemporaryDirectory(dir=".tmp") as temporary:
        database = Path(temporary) / "preferences.sqlite3"
        preferences = Preferences(database)
        assert preferences.export_fps() == 50
        preferences.remember_language("de")
        preferences.remember_export_fps("60000/1001")
        restored = Preferences(database)
        assert restored.export_fps() == "60000/1001" and restored.language() == "de"
        restored.remember_export_fps(60)
        assert Preferences(database).export_fps() == 60
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("UPDATE preferences SET value = 'invalid' WHERE key = 'export_fps'")
        assert Preferences(database).export_fps() == 50
