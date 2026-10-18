"""Published application version."""

from ride_forces_analyzer import __version__


def test_version() -> None:
    assert __version__ == "0.2.0"
