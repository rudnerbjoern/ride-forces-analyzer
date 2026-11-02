"""Portable Library round trips, tolerant fields and rollback of unsafe restores."""

from collections.abc import Generator, Iterator
from contextlib import closing, contextmanager
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import Mock
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

import pytest

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.exports.history import prepare_repeat
from ride_forces_analyzer.rendering.model import ExportSettings, StandardFrameRate, prepare_export
from ride_forces_analyzer.storage.library import LibraryStore, LibraryStoreError
from ride_forces_analyzer.storage.library_backup import (
    BackupLimits,
    LibraryBackup,
    LibraryBackupError,
    LibraryTransferCancelled,
)
from ride_forces_analyzer.storage.library_history import ExportRequest, LibraryHistory
from ride_forces_analyzer.storage.preferences import (
    DEFAULT_LIBRARY_VIDEO_LABELS,
    Language,
    Preferences,
)
from tests.analysis.test_recording_preparation import synthetic_source
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def contents(store: LibraryStore) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    with store.connection() as connection:
        connection.row_factory = sqlite3.Row
        for table in ("recordings", "export_history", "video_links"):
            rows: list[dict[str, object]] = []
            for row in connection.execute(
                f"SELECT * FROM {table} ORDER BY "
                + ("source_sha256" if table == "recordings" else "id"),
            ):
                values: dict[str, object] = dict(row)
                values.pop("id", None)
                if table == "recordings":
                    raw = row["source_bytes"]
                    values["source_bytes"] = (len(raw), sha256(raw).hexdigest())
                rows.append(values)
            result[table] = rows
    return result


@pytest.fixture(scope="module")
def complete_backup() -> Iterator[tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]]]:
    with TemporaryDirectory(dir=".tmp") as directory:
        root = Path(directory)
        store = LibraryStore(root / "original.sqlite3")
        preferences = Preferences(root / "preferences.sqlite3")
        labels = ("YouTube", "Unused custom label", "Private", "Scheduled")
        assert preferences.remember_library_video_labels(labels)
        paths = (
            *REAL_FIXTURE_DIRECTORY.glob("*.zforces"),
            *REAL_FIXTURE_DIRECTORY.glob("*.forces"),
        )
        original_hashes = {path: sha256(path.read_bytes()).hexdigest() for path in paths}
        archive = LibraryArchive(store, preferences)
        imported = archive.import_paths(paths)
        assert all(item.status in {"imported", "duplicate"} for item in imported)
        manta = next(entry for entry in store.entries() if entry.source_ride_name == "Manta")
        data = archive.reopen(manta.source_sha256)
        assert isinstance(data, ExplorerData) and data.analysis is not None
        indices = data.source.recording.indices
        store.update_metadata(
            manta.source_sha256,
            {
                "ride_name": "My Manta",
                "park_name": "My park",
                "row": "Front",
                "seat": "Left",
                "train": "Blue",
                "riding_position": "Flying",
                "notes": "Keep all notes\nSecond line",
            },
        )
        store.update_markers(
            data.source,
            (5000, 6000),
            CalibrationOverrides(indices.gravity, indices.incline),
        )
        store.set_workflow_status(manta.source_sha256, "video_ready")
        store.save_video_link(manta.source_sha256, "https://example.invalid/private", "Private")
        store.save_video_link(
            manta.source_sha256,
            "https://example.invalid/scheduled",
            "Retired label",
        )
        other = next(
            entry for entry in store.entries() if entry.source_sha256 != manta.source_sha256
        )
        store.save_video_link(other.source_sha256, "http://example.invalid/variant", "")
        data = archive.reopen(manta.source_sha256)
        assert isinstance(data, ExplorerData) and data.analysis is not None
        history = LibraryHistory(store)
        settings = ExportSettings(fps=StandardFrameRate.FPS_59_94)
        request = ExportRequest.capture(data.analysis, "video", 5000, 5009, settings)
        snapshot = prepare_export(data.analysis, settings, 5000, 5009).snapshot
        output = root / "overlay.mov"
        output.write_bytes(b"external video bytes must not be archived")
        for status in ("completed", "failed", "cancelled"):
            attempt = history.start(request, "single")
            assert attempt is not None
            history.prepared(attempt, snapshot)
            history.finish(
                attempt,
                status,
                1.25,
                output=output if status == "completed" else None,
                file_size=output.stat().st_size if status == "completed" else None,
                gpu=True,
                error=None if status == "completed" else "Recorded outcome",
            )
        backup = root / "complete.zip"
        LibraryBackup(store, preferences).backup(backup)
        expected = contents(store)
        with ZipFile(backup) as zipped:
            manifest = json.loads(zipped.read("manifest.json"))
            assert manifest["library_video_labels"] == list(labels)
            assert manifest["alembic_revision"] == "1_3_search"
            assert set(zipped.namelist()) == {
                "manifest.json",
                "recordings.jsonl",
                "exports.jsonl",
                "video_links.jsonl",
                *(
                    f"sources/{row['source_sha256']}.{row['source_format']}"
                    for row in expected["recordings"]
                ),
            }
            for row in expected["recordings"]:
                raw = zipped.read(f"sources/{row['source_sha256']}.{row['source_format']}")
                assert (
                    len(raw) == row["source_byte_count"]
                    and sha256(raw).hexdigest() == row["source_sha256"]
                )
        assert {path: sha256(path.read_bytes()).hexdigest() for path in paths} == original_hashes
        output.unlink()
        yield backup, expected, labels


