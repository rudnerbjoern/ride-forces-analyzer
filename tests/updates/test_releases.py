"""Release selection and bounded public transport without live network access."""

# cspell:words autouse

from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self
from urllib.error import URLError

import pytest

from ride_forces_analyzer.runtime import updates
from ride_forces_analyzer.storage.preferences import Preferences


@pytest.fixture(autouse=True)
def windows_release_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates, "runtime_target", lambda: "windows-x64")


def release(tag: str, **fields: object) -> dict[str, object]:
    return {
        "tag_name": tag,
        "draft": False,
        "published_at": "2026-10-18T12:00:00Z",
        "assets": [
            {
                "state": "uploaded",
                "size": 123,
                "browser_download_url": f"{updates.REPOSITORY_URL}/releases/download/{tag}/Ride-Forces-Analyzer-{tag.removeprefix('v')}-windows-x64.exe",
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


@pytest.mark.parametrize(
    "target,suffix",
    [
        ("windows-x64", "windows-x64.exe"),
        ("linux-x64", "linux-x64.tar.gz"),
        ("macos-arm64", "macos-arm64.zip"),
        ("macos-x64", "macos-x64.zip"),
    ],
)
def test_update_requires_a_download_for_the_native_platform(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    suffix: str,
) -> None:
    monkeypatch.setattr(updates, "runtime_target", lambda: target)
    row = release(
        "v0.5.0",
        assets=[
            {
                "state": "uploaded",
                "size": 123,
                "browser_download_url": f"{updates.REPOSITORY_URL}/releases/download/v0.5.0/Ride-Forces-Analyzer-0.5.0-{suffix}",
            },
        ],
    )
    selected = updates.select_release([row], "0.4.0")
    assert selected is not None and selected.tag == "v0.5.0"
    row["assets"] = [
        {
            "state": "uploaded",
            "size": 123,
            "browser_download_url": f"{updates.REPOSITORY_URL}/releases/download/v0.5.0/source.zip",
        },
    ]
    assert updates.select_release([row], "0.4.0") is None
    if target != "windows-x64":
        assert updates.select_release([release("v0.5.0")], "0.4.0") is None


def test_unsupported_platform_does_not_advertise_other_platform_downloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(updates, "runtime_target", lambda: None)
    assert updates.select_release([release("v0.5.0")], "0.4.0") is None


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
            rows = [release("v0.1.0")] * 100 if len(requests) == 1 else [release("v0.3.1")]
            return Response(json.dumps(rows).encode())

    def opener(*handlers: object) -> Opener:
        return Opener()

    monkeypatch.setattr(updates, "build_opener", opener)
    result = updates.check_for_update("0.1.0")
    assert result is not None and result.tag == "v0.3.1"
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
        preferences.skip_update("v0.3.1")
        restored = Preferences(path)
        assert restored.automatic_updates() and restored.skipped_update() == "v0.3.1"
        assert not restored.update_check_due(186399)
        assert restored.update_check_due(186400)


def test_malformed_release_entries_and_assets_are_ignored() -> None:
    rows = [None, release("v2.0.0", assets=None), release("v3.0.0", assets=[None])]
    assert updates.select_release(rows, "1.0.0") is None


def test_release_redirects_reject_other_hosts_and_insecure_urls() -> None:
    from http.client import HTTPMessage
    from typing import cast
    from urllib.request import HTTPRedirectHandler, Request

    handler = cast(HTTPRedirectHandler, getattr(updates, "_GitHubRedirects")())
    request = Request(updates.RELEASES_API)
    for url in ("http://api.github.com/releases", "https://example.invalid/releases"):
        with pytest.raises(updates.UpdateCheckError, match="Unexpected release API redirect"):
            handler.redirect_request(request, Response(b""), 302, "Found", HTTPMessage(), url)
    redirected = handler.redirect_request(
        request,
        Response(b""),
        302,
        "Found",
        HTTPMessage(),
        "https://api.github.com/releases?page=2",
    )
    assert redirected is not None
    assert redirected.full_url == "https://api.github.com/releases?page=2"


@pytest.mark.parametrize(
    "mode",
    ["before-request", "during-read", "after-read", "invalid", "pages"],
)
def test_release_transport_deadlines_shape_and_page_limits(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    from unittest.mock import Mock

    now = [0.0]
    calls = [0]

    def clock() -> float:
        calls[0] += 1
        return 0.0 if calls[0] == 1 else now[0]

    class ControlledResponse(Response):
        def read1(self, size: int | None = -1) -> bytes:
            data = super().read1(size)
            if mode == "after-read" and not data:
                now[0] = updates.CHECK_TIMEOUT + 1
            return data

    class Opener:
        def open(self, request: object, *, timeout: float) -> Response:
            if mode == "during-read":
                now[0] = updates.CHECK_TIMEOUT + 1
            payload: dict[str, object] | list[dict[str, object]] = (
                {} if mode == "invalid" else [release("v2.0.0")] * 100 if mode == "pages" else []
            )
            return ControlledResponse(json.dumps(payload).encode())

    if mode == "before-request":
        now[0] = updates.CHECK_TIMEOUT + 1
    monkeypatch.setattr(updates, "monotonic", clock)
    monkeypatch.setattr(updates, "build_opener", Mock(return_value=Opener()))
    monkeypatch.setattr(updates, "MAX_PAGES", 2)
    with pytest.raises(
        updates.UpdateCheckError,
        match="timed out|check limits|Invalid releases|page limit",
    ):
        updates.check_for_update("1.0.0")
