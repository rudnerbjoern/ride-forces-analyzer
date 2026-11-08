"""Original failures reach the shared log while presentation masks internal details."""

# cspell:words caplog xfferror prefs

import ast
import logging
from pathlib import Path
import subprocess
import sys

import pytest

from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.i18n import Language, get_language, set_language, tr
from ride_forces_analyzer.importers import ImportFailure, decode_forces
from ride_forces_analyzer.runtime.error_logging import error_message, record_error
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.storage.map_tiles import TileCache
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.explorer import loading


def test_exception_handlers_preserve_original_errors_or_document_normal_control_flow() -> None:
    root = Path(__file__).resolve().parents[2] / "src/ride_forces_analyzer"
    control_flow = {
        ("exports/batches.py", "run_batches", "FileExistsError"),  # Reserve another report name.
        ("exports/batches.py", "run_batches", "ExportCancelled"),
        ("rendering/model.py", "__post_init__", "ValueError"),  # Custom integer frame rate.
        ("runtime/error_reporting.py", "_running", "ProcessLookupError"),  # Completed process.
        ("runtime/error_reporting.py", "_running", "PermissionError"),  # Other process owner.
        ("runtime/stream_deck.py", "close", "FileNotFoundError"),  # Endpoint already removed.
        ("ui/dialogs/library_transfer.py", "run", "LibraryTransferCancelled"),
        ("ui/exports/data.py", "run", "(CsvExportCancelled, JsonExportCancelled)"),
        ("ui/exports/workers.py", "run", "ExportCancelled"),
        ("ui/presentation/translation.py", "set_ui_language", "RuntimeError"),  # Deleted Qt object.
    }
    missing: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            owner: ast.AST = node
            while owner in parents and not isinstance(
                owner,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                owner = parents[owner]
            assert isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef))
            key = (
                path.relative_to(root).as_posix(),
                owner.name,
                ast.unparse(node.type) if node.type is not None else "<any exception>",
            )
            if key in control_flow:
                continue
            # A failed report write uses logging's own stderr fallback to avoid recursion.
            if key == ("runtime/error_reporting.py", "emit", "Exception"):
                assert any(
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "handleError"
                    for call in ast.walk(node)
                )
                continue
            original_is_recorded = any(
                isinstance(call, ast.Call)
                and (
                    isinstance(call.func, ast.Name)
                    and call.func.id == "record_error"
                    or isinstance(call.func, ast.Attribute)
                    and call.func.attr == "_warn"
                )
                and any(isinstance(arg, ast.Name) and arg.id == node.name for arg in call.args)
                for call in ast.walk(node)
            )
            if not original_is_recorded:
                missing.append(f"{key[0]}:{node.lineno}: {key[1]} ({key[2]})")
    assert not missing, "Handled original errors must reach the common logger:\n" + "\n".join(
        missing,
    )


def test_shared_logging_does_not_load_qt() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from ride_forces_analyzer.runtime.error_logging import record_error; "
            "assert not any(name.startswith('PySide6') for name in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("language", list(Language))
def test_presentation_masks_internal_details_and_retains_approved_validation(
    language: Language,
) -> None:
    before = get_language()
    set_language(language)
    try:
        error = RuntimeError(r"internal database detail C:\Users\Private\source.forces")
        message = error_message(error)
        assert message == tr("The operation failed. See the error report for details.")
        assert "Private" not in message and "database" not in message
        for validation in (
            "This name already exists. Choose a new name or update the selected item.",
            "Choose or create a batch first",
            "Remove the jobs before deleting this batch",
            "Choose saved batches that contain export jobs",
        ):
            assert error_message(ValueError(validation)) == tr(validation)
    finally:
        set_language(before)