def rewrite(source: Path, destination: Path, changes: dict[str, bytes | None]) -> None:
    with ZipFile(source) as before, ZipFile(destination, "w", compression=ZIP_DEFLATED) as after:
        for member in before.infolist():
            data = changes.get(member.filename, before.read(member))
            if data is not None:
                after.writestr(member.filename, data)
        for name, data in changes.items():
            if name not in before.namelist() and data is not None:
                after.writestr(name, data)


def target(root: Path) -> tuple[LibraryStore, Preferences, LibraryBackup]:
    store = LibraryStore(root / "library.sqlite3")
    preferences = Preferences(root / "preferences.sqlite3")
    source = synthetic_source(name="Existing ride")
    store.archive(source, "existing.forces", (2, 6), CalibrationOverrides())
    preferences.remember_language(Language.GERMAN)
    preferences.remember_render_jobs(1)
    preferences.remember_library_video_labels(("Existing option",))
    return store, preferences, LibraryBackup(store, preferences)


def test_complete_round_trip_reopens_sources_and_repeats_saved_recipe(
    complete_backup: tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]],
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, expected, labels = complete_backup
    store = LibraryStore(export_directory / "fresh.sqlite3")
    preferences = Preferences(export_directory / "preferences.sqlite3")
    preferences.remember_language(Language.FRENCH)
    LibraryBackup(store, preferences).restore(path, replace=True)
    assert contents(store) == expected
    assert (
        preferences.library_video_labels() == labels and preferences.language() == Language.FRENCH
    )
    monkeypatch.setattr(
        "ride_forces_analyzer.explorer.library.import_forces",
        Mock(side_effect=AssertionError("No external source lookup")),
    )
    archive = LibraryArchive(store, preferences)
    for entry in store.entries():
        reopened = archive.reopen(entry.source_sha256)
        assert isinstance(reopened, ExplorerData)
        assert reopened.source.recording.source.provenance.path is None
        assert reopened.source.source_sha256 == entry.source_sha256
    manta = next(entry for entry in store.entries() if entry.source_ride_name == "Manta")
    saved = next(
        entry
        for entry in LibraryHistory(store).entries(manta.source_sha256)
        if entry.status == "completed"
    )
    assert saved.output_path is not None and not Path(saved.output_path).exists()
    repeat = prepare_repeat(saved, LibraryHistory(store))
    assert repeat.request.settings is not None and repeat.request.settings.fps == "60000/1001"
    assert repeat.data.source.additions.row == "Front"
    assert repeat.data.ride_bounds == (5000, 6000)


