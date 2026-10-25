"""Local folder preferences survive restart and tolerate missing storage."""

from ride_forces_analyzer.rendering.model import StandardFrameRate

# cspell:words executemany

from pathlib import Path
from tempfile import TemporaryDirectory
from collections.abc import Callable
from typing import cast

import pytest

from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.storage.preferences import Appearance, Preferences


def test_render_jobs_survive_restart_and_fit_the_current_computer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.runtime import cpu_resources

    monkeypatch.setattr(cpu_resources, "render_job_limit", lambda: 24)
    path = tmp_path / "preferences.sqlite3"
    preferences = Preferences(path)
    assert preferences.render_jobs() == 1
    preferences.remember_render_jobs(18)
    assert Preferences(path).render_jobs() == 18
    monkeypatch.setattr(cpu_resources, "render_job_limit", lambda: 4)
    assert Preferences(path).render_jobs() == 4
    preferences.remember_render_jobs(100)
    monkeypatch.setattr(cpu_resources, "render_job_limit", lambda: 24)
    assert Preferences(path).render_jobs() == 4


def test_recording_markers_survive_restart_are_content_bound_and_can_be_reset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "preferences.sqlite3"
    preferences = Preferences(path)
    source, other = "a" * 64, "b" * 64
    assert preferences.recording_bounds(source) is None
    assert preferences.remember_recording_bounds(source, (3, 9))
    assert Preferences(path).recording_bounds(source) == (3, 9)
    assert preferences.recording_bounds(other) is None
    with pytest.raises(ValueError):
        preferences.remember_recording_bounds(source, (9, 3))
    assert preferences.recording_bounds(source) == (3, 9)
    assert preferences.remember_recording_bounds(source, None)
    assert Preferences(path).recording_bounds(source) is None


def test_recording_markers_tolerate_unavailable_storage(tmp_path: Path) -> None:
    preferences = Preferences(tmp_path)
    assert preferences.recording_bounds("a" * 64) is None
    assert not preferences.remember_recording_bounds("a" * 64, (1, 2))