def test_original_exception_chain_context_and_long_messages_are_unchanged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    detail = "original beginning " + "x" * 6000 + " original end"
    try:
        try:
            raise PermissionError(r"original denied path C:\Users\Private\source.forces")
        except PermissionError as cause:
            raise RuntimeError(detail) from cause
    except RuntimeError as error:
        record_error("Test operation", error, context=r"Path: C:\Users\Private\source.forces")
        assert caplog.records[-1].exc_info is not None
        assert caplog.records[-1].exc_info[1] is error
    text = logging.Formatter("%(message)s").format(caplog.records[-1])
    assert detail in text and "PermissionError: original denied path" in text
    assert r"Path: C:\Users\Private\source.forces" in text
    assert "direct cause" in text and "Traceback" in text


def test_subprocess_output_is_recorded_without_truncation(caplog: pytest.LogCaptureFixture) -> None:
    output = "output beginning " + "x" * 6000 + " output end"
    error = subprocess.CalledProcessError(
        9,
        ["encoder"],
        output=output,
        stderr=b"original\xfferror",
    )
    record_error("Encoder", error)
    assert output in caplog.text and r"original\xfferror" in caplog.text
    assert caplog.records[0].exc_info is not None
    assert caplog.records[0].exc_info[1] is error


@pytest.mark.parametrize("kind", [FileNotFoundError, PermissionError, ValueError])
def test_source_failures_keep_original_exceptions_and_attempted_paths(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    kind: type[Exception],
) -> None:
    path = Path(".tmp/private-source.forces")
    error = kind("unmasked original filesystem detail")

    def fail(_path: Path) -> None:
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(Path, "stat", fail)
        result = decode_forces(path)
    assert isinstance(result, ImportFailure)
    assert str(path) in caplog.text and str(error) in caplog.text
    assert caplog.records[-1].exc_info is not None
    assert caplog.records[-1].exc_info[1] is error
    assert str(error) not in result.diagnostics[0].message


def test_original_import_diagnostic_and_path_survive_localized_presentation(
    export_directory: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    archive = LibraryArchive(
        LibraryStore(export_directory / "library.sqlite3"),
        Preferences(export_directory / "prefs.sqlite3"),
    )
    path = Path(r"\\server\share\private-source.forces")
    before = get_language()
    set_language(Language.GERMAN)
    try:
        result = archive.import_paths((path,))[0]
        assert result.status == "failed" and result.error == error_message()
        assert result.error is not None
        assert "server" not in result.error
    finally:
        set_language(before)
    assert str(path) in caplog.text
    assert "INVALID_SOURCE_PATH" in caplog.text
    assert "Network and device paths are unsupported" in caplog.text


@pytest.mark.parametrize("worker_kind", ["single", "multiple"])
def test_import_workers_mask_internal_errors_but_log_the_original_with_source_context(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    worker_kind: str,
) -> None:
    path = Path(".tmp/private-source.forces")
    error = RuntimeError("unmasked internal worker detail")

    def fail(*_args: object) -> None:
        raise error

    messages: list[str] = []

    def remember_failure(_generation: int, message: str) -> None:
        messages.append(message)

    if worker_kind == "single":
        monkeypatch.setattr(loading, "import_recording", fail)
        worker = loading.LoadWorker(path)
        worker.signals.failed.connect(remember_failure)
    else:
        monkeypatch.setattr(loading.LibraryArchive, "import_paths", fail)
        worker = loading.ArchiveImportWorker((path,))
        worker.signals.failed.connect(messages.append)
    worker.run()
    assert len(messages) == 1
    assert str(error) not in messages[0] and str(path) not in messages[0]
    assert str(error) in caplog.text and str(path) in caplog.text
    assert caplog.records[-1].exc_info is not None and caplog.records[-1].exc_info[1] is error


@pytest.mark.parametrize("subsystem", ["preferences", "tile-cache"])
def test_storage_fallbacks_log_original_database_failures(
    export_directory: Path,
    caplog: pytest.LogCaptureFixture,
    subsystem: str,
) -> None:
    path = export_directory / "corrupt.sqlite3"
    path.write_bytes(b"not a database")
    if subsystem == "preferences":
        assert Preferences(path).last_library_recording() is None
    else:
        assert TileCache(path).get("provider", 1, 0, 0) is None
    assert str(path) in caplog.text and "file is not a database" in caplog.text
    assert any(record.exc_info for record in caplog.records)