@pytest.mark.parametrize(
    "case",
    [
        "version",
        "revision",
        "missing-member",
        "unexpected-member",
        "hash",
        "relationship",
        "index",
        "truncated",
        "duplicate",
        "duplicate-source",
        "traversal",
        "expansion",
    ],
)
def test_unsafe_archives_preserve_active_library_and_preferences(
    complete_backup: tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]],
    export_directory: Path,
    case: str,
) -> None:
    source, _, _ = complete_backup
    store, preferences, service = target(export_directory)
    before = contents(store)
    old_labels = preferences.library_video_labels()
    damaged = export_directory / "damaged.zip"
    with ZipFile(source) as zipped:
        manifest = json.loads(zipped.read("manifest.json"))
        records = [json.loads(line) for line in zipped.read("recordings.jsonl").splitlines()]
        changes: dict[str, bytes | None] = {}
        if case == "version":
            manifest["format_version"] = 999
        elif case == "revision":
            manifest["alembic_revision"] = "99_0"
        elif case == "missing-member":
            changes["video_links.jsonl"] = None
        elif case == "unexpected-member":
            changes["overlay.mov"] = b"must not be imported"
        elif case == "hash":
            member = next(name for name in zipped.namelist() if name.startswith("sources/"))
            changes[member] = b"changed original"
        elif case == "duplicate-source":
            member = next(name for name in zipped.namelist() if name.startswith("sources/"))
            other = (
                member.removesuffix(".zforces") + ".forces"
                if member.endswith(".zforces")
                else member + ".zforces"
            )
            changes[other] = zipped.read(member)
        elif case == "relationship":
            rows = [json.loads(line) for line in zipped.read("video_links.jsonl").splitlines()]
            rows[0]["recording_sha256"] = "f" * 64
            changes["video_links.jsonl"] = b"\n".join(json.dumps(row).encode() for row in rows)
        elif case == "index":
            records[0]["first_sample"] = -1
            changes["recordings.jsonl"] = b"\n".join(json.dumps(row).encode() for row in records)
        elif case == "traversal":
            changes["../outside.forces"] = b"unsafe"
        changes["manifest.json"] = json.dumps(manifest).encode()
    rewrite(source, damaged, changes)
    if case == "truncated":
        damaged.write_bytes(damaged.read_bytes()[:-30])
    elif case == "duplicate":
        with pytest.warns(UserWarning, match="Duplicate name"), ZipFile(damaged, "a") as zipped:
            zipped.writestr("manifest.json", json.dumps(manifest))
    elif case == "expansion":
        service = LibraryBackup(
            store,
            preferences,
            limits=replace(BackupLimits(), max_expanded_bytes=100),
        )
    with pytest.raises((LibraryBackupError, LibraryStoreError)):
        service.restore(damaged, replace=True)
    assert contents(store) == before
    assert (
        preferences.library_video_labels() == old_labels
        and preferences.language() == Language.GERMAN
    )
    assert not (export_directory / "outside.forces").exists()


def test_missing_fields_use_null_source_values_and_defaults(
    complete_backup: tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]],
    export_directory: Path,
) -> None:
    source, expected, _ = complete_backup
    records = [
        {"source_sha256": row["source_sha256"], "row_override": None}
        for row in expected["recordings"]
    ]
    exports = [{"recording_sha256": row["recording_sha256"]} for row in expected["export_history"]]
    links = [{"recording_sha256": row["recording_sha256"]} for row in expected["video_links"]]
    modified = export_directory / "optional-fields.zip"
    rewrite(
        source,
        modified,
        {
            "manifest.json": b"{}",
            "recordings.jsonl": b"\n".join(json.dumps(row).encode() for row in records),
            "exports.jsonl": b"\n".join(json.dumps(row).encode() for row in exports),
            "video_links.jsonl": b"\n".join(json.dumps(row).encode() for row in links),
        },
    )
    store, preferences, service = target(export_directory)
    service.restore(modified, replace=True)
    assert len(store.entries()) == len(expected["recordings"])
    assert preferences.library_video_labels() == DEFAULT_LIBRARY_VIDEO_LABELS
    for entry in store.entries():
        assert entry.workflow_status == "imported"
        archived = store.source(entry.source_sha256)
        assert archived.additions.row is None and archived.additions.notes == ""
        assert archived.calibration == CalibrationOverrides()
        assert all(
            link.label == "" and link.url == "" for link in store.video_links(entry.source_sha256)
        )
        assert all(
            attempt.status == "interrupted" and attempt.request_json == "{}"
            for attempt in LibraryHistory(store).entries(entry.source_sha256)
        )


def test_empty_label_list_is_restored_without_defaults(
    complete_backup: tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]],
    export_directory: Path,
) -> None:
    source, _, _ = complete_backup
    with ZipFile(source) as zipped:
        manifest = json.loads(zipped.read("manifest.json"))
    manifest["library_video_labels"] = []
    modified = export_directory / "empty-labels.zip"
    rewrite(source, modified, {"manifest.json": json.dumps(manifest).encode()})
    _, preferences, service = target(export_directory)
    service.restore(modified, replace=True)
    assert Preferences(preferences.path).library_video_labels() == ()


def test_restore_commit_failure_rolls_back_library_and_labels(
    complete_backup: tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]],
    export_directory: Path,
) -> None:
    source, _, _ = complete_backup
    store, preferences, service = target(export_directory)
    before = contents(store)
    with closing(sqlite3.connect(preferences.path)) as connection, connection:
        connection.execute(
            "CREATE TRIGGER reject_labels BEFORE INSERT ON preferences WHEN NEW.key='library_video_labels' BEGIN SELECT RAISE(ABORT,'injected restore failure'); END",
        )
    with pytest.raises(LibraryStoreError, match="injected restore failure"):
        service.restore(source, replace=True)
    assert contents(store) == before
    assert preferences.library_video_labels() == ("Existing option",)


