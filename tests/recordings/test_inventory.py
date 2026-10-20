"""DEV-REQ-002 Stage 0: FR-004/FR-030 evidence, not importer acceptance."""

from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

from tests.support.fixture_inventory import inspect_bytes, inventory, snapshot_bytes
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

SNAPSHOT = Path(__file__).resolve().parents[1] / "fixtures" / "schema-inventory.json"


def test_complete_recursive_fixture_snapshot() -> None:
    """Complete schema observations preserve all pinned bytes and modification times."""
    originals = {
        name: (path.read_bytes(), path.stat().st_mtime_ns)
        for name in REAL_FIXTURES
        for path in (REAL_FIXTURE_DIRECTORY / name,)
    }
    actual = inventory()
    assert set(actual["fixtures"]) == set(REAL_FIXTURES)
    for name, (before, modified) in originals.items():
        result = actual["fixtures"][name]
        assert (result["byte_count"], result["sha256"]) == REAL_FIXTURES[name]
        path = REAL_FIXTURE_DIRECTORY / name
        assert path.read_bytes() == before
        assert path.stat().st_mtime_ns == modified
        assert sha256(before).hexdigest() == REAL_FIXTURES[name][1]
    # Compare aggregate statistics, never dump raw GPS values on failure.
    assert snapshot_bytes(actual) == SNAPSHOT.read_bytes()


def test_inventory_sees_late_nested_extensions_and_presence() -> None:
    """A prefix-only scan would miss this final element and optional nested field."""
    raw = b'{"samples":[' + b'{"x":"1"},' * 1000
    raw += b'{"x":2,"extra":{"flags":[true,null]}}]}'
    result = inspect_bytes(raw)
    paths = result["paths"]
    assert paths['$["samples"]'].get("array_lengths") == {"1001": 1}
    assert paths['$["samples"][*]'].get("members") == {"extra": 1, "x": 1001}
    assert paths['$["samples"][*]["x"]']["types"] == {"number": 1, "string": 1000}
    assert paths['$["samples"][*]["extra"]["flags"][*]']["types"] == {"boolean": 1, "null": 1}
    assert result["max_container_depth"] == 5
    assert sum(sum(entry["types"].values()) for entry in paths.values()) == result["node_count"]


def test_inventory_distinguishes_empty_missing_null_and_escaped_keys() -> None:
    paths = inspect_bytes(b'{"empty":[],"object":{},"nothing":null,"a/b~c":[{"*":true},{}]}')[
        "paths"
    ]
    assert paths['$["empty"]'].get("array_lengths") == {"0": 1}
    assert paths['$["object"]'].get("members") == {}
    assert paths['$["nothing"]']["types"] == {"null": 1}
    assert paths['$["a/b~c"][*]'].get("members") == {"*": 1}
    assert paths['$["a/b~c"][*]["*"]']["types"] == {"boolean": 1}
    assert '$["missing"]' not in paths


def test_inventory_is_independent_of_object_order() -> None:
    first = inspect_bytes(b'{"a":1,"b":{"x":"2","y":[]}}')
    second = inspect_bytes(b'{"b":{"y":[],"x":"2"},"a":1}')
    assert first["paths"] == second["paths"]
    assert first["sha256"] != second["sha256"]


def test_inventory_cli_refuses_recording_as_output() -> None:
    """FR-004/AC-02: the regeneration command cannot overwrite a real fixture."""
    path = REAL_FIXTURE_DIRECTORY / next(iter(REAL_FIXTURES))
    before = path.read_bytes()
    modified = path.stat().st_mtime_ns
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "support/fixture_inventory.py"),
            "--output",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 2
    assert b"output must be under the repository .tmp" in result.stderr
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == modified


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}', b"NaN", b"1e9999"])
def test_inventory_refuses_lossy_or_non_finite_observations(raw: bytes) -> None:
    """FR-024 evidence quality only: this utility does not validate importer limits."""
    with pytest.raises(ValueError):
        inspect_bytes(raw)
