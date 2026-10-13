from pathlib import Path

from ride_forces_analyzer import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_real_fixture_is_present() -> None:
    fixtures = list((Path(__file__).parent / "fixtures" / "real").glob("*.forces"))
    assert len(fixtures) == 1
    assert fixtures[0].stat().st_size > 100_000
