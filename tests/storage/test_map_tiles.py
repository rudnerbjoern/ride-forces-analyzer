"""SQLite tile persistence, provider identity, retention and best-effort failure."""

from pathlib import Path

import pytest

from ride_forces_analyzer.storage import map_tiles
from ride_forces_analyzer.storage.map_tiles import TileCache, TileEntry


def test_tiles_persist_with_independent_provider_zoom_and_coordinates(
    export_directory: Path,
) -> None:
    path = export_directory / "tiles.sqlite3"
    entry = TileEntry(b"image", 1234.0, '"etag"', "date")
    TileCache(path).put("provider", 2, 1, 3, entry)
    reopened = TileCache(path)
    assert reopened.get("provider", 2, 1, 3) == entry
    for key in (
        ("other", 2, 1, 3),
        ("provider", 3, 1, 3),
        ("provider", 2, 0, 3),
        ("provider", 2, 1, 2),
    ):
        assert reopened.get(*key) is None
    replacement = TileEntry(b"updated", 5678.0, "", "")
    reopened.put("provider", 2, 1, 3, replacement)
    assert TileCache(path).get("provider", 2, 1, 3) == replacement
    reopened.delete("provider", 2, 1, 3)
    assert reopened.get("provider", 2, 1, 3) is None


def test_cache_budget_evicts_least_recently_used_across_providers(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [1.0]
    monkeypatch.setattr(map_tiles, "time", lambda: now[0])
    cache = TileCache(export_directory / "tiles.sqlite3", max_bytes=8)
    entry = TileEntry(b"1234", 0, "", "")
    cache.put("a", 0, 0, 0, entry)
    now[0] = 2
    cache.put("b", 0, 0, 0, entry)
    now[0] = 3
    assert cache.get("a", 0, 0, 0) == entry
    now[0] = 4
    cache.put("c", 0, 0, 0, entry)
    assert cache.get("a", 0, 0, 0) == cache.get("c", 0, 0, 0) == entry
    assert cache.get("b", 0, 0, 0) is None
    now[0] = 5
    cache.put("oversized", 0, 0, 0, TileEntry(b"123456789", 0, "", ""))
    assert cache.get("oversized", 0, 0, 0) is None
    assert cache.get("a", 0, 0, 0) == cache.get("c", 0, 0, 0) == entry


@pytest.mark.parametrize("mode", ["directory", "corrupt"])
def test_unavailable_cache_is_a_miss_and_writes_are_optional(
    export_directory: Path,
    mode: str,
) -> None:
    path = export_directory / "tiles.sqlite3"
    if mode == "directory":
        path.mkdir()
    else:
        path.write_bytes(b"not a database")
    cache = TileCache(path)
    assert cache.get("a", 0, 0, 0) is None
    cache.put("a", 0, 0, 0, TileEntry(b"image", 0, "", ""))
    cache.delete("a", 0, 0, 0)
    assert cache.get("a", 0, 0, 0) is None
    assert not cache.clear()
    assert cache.count() is None


def test_clear_removes_all_providers_and_allows_cache_reuse(export_directory: Path) -> None:
    cache = TileCache(export_directory / "tiles.sqlite3")
    entry = TileEntry(b"image", 1234.0, '"etag"', "date")
    assert cache.count() == 0
    for provider in ("a", "b"):
        cache.put(provider, 2, 1, 3, entry)
    assert cache.count() == 2
    assert cache.clear()
    assert cache.count() == 0
    for provider in ("a", "b"):
        assert cache.get(provider, 2, 1, 3) is None
    assert cache.clear()
    cache.put("a", 2, 1, 3, entry)
    assert cache.get("a", 2, 1, 3) == entry
    assert cache.count() == 1
