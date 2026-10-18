"""FR-003/023/027: typed outcomes, deterministic diagnostics and ownership."""

from dataclasses import FrozenInstanceError
import subprocess
import sys
from typing import assert_type

import pytest

from ride_forces_analyzer.domain import Recording, SourceEnvelope
from ride_forces_analyzer.importers import (
    ImportDiagnostic,
    ImportFailure,
    ImportResult,
    ImportSuccess,
    Severity,
    json_pointer,
    ordered_diagnostics,
)


def test_diagnostics_sort_by_severity_pointer_code_and_stable_ties() -> None:
    first = ImportDiagnostic("B", Severity.WARNING, "/z", "first tie", 0)
    second = ImportDiagnostic("B", Severity.WARNING, "/z", "second tie", 0)
    error = ImportDiagnostic("CORE", Severity.ERROR, "", "core invalid")
    before = ImportDiagnostic("A", Severity.WARNING, "/a~1b/10", "earlier pointer")
    same_pointer = ImportDiagnostic("A", Severity.WARNING, "/z", "earlier code")
    info = ImportDiagnostic("NOTE", Severity.INFO, "", "metadata absent")
    inputs = [info, first, before, error, same_pointer, second]
    ordered = ordered_diagnostics(inputs)
    inputs.clear()
    assert ordered == (error, before, same_pointer, first, second, info)
    assert ordered_diagnostics(ordered) == ordered
    assert first.sample_index == 0
    with pytest.raises(FrozenInstanceError):
        setattr(first, "message", "changed")


def test_json_pointer_escapes_keys_and_keeps_root_distinct() -> None:
    assert json_pointer() == ""
    assert json_pointer("") == "/"
    assert json_pointer("a/b~c", 0, "x") == "/a~1b~0c/0/x"
    with pytest.raises(ValueError):
        json_pointer(True)


@pytest.mark.parametrize("pointer", ["field", "/a~", "/a~2"])
def test_invalid_diagnostic_pointer_is_rejected(pointer: str) -> None:
    with pytest.raises(ValueError):
        ImportDiagnostic("BAD", Severity.ERROR, pointer, "invalid field")


def test_success_requires_recording_and_no_errors(synthetic_recording: Recording) -> None:
    warning = ImportDiagnostic(
        "GPS_NEGATIVE_VALUE",
        Severity.WARNING,
        "/locationSequence/0/speed",
        "Unverified negative value",
        0,
    )
    inputs = [warning]
    result = ImportSuccess(synthetic_recording, inputs)
    inputs.clear()
    assert result.success and result.diagnostics == (warning,)
    assert result.recording == synthetic_recording
    assert result.byte_count == len(synthetic_recording.source.original_bytes)
    assert result.source_sha256 == synthetic_recording.source.provenance.sha256
    assert result.schema_version == "2.2.0"
    with pytest.raises(ValueError):
        ImportSuccess(synthetic_recording, [ImportDiagnostic("BAD", Severity.ERROR, "", "bad")])
    with pytest.raises(FrozenInstanceError):
        setattr(result, "recording", None)


def test_failure_exposes_no_recording_or_invented_provenance() -> None:
    error = ImportDiagnostic("UNREADABLE_SOURCE", Severity.ERROR, "", "Unable to read source")
    result = ImportFailure([error])
    assert not result.success and result.recording is None
    assert result.source is None and result.byte_count is None and result.source_sha256 is None
    assert result.schema_version is None
    retained = ImportFailure([error], source=SourceEnvelope(b"raw bytes"), schema_version="future")
    assert retained.byte_count == 9 and retained.source is not None
    assert retained.source.original_bytes == b"raw bytes"
    assert retained.source.root is None and retained.recording is None
    empty = ImportFailure([error], source=SourceEnvelope(b""))
    assert empty.byte_count == 0 and empty.source_sha256 is not None
    assert empty.source_sha256 != retained.source_sha256
    with pytest.raises(ValueError):
        ImportFailure([])
    with pytest.raises(ValueError):
        ImportFailure([ImportDiagnostic("OPTIONAL", Severity.WARNING, "", "optional defect")])


def test_diagnostic_indices_sort_lexically_without_reordering_samples() -> None:
    second = ImportDiagnostic("BAD", Severity.WARNING, "/motion/2", "invalid value", 2)
    tenth = ImportDiagnostic("BAD", Severity.WARNING, "/motion/10", "invalid value", 10)
    assert ordered_diagnostics([second, tenth]) == (tenth, second)


@pytest.mark.parametrize("index", [-1, True])
def test_diagnostic_index_rejects_boolean_and_negative_values(index: int) -> None:
    with pytest.raises(ValueError):
        ImportDiagnostic("BAD", Severity.ERROR, "", "invalid value", index)


def test_result_union_is_typed_and_equal_on_repeat(synthetic_recording: Recording) -> None:
    def outcome(success: bool) -> ImportResult:
        if success:
            return ImportSuccess(synthetic_recording)
        return ImportFailure([ImportDiagnostic("BAD", Severity.ERROR, "", "bad")])

    result = outcome(True)
    if isinstance(result, ImportSuccess):
        assert_type(result.recording, Recording)
        assert_type(result.byte_count, int)
        assert result == ImportSuccess(synthetic_recording)
    else:
        assert_type(result.recording, None)
        assert_type(result.byte_count, int | None)
        pytest.fail("Expected synthetic success")


def test_public_model_packages_do_not_import_qt() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import ride_forces_analyzer.domain; import ride_forces_analyzer.importers; "
            "assert not any(name.startswith(('PySide', 'PyQt')) for name in sys.modules); "
            "print('Qt-independent model packages verified')",
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert b"Qt-independent model packages verified" in result.stdout
