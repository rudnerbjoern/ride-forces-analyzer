from hashlib import sha256
from pathlib import Path

import pytest

from tests.support.recordings import (
    REAL_FIXTURE_DIRECTORY,
    REAL_FIXTURES,
    RFDB_FIXTURE_DIRECTORY,
    RFDB_FIXTURES,
)


@pytest.mark.parametrize(
    ("directory", "fixtures"),
    [(REAL_FIXTURE_DIRECTORY, REAL_FIXTURES), (RFDB_FIXTURE_DIRECTORY, RFDB_FIXTURES)],
    ids=("app", "rfdb"),
)
def test_real_fixture_inventory(directory: Path, fixtures: dict[str, tuple[int, str]]) -> None:
    filenames = {fixture.name for fixture in directory.glob("*.forces")}
    assert filenames == set(fixtures)


@pytest.mark.parametrize(
    ("path", "expected_size", "expected_digest"),
    [
        (directory / name, size, digest)
        for directory, fixtures in (
            (REAL_FIXTURE_DIRECTORY, REAL_FIXTURES),
            (RFDB_FIXTURE_DIRECTORY, RFDB_FIXTURES),
        )
        for name, (size, digest) in fixtures.items()
    ],
)
def test_real_fixture_is_unaltered(path: Path, expected_size: int, expected_digest: str) -> None:
    original = path.read_bytes()
    assert len(original) == expected_size
    assert sha256(original).hexdigest() == expected_digest
