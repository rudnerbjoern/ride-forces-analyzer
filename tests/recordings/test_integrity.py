from hashlib import sha256

import pytest


from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


def test_real_fixture_inventory() -> None:
    filenames = {fixture.name for fixture in REAL_FIXTURE_DIRECTORY.glob("*.forces")}
    assert filenames == set(REAL_FIXTURES)


@pytest.mark.parametrize(
    "filename",
    REAL_FIXTURES,
    ids=[filename.split("-", 1)[0] for filename in REAL_FIXTURES],
)
def test_real_fixture_is_unaltered(filename: str) -> None:
    expected_size, expected_digest = REAL_FIXTURES[filename]
    original = (REAL_FIXTURE_DIRECTORY / filename).read_bytes()
    assert len(original) == expected_size
    assert sha256(original).hexdigest() == expected_digest
