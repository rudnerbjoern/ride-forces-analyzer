"""Isolated processes verify report lifetime and complete exception hooks."""

# cspell:words getppid excepthook

from pathlib import Path
import subprocess
import sys


def run_report(directory: Path, program: str) -> subprocess.CompletedProcess[str]:
    setup = """
import os
from pathlib import Path
import sys
from ride_forces_analyzer import error_reporting as reports
directory = Path(sys.argv[1])
reports.data_directory = lambda: directory
"""
    return subprocess.run(
        [sys.executable, "-c", setup + program, str(directory)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_report_retains_every_error_and_replaces_completed_runs(export_directory: Path) -> None:
    result = run_report(
        export_directory,
        """
support = directory / "support"
support.mkdir()
(support / "error-report-999999999.txt").write_text("obsolete")
active = support / f"error-report-{os.getppid()}.txt"
active.write_text("active instance")
path = reports.initialize_error_reporting()
assert path is not None and path == reports.initialize_error_reporting()
assert active.read_text() == "active instance"
assert not (support / "error-report-999999999.txt").exists()
for number in range(75):
    try:
        raise ValueError(f"failure-{number}")
    except ValueError as error:
        reports.record_error("Import", error)
text = path.read_text(encoding="utf-8")
assert all(f"ValueError: failure-{number}" in text for number in range(75))
print(path.name)
""",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    old_report = export_directory / "support" / result.stdout.strip()
    assert old_report.is_file()
    replacement = run_report(
        export_directory,
        """
path = reports.initialize_error_reporting()
assert path is not None
reports.record_error("Export", message="current run")
print(path.name)
""",
    )
    assert replacement.returncode == 0, replacement.stdout + replacement.stderr
    new_report = export_directory / "support" / replacement.stdout.strip()
    assert new_report.is_file() and not old_report.exists()
    assert "current run" in new_report.read_text(encoding="utf-8")
    assert "failure-" not in new_report.read_text(encoding="utf-8")


def test_report_captures_chains_groups_threads_and_unraisable_errors(
    export_directory: Path,
) -> None:
    result = run_report(
        export_directory,
        """
import faulthandler
import threading
reports.initialize_error_reporting()
assert faulthandler.is_enabled()
def failed_thread():
    raise RuntimeError("thread failure")
thread = threading.Thread(target=failed_thread)
thread.start()
thread.join()
class Broken:
    def __del__(self):
        raise RuntimeError("destructor failure")
broken = Broken()
del broken
try:
    raise ValueError("original cause")
except ValueError as cause:
    raise ExceptionGroup("all errors", [RuntimeError(f"group-{n}") for n in range(25)]) from cause
""",
    )
    assert result.returncode != 0
    report = next((export_directory / "support").glob("error-report-*.txt"))
    text = report.read_text(encoding="utf-8")
    for expected in (
        "Unhandled main-thread exception",
        "Unhandled thread exception",
        "Unraisable exception",
        "thread failure",
        "destructor failure",
        "ValueError: original cause",
        "Traceback",
    ):
        assert expected in text
    assert all(f"RuntimeError: group-{number}" in text for number in range(25))


def test_unwritable_report_location_preserves_exception_behavior(export_directory: Path) -> None:
    result = run_report(
        export_directory,
        """
directory.mkdir(exist_ok=True)
(directory / "support").write_text("not a directory")
before = sys.excepthook
assert reports.initialize_error_reporting() is None
assert sys.excepthook is before
raise RuntimeError("original failure remains visible")
""",
    )
    assert result.returncode != 0
    assert "original failure remains visible" in result.stderr


def test_handled_import_and_export_worker_failures_reach_report(export_directory: Path) -> None:
    result = run_report(
        export_directory,
        """
from ride_forces_analyzer.ui import loading, data_export
path = reports.initialize_error_reporting()
assert path is not None
loading.LoadWorker(directory / "missing.forces").run()
def broken_import(*args, **kwargs):
    raise RuntimeError("unexpected import failure")
loading.load_recording = broken_import
loading.LoadWorker(directory / "missing.forces").run()
def broken_export(*args, **kwargs):
    raise OSError("export write failure")
data_export.export_csv = broken_export
data_export.DataWorker(None, directory / "output.csv", 0, 0, "csv").run()
text = path.read_text(encoding="utf-8")
assert "Import:" in text
assert "Import worker:" in text and "RuntimeError: unexpected import failure" in text
assert "Data export:" in text and "OSError: export write failure" in text
""",
    )
    assert result.returncode == 0, result.stdout + result.stderr
