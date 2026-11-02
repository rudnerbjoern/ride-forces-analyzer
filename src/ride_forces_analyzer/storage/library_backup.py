"""Portable Library ZIPs and validated, transactional full replacement.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words EXDEV ENOTSUP

from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from hashlib import sha256
from importlib.resources import as_file, files
import errno
import json
import os
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any, cast
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import TypeAdapter

from ride_forces_analyzer import __version__
from ride_forces_analyzer.analysis.calibration import (
    CalibrationOverrides,
    validate_calibration_references,
)
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer.importers import (
    DEFAULT_LIMITS,
    ImportLimits,
    ImportSuccess,
    import_forces_bytes,
)
from ride_forces_analyzer.importers._json_preflight import DecodeProblem, preflight
from ride_forces_analyzer.importers.library_metadata import project_library_metadata, recording_uuid
from ride_forces_analyzer.validation.checks import validate_sample_range, validate_sha256
from .library import LibraryStore, LibraryStoreError
from .library_search import library_search_values
from .library_history import LibraryHistory
from .preferences import DEFAULT_LIBRARY_VIDEO_LABELS, Preferences

_MEMBERS = {"manifest.json", "recordings.jsonl", "exports.jsonl", "video_links.jsonl"}
_TABLES = ("recordings", "export_history", "video_links")
_SOURCE = re.compile(r"sources/([0-9a-f]{64})\.(forces|zforces)\Z")


class LibraryBackupError(ValueError):
    """A backup or restore failed without publishing partial data."""


class LibraryTransferCancelled(Exception):
    """Cancellation requested before backup publication or restore commit."""


@dataclass(frozen=True, slots=True)
class BackupLimits:
    """Bound ZIP expansion and JSON processing independently of source import limits.

    Attributes:
        max_archive_bytes: Maximum compressed ZIP length.
        max_expanded_bytes: Total permitted uncompressed member bytes.
        max_members: Maximum ZIP members and rows per metadata file.
        max_metadata_bytes: Maximum bytes in one JSON Lines file.
        max_row_bytes: Maximum manifest/JSON row length; sources use import limits.
    """

    max_archive_bytes: int = 4 * 1024**3
    max_expanded_bytes: int = 4 * 1024**3
    max_members: int = 100_000
    max_metadata_bytes: int = 256 * 1024**2
    max_row_bytes: int = DEFAULT_LIMITS.max_bytes

    def __post_init__(self) -> None:
        """Require positive resource budgets before reading or writing files.

        Raises:
            ValueError: A budget is not a positive integer.
        """
        for definition in fields(self):
            value = getattr(self, definition.name)
            if type(value) is not int or value <= 0:
                raise ValueError("Backup limits must be positive integers")


def _cancel(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise LibraryTransferCancelled()


def _json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
        "utf-8",
    )


def _object(raw: bytes, limits: BackupLimits) -> dict[str, Any]:
    if len(raw) > limits.max_row_bytes:
        raise LibraryBackupError("Library metadata exceeds its resource limit")
    text = raw.decode("utf-8-sig")
    try:
        preflight(
            text,
            ImportLimits(max_bytes=limits.max_row_bytes, max_string_length=limits.max_row_bytes),
        )
        result = json.loads(text)
    except (DecodeProblem, RecursionError, ValueError) as error:
        raise LibraryBackupError("Invalid Library backup JSON") from error
    if not isinstance(result, dict):
        raise LibraryBackupError("Library metadata must be a JSON object")
    return cast(dict[str, Any], result)


def _revisions() -> set[str]:
    with as_file(files("ride_forces_analyzer.storage.library_migrations")) as location:
        config = Config()
        config.set_main_option("script_location", str(location).replace("%", "%%"))
        return {
            revision.revision for revision in ScriptDirectory.from_config(config).walk_revisions()
        }


def _insert(connection: sqlite3.Connection, table: str, values: dict[str, Any]) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    selected = {key: value for key, value in values.items() if key in columns and key != "id"}
    names = ",".join(f'"{key}"' for key in selected)
    connection.execute(
        f"INSERT INTO {table} ({names}) VALUES ({','.join('?' for _ in selected)})",
        tuple(selected.values()),
    )


class LibraryBackup:
    """Own complete Library backup/restore without touching external media files.

    Attributes:
        store: Library whose tables and exact source bytes are transferred.
        preferences: Independent preferences; only video-label choices are restored.
        limits: Per-operation resource budgets.
    """

    def __init__(
        self,
        store: LibraryStore | None = None,
        preferences: Preferences | None = None,
        *,
        limits: BackupLimits = BackupLimits(),
    ) -> None:
        """Select stores without opening or modifying either database.

        Args:
            store: Explicit Library, or the application-local default.
            preferences: Explicit preferences, or the application-local default.
            limits: ZIP/member/metadata budgets, with existing source-import limits.
        """
        self.store = store if store is not None else LibraryStore()
        self.preferences = preferences if preferences is not None else Preferences()
        self.limits = limits

    def backup(
        self,
        destination: Path,
        *,
        overwrite: bool = False,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Path:
        """Publish one complete ZIP from a consistent read of all Library tables.

        Args:
            destination: ZIP destination; external recordings/videos are never written.
            overwrite: Explicit permission to replace an existing backup after success.
            cancelled: Cooperative cancellation before publication.

        Returns:
            Published ZIP path.

        Raises:
            LibraryBackupError: Invalid/corrupt data or a resource budget is exceeded.
            LibraryStoreError: The Library cannot be read.
            LibraryTransferCancelled: Cancellation leaves no incomplete backup.
            OSError: Writing/publication fails, preserving an existing destination.
        """
        destination = destination.resolve()
        if destination.suffix.lower() != ".zip":
            raise LibraryBackupError("Choose a ZIP filename")
        if destination.exists() and not overwrite:
            raise FileExistsError(destination)
        _cancel(cancelled)
        with TemporaryDirectory(prefix=".rfa-backup-", dir=destination.parent) as directory:
            root = Path(directory)
            staged = root / "library.zip"
            snapshot = root / "library.sqlite3"
            self._snapshot(snapshot, cancelled)
            expanded = 0
            counts: dict[str, int] = {}
            with (
                ZipFile(staged, "w", compression=ZIP_DEFLATED) as archive,
                closing(sqlite3.connect(snapshot)) as connection,
            ):
                connection.row_factory = sqlite3.Row
                revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[
                    0
                ]
                labels = self.preferences.library_video_labels()
                for table, member in zip(
                    _TABLES,
                    ("recordings.jsonl", "exports.jsonl", "video_links.jsonl"),
                    strict=True,
                ):
                    count = 0
                    metadata_size = 0
                    metadata = root / member
                    with metadata.open("wb") as stream:
                        for row in connection.execute(
                            f"SELECT * FROM {table} ORDER BY "
                            + ("source_sha256" if table == "recordings" else "id"),
                        ):
                            _cancel(cancelled)
                            values = dict(row)
                            if table == "recordings":
                                data = values.pop("source_bytes")
                                digest = validate_sha256(
                                    values["source_sha256"],
                                    "Invalid archived source hash",
                                )
                                format = values["source_format"]
                                if (
                                    format not in {"forces", "zforces"}
                                    or not isinstance(data, bytes)
                                    or len(data) != values["source_byte_count"]
                                    or sha256(data).hexdigest() != digest
                                ):
                                    raise LibraryBackupError(
                                        "Archived source integrity check failed",
                                    )
                                expanded += len(data)
                                if (
                                    len(data) > DEFAULT_LIMITS.max_bytes
                                    or expanded > self.limits.max_expanded_bytes
                                ):
                                    raise LibraryBackupError(
                                        "Library backup exceeds its resource limit",
                                    )
                                archive.writestr(f"sources/{digest}.{format}", data)
                            encoded = _json(values) + b"\n"
                            _object(encoded, self.limits)
                            metadata_size += len(encoded)
                            count += 1
                            if (
                                count > self.limits.max_members - 4
                                or metadata_size > self.limits.max_metadata_bytes
                            ):
                                raise LibraryBackupError(
                                    "Library metadata exceeds its resource limit",
                                )
                            stream.write(encoded)
                    counts[table] = count
                    expanded += metadata_size
                    archive.write(metadata, member)
                manifest = _json(
                    {
                        "format_version": 1,
                        "application_version": __version__,
                        "alembic_revision": revision,
                        "library_video_labels": labels,
                        "counts": counts,
                    },
                )
                _object(manifest, self.limits)
                expanded += len(manifest)
                if expanded > self.limits.max_expanded_bytes:
                    raise LibraryBackupError("Library backup exceeds its resource limit")
                archive.writestr("manifest.json", manifest)
            if staged.stat().st_size > self.limits.max_archive_bytes:
                raise LibraryBackupError("Library ZIP exceeds its resource limit")
            _cancel(cancelled)
            if overwrite:
                staged.replace(destination)
            else:
                self._publish_new(staged, destination, cancelled)
        return destination

    def _snapshot(self, destination: Path, cancelled: Callable[[], bool]) -> None:
        self.store.initialize()

        def progress(status: int, remaining: int, total: int) -> None:
            _cancel(cancelled)

        try:
            with (
                closing(sqlite3.connect(self.store.path)) as source,
                closing(sqlite3.connect(destination)) as target,
            ):
                source.backup(target, pages=256, progress=progress)
        except sqlite3.Error as error:
            raise LibraryStoreError(f"Library snapshot: {error}") from error

    def _publish_new(self, staged: Path, destination: Path, cancelled: Callable[[], bool]) -> None:
        try:
            os.link(staged, destination)
            return
        except OSError as error:
            if error.errno not in (errno.EXDEV, errno.EPERM, errno.ENOTSUP):
                raise
        created = False
        try:
            with destination.open("xb") as target, staged.open("rb") as source:
                created = True
                while block := source.read(1024 * 1024):
                    _cancel(cancelled)
                    target.write(block)
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise

    def restore(
        self,
        source: Path,
        *,
        replace: bool = False,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> None:
        """Validate a complete archive, then replace the Library and labels atomically.

        Missing optional values use NULL or existing domain/schema defaults. Original
        bytes and relationships remain mandatory when they cannot be derived safely.

        Args:
            source: Portable ZIP; no member is extracted to a caller-supplied path.
            replace: Explicit confirmation to replace the entire active Library.
            cancelled: Cancellation before the replacement transaction commits.

        Raises:
            LibraryBackupError: Archive/relationships/source data are unsafe or invalid.
            LibraryStoreError: Replacement fails; existing data/labels are rolled back.
            LibraryTransferCancelled: Cancellation leaves the active Library intact.
            OSError: The ZIP or temporary storage cannot be read/written.
        """
        if not replace:
            raise LibraryBackupError("Confirm full Library replacement before restoring")
        _cancel(cancelled)
        if source.stat().st_size > self.limits.max_archive_bytes:
            raise LibraryBackupError("Library ZIP exceeds its resource limit")
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with TemporaryDirectory(
                prefix=".rfa-restore-",
                dir=self.store.path.parent,
            ) as directory:
                candidate = LibraryStore(Path(directory) / "library.sqlite3")
                with ZipFile(source) as archive:
                    members = self._members(archive)
                    manifest = _object(
                        self._read(archive, members["manifest.json"], self.limits.max_row_bytes),
                        self.limits,
                    )
                    if (
                        manifest.get("format_version", 1) != 1
                        or type(manifest.get("format_version", 1)) is not int
                    ):
                        raise LibraryBackupError("Unsupported Library backup version")
                    if (
                        manifest.get("alembic_revision") is not None
                        and manifest["alembic_revision"] not in _revisions()
                    ):
                        raise LibraryBackupError("Unsupported Library schema revision")
                    labels = manifest.get("library_video_labels")
                    if labels is None:
                        labels = list(DEFAULT_LIBRARY_VIDEO_LABELS)
                    labels = self._validate_labels(labels)
                    counts = self._populate(candidate, archive, members, cancelled)
                    LibraryHistory(candidate).interrupt_running()
                    raw_counts: object = manifest.get("counts") or {}
                    if not isinstance(raw_counts, dict):
                        raise LibraryBackupError("Invalid Library backup counts")
                    declared = cast(dict[str, Any], raw_counts)
                    if any(value != counts.get(key) for key, value in declared.items()):
                        raise LibraryBackupError("Library backup counts do not match its contents")
                _cancel(cancelled)
                self._replace(candidate, labels, cancelled)
        except LibraryBackupError:
            raise
        except (
            BadZipFile,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
            sqlite3.Error,
            UnicodeError,
        ) as error:
            raise LibraryBackupError(f"Invalid Library backup: {error}") from error

    def _members(self, archive: ZipFile) -> dict[str, ZipInfo]:
        infos = archive.infolist()
        if (
            len(infos) > self.limits.max_members
            or sum(info.file_size for info in infos) > self.limits.max_expanded_bytes
        ):
            raise LibraryBackupError("Library ZIP expansion exceeds its resource limit")
        members: dict[str, ZipInfo] = {}
        source_digests: set[str] = set()
        for info in infos:
            if info.filename in members or (
                info.filename not in _MEMBERS and _SOURCE.fullmatch(info.filename) is None
            ):
                raise LibraryBackupError("Duplicate or unexpected Library ZIP member")
            match = _SOURCE.fullmatch(info.filename)
            if match is not None:
                if match.group(1) in source_digests:
                    raise LibraryBackupError("Duplicate Library source identity")
                source_digests.add(match.group(1))
            if (
                info.is_dir()
                or info.flag_bits & 1
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise LibraryBackupError("Unsafe Library ZIP member")
            limit = (
                self.limits.max_row_bytes
                if info.filename == "manifest.json"
                else self.limits.max_metadata_bytes
                if info.filename in _MEMBERS
                else DEFAULT_LIMITS.max_bytes
            )
            if info.file_size > limit:
                raise LibraryBackupError("Library ZIP member exceeds its resource limit")
            members[info.filename] = info
        if not _MEMBERS <= members.keys():
            raise LibraryBackupError("Library ZIP is missing a required member")
        return members

    def _read(self, archive: ZipFile, info: ZipInfo, limit: int) -> bytes:
        with archive.open(info) as stream:
            result = stream.read(limit + 1)
        if len(result) != info.file_size or len(result) > limit:
            raise LibraryBackupError("Library ZIP member length does not match")
        return result

    def _rows(
        self,
        archive: ZipFile,
        info: ZipInfo,
        cancelled: Callable[[], bool],
    ) -> Iterator[dict[str, Any]]:
        with archive.open(info) as stream:
            count = 0
            while raw := stream.readline(self.limits.max_row_bytes + 1):
                _cancel(cancelled)
                if not raw.strip():
                    continue
                count += 1
                if count > self.limits.max_members:
                    raise LibraryBackupError("Library metadata row limit exceeded")
                yield _object(raw, self.limits)

    def _populate(
        self,
        candidate: LibraryStore,
        archive: ZipFile,
        members: dict[str, ZipInfo],
        cancelled: Callable[[], bool],
    ) -> dict[str, int]:
        sources = {
            match.group(1): (info, match.group(2))
            for name, info in members.items()
            if (match := _SOURCE.fullmatch(name))
        }
        used: set[str] = set()
        counts = {table: 0 for table in _TABLES}
        with candidate.connection() as connection:
            for row in self._rows(archive, members["recordings.jsonl"], cancelled):
                digest = row.get("source_sha256")
                if digest is None and len(sources) == 1:
                    digest = next(iter(sources))
                if not isinstance(digest, str) or digest not in sources or digest in used:
                    raise LibraryBackupError("Missing, duplicate or unmatched recording identity")
                info, format = sources[digest]
                raw = self._read(archive, info, DEFAULT_LIMITS.max_bytes)
                if (
                    sha256(raw).hexdigest() != digest
                    or row.get("source_byte_count", len(raw)) not in (None, len(raw))
                    or row.get("source_format", format) not in (None, format)
                ):
                    raise LibraryBackupError("Archived source integrity check failed")
                imported = import_forces_bytes(raw, compressed=format == "zforces")
                if not isinstance(imported, ImportSuccess):
                    raise LibraryBackupError("Archived source cannot be decoded")
                values = self._recording(row, imported, format)
                _insert(connection, "recordings", values)
                used.add(digest)
                counts["recordings"] += 1
            if used != sources.keys():
                raise LibraryBackupError("Library ZIP contains an unassociated original source")
            for table, member in (
                ("export_history", "exports.jsonl"),
                ("video_links", "video_links.jsonl"),
            ):
                for row in self._rows(archive, members[member], cancelled):
                    digest = row.get("recording_sha256")
                    if digest is None and len(used) == 1:
                        digest = next(iter(used))
                    if not isinstance(digest, str) or digest not in used:
                        raise LibraryBackupError(
                            "Library relationship references a missing recording",
                        )
                    defaults: dict[str, Any] = {"recording_sha256": digest}
                    if table == "video_links":
                        defaults.update(url="", label="")
                    else:
                        defaults.update(
                            export_kind="video",
                            origin="single",
                            started_at_utc="",
                            status="interrupted",
                            application_version="",
                            request_json="{}",
                        )
                    values = {
                        **defaults,
                        **{
                            key: value
                            for key, value in row.items()
                            if value is not None or key not in defaults
                        },
                    }
                    values["recording_sha256"] = digest
                    for key in ("request_json", "export_snapshot_json"):
                        if isinstance(values.get(key), dict):
                            values[key] = _json(values[key]).decode("utf-8")
                    _insert(connection, table, values)
                    counts[table] += 1
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise LibraryBackupError("Invalid Library relationships")
        return counts

    def _recording(self, row: dict[str, Any], source: ImportSuccess, format: str) -> dict[str, Any]:
        metadata = project_library_metadata(source.recording)
        indices = source.recording.indices
        calibration = CalibrationOverrides()
        first: int | None = row.get("first_sample")
        last: int | None = row.get("last_sample")
        if any(value is not None and type(value) is not int for value in (first, last)):
            raise LibraryBackupError("Restored recording indices must be integers")
        default_first = min(indices.start, last if last is not None else indices.end)
        default_last = max(indices.end, first if first is not None else default_first)
        defaults: dict[str, Any] = {
            "source_sha256": source.source_sha256,
            "source_filename": f"{source.source_sha256}.{format}",
            "source_format": format,
            "source_byte_count": source.byte_count,
            "source_ride_name": metadata.source_ride_name,
            "source_park_name": metadata.source_park_name,
            "recorded_at_utc": metadata.recorded_at_utc,
            "recorded_day": metadata.recorded_day,
            "day_timezone": metadata.day_timezone,
            "imported_at_utc": "",
            "first_sample": default_first,
            "calibration_algorithm_version": calibration.algorithm_version,
            "calibration_window_samples": calibration.window_samples,
            "notes": "",
            "workflow_status": "imported",
            "source_uuid": recording_uuid(source.recording),
        }
        defaults["last_sample"] = default_last
        required_columns = {
            "source_sha256",
            "source_filename",
            "source_format",
            "source_byte_count",
            "imported_at_utc",
            "first_sample",
            "last_sample",
            "calibration_algorithm_version",
            "calibration_window_samples",
            "notes",
            "workflow_status",
            "search_text",
        }
        values: dict[str, Any] = {
            **defaults,
            **{
                key: value
                for key, value in row.items()
                if value is not None or key not in required_columns
            },
        }
        values["source_sha256"] = source.source_sha256
        values["source_bytes"] = source.recording.source.original_bytes
        values["source_format"] = format
        values["source_byte_count"] = source.byte_count
        validate_sample_range(
            values["first_sample"],
            values["last_sample"],
            len(source.recording.motion.acceleration),
            "Invalid restored recording bounds",
        )
        references = CalibrationOverrides(
            values.get("gravity_index"),
            values.get("incline_index"),
            values["calibration_algorithm_version"],
            values["calibration_window_samples"],
        )
        validate_calibration_references(source, references, calculation_time=datetime.now(UTC))
        additions = RecordingAdditions.model_validate(
            {"notes": values["notes"]}
            | {
                key: values.get(column)
                for key, column in (
                    ("ride_name", "ride_name_override"),
                    ("park_name", "park_name_override"),
                    ("row", "row_override"),
                    ("seat", "seat_override"),
                    ("train", "train_override"),
                    ("riding_position", "riding_position_override"),
                )
            },
        )
        values["park_key"], values["search_text"] = library_search_values(
            additions.ride_name if additions.ride_name is not None else values["source_ride_name"],
            additions.park_name if additions.park_name is not None else values["source_park_name"],
        )
        return values

    def _validate_labels(self, labels: object) -> list[str]:
        values = TypeAdapter(list[str]).validate_python(labels, strict=True)
        if any(not label.strip() for label in values) or len(set(values)) != len(values):
            raise LibraryBackupError("Invalid Library video-label choices")
        return values

    def _replace(
        self,
        candidate: LibraryStore,
        labels: list[str],
        cancelled: Callable[[], bool],
    ) -> None:
        self.preferences.path.parent.mkdir(parents=True, exist_ok=True)
        with self.store.connection() as connection:
            connection.execute("ATTACH DATABASE ? AS restored", (str(candidate.path),))
            connection.execute(
                "ATTACH DATABASE ? AS label_preferences",
                (str(self.preferences.path),),
            )
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
            if (
                connection.execute(
                    "SELECT 1 FROM export_history WHERE status='running' LIMIT 1",
                ).fetchone()
                is not None
            ):
                raise LibraryBackupError(
                    "Finish active exports or restart the application before restoring the Library",
                )
            for schema in ("main", "label_preferences"):
                if connection.execute(f"PRAGMA {schema}.journal_mode").fetchone()[0] == "wal":
                    raise LibraryBackupError(
                        "Library restore requires standard SQLite journal mode",
                    )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS label_preferences.preferences (key TEXT PRIMARY KEY,value TEXT NOT NULL)",
            )
            for table in reversed(_TABLES):
                connection.execute(f"DELETE FROM main.{table}")
            for table in _TABLES:
                _cancel(cancelled)
                connection.execute(f"INSERT INTO main.{table} SELECT * FROM restored.{table}")
            connection.execute(
                "INSERT OR REPLACE INTO label_preferences.preferences(key,value) VALUES ('library_video_labels',?)",
                (_json(labels).decode("utf-8"),),
            )
            _cancel(cancelled)
