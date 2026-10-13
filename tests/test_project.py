from hashlib import sha256
from pathlib import Path

from ride_forces_analyzer import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_real_fixture_is_present() -> None:
    fixtures = list((Path(__file__).parent / "fixtures" / "real").glob("*.forces"))
    assert len(fixtures) == 1
    assert fixtures[0].stat().st_size > 100_000


def test_real_fixture_is_unaltered() -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "real"
        / "Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces"
    )
    assert sha256(fixture.read_bytes()).hexdigest() == (
        "30cf81c360cb28f45ee97234779689bdcdd7ec3aa8fa148645a4b015771be6c6"
    )
