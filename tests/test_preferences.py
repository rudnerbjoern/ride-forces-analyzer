"""Local folder preferences survive restart and tolerate missing storage."""

from pathlib import Path
from tempfile import TemporaryDirectory

from ride_forces_analyzer.storage.preferences import Preferences


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