def test_cancelled_or_failed_backups_and_restores_leave_no_partial_state(
    complete_backup: tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]],
    export_directory: Path,
) -> None:
    source, _, _ = complete_backup
    store, preferences, service = target(export_directory)
    old_zip = export_directory / "old.zip"
    old_zip.write_bytes(b"old backup remains")
    with pytest.raises(LibraryTransferCancelled):
        service.backup(old_zip, overwrite=True, cancelled=lambda: True)
    assert old_zip.read_bytes() == b"old backup remains"
    limited = LibraryBackup(
        store,
        preferences,
        limits=replace(BackupLimits(), max_expanded_bytes=10),
    )
    with pytest.raises(LibraryBackupError):
        limited.backup(old_zip, overwrite=True)
    assert old_zip.read_bytes() == b"old backup remains"
    before = contents(store)
    with pytest.raises(LibraryTransferCancelled):
        service.restore(source, replace=True, cancelled=lambda: True)
    assert contents(store) == before
    with pytest.raises(LibraryBackupError, match="Confirm"):
        service.restore(source)


def test_backup_snapshot_stays_consistent_while_live_metadata_changes(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, preferences, service = target(export_directory)
    digest = store.entries()[0].source_sha256
    original = ZipFile.writestr

    def write(
        archive: ZipFile,
        name: str | ZipInfo,
        data: bytes | str,
        compress_type: int | None = None,
        compresslevel: int | None = None,
    ) -> None:
        filename = name.filename if isinstance(name, ZipInfo) else name
        if filename.startswith("sources/"):
            store.update_metadata(digest, {"ride_name": "Changed during ZIP writing"})
            preferences.remember_library_video_labels(("Changed option",))
        original(archive, name, data, compress_type=compress_type, compresslevel=compresslevel)

    monkeypatch.setattr(ZipFile, "writestr", write)
    path = export_directory / "consistent.zip"
    service.backup(path)
    assert store.entries()[0].ride_name == "Changed during ZIP writing"
    restored = LibraryStore(export_directory / "restored.sqlite3")
    labels = Preferences(export_directory / "restored-preferences.sqlite3")
    LibraryBackup(restored, labels).restore(path, replace=True)
    assert restored.entries()[0].ride_name == "Existing ride"
    assert labels.library_video_labels() == ("Existing option",)


def test_restore_cancellation_after_copying_rolls_back_both_databases(
    complete_backup: tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]],
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, _, _ = complete_backup
    store, preferences, service = target(export_directory)
    before = contents(store)
    cancelled = Event()
    original = store.connection

    @contextmanager
    def connection_with_cancel() -> Generator[sqlite3.Connection]:
        with original() as connection:
            connection.create_function("cancel_restore", 0, cancelled.set)
            yield connection

    monkeypatch.setattr(store, "connection", connection_with_cancel)
    with closing(sqlite3.connect(preferences.path)) as connection, connection:
        connection.execute(
            "CREATE TRIGGER cancel_restore AFTER INSERT ON preferences "
            "WHEN NEW.key='library_video_labels' BEGIN SELECT cancel_restore(); END",
        )
    with pytest.raises(LibraryTransferCancelled):
        service.restore(source, replace=True, cancelled=cancelled.is_set)
    assert cancelled.is_set() and contents(store) == before
    assert preferences.library_video_labels() == ("Existing option",)


def test_cancellation_while_writing_does_not_replace_existing_backup(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, service = target(export_directory)
    destination = export_directory / "existing.zip"
    destination.write_bytes(b"Existing backup")
    cancelled = Event()
    original = ZipFile.writestr

    def write(
        archive: ZipFile,
        name: str | ZipInfo,
        data: bytes | str,
        compress_type: int | None = None,
        compresslevel: int | None = None,
    ) -> None:
        original(archive, name, data, compress_type=compress_type, compresslevel=compresslevel)
        cancelled.set()

    monkeypatch.setattr(ZipFile, "writestr", write)
    with pytest.raises(LibraryTransferCancelled):
        service.backup(destination, overwrite=True, cancelled=cancelled.is_set)
    assert destination.read_bytes() == b"Existing backup"


def test_restore_preserves_an_active_export(
    complete_backup: tuple[Path, dict[str, list[dict[str, object]]], tuple[str, ...]],
    export_directory: Path,
) -> None:
    source, _, _ = complete_backup
    store, preferences, service = target(export_directory)
    digest = store.entries()[0].source_sha256
    with store.connection() as connection:
        connection.execute(
            "INSERT INTO export_history(recording_sha256,export_kind,origin,started_at_utc,status,application_version,request_json) VALUES (?, 'video', 'single', '', 'running', '', '{}')",
            (digest,),
        )
    before = contents(store)
    with pytest.raises(LibraryBackupError, match="Finish active exports"):
        service.restore(source, replace=True)
    assert contents(store) == before
    assert preferences.library_video_labels() == ("Existing option",)
