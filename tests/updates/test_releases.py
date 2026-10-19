"""Release selection and bounded public transport without live network access."""

from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self
from urllib.error import URLError

import pytest

from ride_forces_analyzer import updates
from ride_forces_analyzer.storage.preferences import Preferences


def release(tag: str, **fields: object) -> dict[str, object]:
    return {
        "tag_name": tag,
        "draft": False,
        "published_at": "2026-10-18T12:00:00Z",
        "assets": [
            {
                "state": "uploaded",
                "size": 123,
                "browser_download_url": f"{updates.REPOSITORY_URL}/releases/download/{tag}/source.zip",
            },
        ],
        **fields,
    }


def test_release_selection_uses_numeric_and_prerelease_order_not_api_order() -> None:
    result = updates.select_release(
        [release("v0.10.0rc2"), release("v0.9.0"), release("v0.10.0rc10")],
        "0.1.0",
    )
    assert result is not None and result.tag == "v0.10.0rc10"
    result = updates.select_release([release("v0.10.0rc10"), release("v0.10.0")], "0.10.0rc2")
    assert result is not None and result.tag == "v0.10.0"
    assert updates.select_release([release("v0.1.0"), release("v0.1.0rc1")], "0.1.0") is None


def test_unpublished_invalid_or_unavailable_releases_are_not_advertised() -> None:
    rows = [
        release("v9.0.0", draft=True),
        release("v8.0.0", published_at=None),
        release("v7.0.0", assets=[]),
        release("not-a-version"),
        release(
            "v6.0.0",
            assets=[
                {
                    "state": "uploaded",
                    "size": 1,
                    "browser_download_url": "https://example.invalid/download",
                },
            ],
        ),
    ]
    assert updates.select_release(rows, "0.1.0") is None
    with pytest.raises(updates.UpdateCheckError):
        updates.select_release({"message": "rate limited"}, "0.1.0")


class Response(BytesIO):
    def __enter__(self) -> Self:
        return self


def test_transport_uses_public_api_and_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []

    class Opener:
        def open(self, request: object, *, timeout: float) -> Response:
            from urllib.request import Request

            assert isinstance(request, Request)
            assert not request.has_header("Authorization")
            assert 0 < timeout <= updates.REQUEST_TIMEOUT
            requests.append(request.full_url)
            rows = [release("v0.1.0")] * 100 if len(requests) == 1 else [release("v0.3.0")]
            return Response(json.dumps(rows).encode())

    def opener(*handlers: object) -> Opener:
        return Opener()

    monkeypatch.setattr(updates, "build_opener", opener)
    result = updates.check_for_update("0.1.0")
    assert result is not None and result.tag == "v0.3.0"
    assert requests == [f"{updates.RELEASES_API}?per_page=100&page={page}" for page in (1, 2)]


def test_network_errors_and_large_responses_fail_without_false_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Opener:
        def open(self, request: object, *, timeout: float) -> Response:
            raise URLError("offline")

    def opener(*handlers: object) -> Opener:
        return Opener()

    monkeypatch.setattr(updates, "build_opener", opener)
    with pytest.raises(updates.UpdateCheckError):
        updates.check_for_update("0.1.0")

    class LargeOpener:
        def open(self, request: object, *, timeout: float) -> Response:
            return Response(b"x" * 17)

    monkeypatch.setattr(updates, "MAX_PAGE_BYTES", 16)

    def large_opener(*handlers: object) -> LargeOpener:
        return LargeOpener()

    monkeypatch.setattr(updates, "build_opener", large_opener)
    with pytest.raises(updates.UpdateCheckError):
        updates.check_for_update("0.1.0")


def test_update_preferences_opt_in_daily_attempts_and_skipped_version_survive_restart() -> None:
    with TemporaryDirectory(dir=".tmp") as temporary:
        path = Path(temporary) / "preferences.sqlite3"
        preferences = Preferences(path)
        assert not preferences.update_check_due(100000)
        preferences.remember_automatic_updates(True)
        assert preferences.update_check_due(100000)
        preferences.remember_update_check(100000)
        preferences.skip_update("v0.3.0")
        restored = Preferences(path)
        assert restored.automatic_updates() and restored.skipped_update() == "v0.3.0"
        assert not restored.update_check_due(186399)
        assert restored.update_check_due(186400)