@pytest.mark.parametrize(
    ("method", "invalid"),
    [
        ("remember_language", "es"),
        ("remember_language", "de"),
        ("remember_language", b"de"),
        ("remember_language", None),
        ("remember_appearance", "blue"),
        ("remember_appearance", "dark"),
        ("remember_appearance", b"dark"),
        ("remember_automatic_updates", "false"),
        ("remember_automatic_updates", "true"),
        ("remember_automatic_updates", 0),
        ("remember_automatic_updates", 1),
        ("remember_automatic_updates", None),
        ("remember_restore_last_file", "true"),
        ("remember_restore_last_file", 1),
        ("remember_restore_last_file", None),
        ("remember_export_fps", True),
        ("remember_export_fps", 50.0),
        ("remember_export_fps", "50"),
        ("remember_export_fps", 23.976),
        ("remember_export_fps", "23.976"),
        ("remember_export_fps", 0),
        ("remember_render_jobs", True),
        ("remember_render_jobs", 2.0),
        ("remember_render_jobs", "2"),
        ("remember_render_jobs", 0),
        ("remember_update_check", "100000"),
        ("remember_update_check", True),
        ("remember_update_check", float("nan")),
        ("remember_update_check", float("inf")),
        ("remember_update_check", -float("inf")),
        ("skip_update", 123),
        ("skip_update", b"v0.3.1"),
        ("skip_update", None),
        ("remember_recording", "ride.forces"),
        ("remember_recording", None),
        ("remember_export", "ride.mov"),
        ("remember_export", 123),
        ("language", "es"),
        ("language", "de"),
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
        preferences.remember_language(Language.GERMAN)
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
        preferences.remember_language(Language.GERMAN)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.executemany(
                "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
                [
                    ("language", "es"),
                    ("appearance", "blue"),
                    ("automatic_updates", "1"),
                    ("restore_last_file", "1"),
                    ("last_recording_path", "relative.forces"),
                    ("export_fps", "NaN"),
                    ("render_jobs", "NaN"),
                    ("update_checked_at", "invalid"),
                ],
            )
        assert preferences.language() == "en"
        assert preferences.language(Language.GERMAN) == "de"
        assert preferences.appearance() is Appearance.SYSTEM
        assert preferences.export_fps() is StandardFrameRate.FPS_50
        assert preferences.render_jobs() == 1
        assert not preferences.automatic_updates()
        assert not preferences.restore_last_file()
        assert preferences.last_recording() is None
        preferences.remember_automatic_updates(True)
        assert preferences.update_check_due(100000)
        preferences.remember_automatic_updates(False)
        assert not Preferences(database).automatic_updates()


def test_language_and_appearance_survive_restart_with_safe_defaults() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        database = Path(temporary) / "preferences.sqlite3"
        preferences = Preferences(database)
        assert preferences.language() == "en" and preferences.appearance() is Appearance.SYSTEM
        preferences.remember_language(Language.GERMAN)
        preferences.remember_appearance(Appearance.LIGHT)
        restored = Preferences(database)
        assert restored.language() == "de" and restored.appearance() is Appearance.LIGHT
        preferences.remember_appearance(Appearance.VERBOLTEN)
        assert Preferences(database).appearance() is Appearance.VERBOLTEN
        preferences.remember_appearance(Appearance.MANTA)
        assert Preferences(database).appearance() is Appearance.MANTA
        preferences.remember_appearance(Appearance.FALCONS_FLIGHT)
        assert Preferences(database).appearance() is Appearance.FALCONS_FLIGHT
        preferences.remember_appearance(Appearance.TARON)
        assert Preferences(database).appearance() is Appearance.TARON
        preferences.remember_appearance(Appearance.RED_FORCE)
        assert Preferences(database).appearance() is Appearance.RED_FORCE
        preferences.remember_appearance(Appearance.LOCH_NESS)
        assert Preferences(database).appearance() is Appearance.LOCH_NESS
        preferences.remember_appearance(Appearance.SLINKY_DOG_DASH)
        assert Preferences(database).appearance() is Appearance.SLINKY_DOG_DASH
        preferences.remember_appearance(Appearance.TOP_THRILL_2)
        assert Preferences(database).appearance() is Appearance.TOP_THRILL_2


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
        assert not blocked.restore_last_file()
        assert blocked.last_recording() is None


def test_last_recording_and_restore_preference_survive_restart() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        root = Path(temporary)
        recording = root / "ride.forces"
        recording.write_bytes(b"recording")
        database = root / "preferences.sqlite3"
        preferences = Preferences(database)
        assert not preferences.restore_last_file()
        assert preferences.last_recording() is None
        preferences.remember_recording(recording)
        preferences.remember_restore_last_file(True)
        restored = Preferences(database)
        assert restored.restore_last_file()
        assert restored.last_recording() == recording.resolve()
        restored.remember_restore_last_file(False)
        assert not Preferences(database).restore_last_file()
        assert restored.last_recording() == recording.resolve()
        recording.unlink()
        assert restored.last_recording() is None
        # A folder with the same name is not a restorable recording.
        recording.mkdir()
        assert restored.last_recording() is None


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
        assert preferences.export_fps() is StandardFrameRate.FPS_50
        preferences.remember_language(Language.GERMAN)
        for rate in StandardFrameRate:
            preferences.remember_export_fps(rate)
            restored = Preferences(database)
            assert restored.export_fps() == rate and restored.language() == "de"
        preferences.remember_export_fps(60)
        assert Preferences(database).export_fps() is StandardFrameRate.FPS_60
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("UPDATE preferences SET value = 'invalid' WHERE key = 'export_fps'")
        assert Preferences(database).export_fps() is StandardFrameRate.FPS_50
