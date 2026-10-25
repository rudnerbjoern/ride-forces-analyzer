"""Optional public GitHub release discovery; independent of recording processing.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words newurl

from dataclasses import dataclass
import json
import re
from time import monotonic
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from http.client import HTTPMessage
from typing import IO, cast
from .runtime_paths import runtime_target

REPOSITORY_URL = "https://github.com/rudnerbjoern/ride-forces-analyzer"
RELEASES_API = "https://api.github.com/repos/rudnerbjoern/ride-forces-analyzer/releases"
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_PAGES = 5
REQUEST_TIMEOUT = 5.0
CHECK_TIMEOUT = 20.0
VERSION_PATTERN = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?")


class UpdateCheckError(Exception):
    """Public release availability could not be determined."""


@dataclass(frozen=True, slots=True)
class AvailableRelease:
    """Available release contract and owned data.

    Attributes:
        tag: Version tag selected for lookup, validation or suppression.
        url: Release page or download URL retained from release metadata.
    """

    tag: str
    url: str


def version_key(value: str) -> tuple[int, int, int, int, int] | None:
    """Parse a supported version into its release-order comparison key.

    Args:
        value: Candidate value to validate, format or store.

    Returns:
        Tuple of major, minor, patch, release-stage rank and stage number, or None for
        unsupported text.
    """
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        return None
    major, minor, patch, stage, number = match.groups()
    return (
        int(major),
        int(minor),
        int(patch),
        {"a": 0, "b": 1, "rc": 2, None: 3}[stage],
        int(number or 0),
    )


def select_release(releases: object, current: str) -> AvailableRelease | None:
    """Choose the highest newer published version with a native application asset.

    Args:
        releases: Available release metadata.
        current: Current measured value or operation state.

    Returns:
        Highest newer compatible release, or None when no candidate exists.

    Raises:
        UpdateCheckError: Invalid version or releases response.
    """
    installed = version_key(current)
    if installed is None or not isinstance(releases, list):
        raise UpdateCheckError("Invalid version or releases response")
    target = runtime_target()
    if target is None:
        return None
    suffixes = (
        ("-windows-x64.exe", "-windows-x64-standard.zip", "-windows-x64-complete.zip")
        if target == "windows-x64"
        else (f"-{target}.tar.gz",)
        if target == "linux-x64"
        else (f"-{target}.zip",)
    )
    candidates: list[tuple[tuple[int, int, int, int, int], AvailableRelease]] = []
    for raw_item in cast(list[object], releases):
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, object], raw_item)
        if item.get("draft") is not False or not item.get("published_at"):
            continue
        tag = item.get("tag_name")
        if (
            not isinstance(tag, str)
            or (version := version_key(tag)) is None
            or version <= installed
        ):
            continue
        assets = item.get("assets")
        if not isinstance(assets, list):
            continue
        prefix = f"{REPOSITORY_URL}/releases/download/{quote(tag, safe='')}/"
        for raw_asset in cast(list[object], assets):
            if not isinstance(raw_asset, dict):
                continue
            asset = cast(dict[str, object], raw_asset)
            size, url = asset.get("size"), asset.get("browser_download_url")
            if (
                asset.get("state") == "uploaded"
                and type(size) is int
                and size > 0
                and isinstance(url, str)
                and url.startswith(prefix)
                and url[len(prefix) :]
                in {f"Ride-Forces-Analyzer-{tag.removeprefix('v')}{suffix}" for suffix in suffixes}
            ):
                candidates.append(
                    (
                        version,
                        AvailableRelease(
                            tag,
                            f"{REPOSITORY_URL}/releases/tag/{quote(tag, safe='')}",
                        ),
                    ),
                )
                break
    return max(candidates, key=lambda candidate: candidate[0])[1] if candidates else None


class _GitHubRedirects(HTTPRedirectHandler):
    """Git hub redirects contract and owned data."""

    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        """Follow only HTTPS redirects within the GitHub API host.

        Args:
            req: HTTP request being redirected.
            fp: Response stream supplied by the redirect handler.
            code: HTTP response status code.
            msg: HTTP response status message.
            headers: HTTP response headers.
            newurl: Proposed redirect destination URL.

        Returns:
            Redirected request, or None when the base handler declines the redirect.

        Raises:
            UpdateCheckError: Unexpected release API redirect.
        """
        target = urlsplit(newurl)
        if target.scheme != "https" or target.netloc != "api.github.com":
            raise UpdateCheckError("Unexpected release API redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_for_update(current: str) -> AvailableRelease | None:
    """Bounded HTTPS requests with default certificate validation and no credentials.

    Args:
        current: Current measured value or operation state.

    Returns:
        Newer compatible release, or None when the installed version is current.

    Raises:
        UpdateCheckError: Release check timed out. Release response exceeded check limits.
            Invalid releases response. GitHub releases are unavailable. Release listing
            exceeded the page limit.
    """
    opener = build_opener(_GitHubRedirects())
    releases: list[object] = []
    deadline = monotonic() + CHECK_TIMEOUT
    try:
        for page in range(1, MAX_PAGES + 1):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise UpdateCheckError("Release check timed out")
            request = Request(
                f"{RELEASES_API}?per_page=100&page={page}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "Ride-Forces-Analyzer-update-check",
                },
            )
            with opener.open(request, timeout=min(REQUEST_TIMEOUT, remaining)) as response:
                chunks: list[bytes] = []
                size = 0
                while True:
                    if monotonic() > deadline:
                        raise UpdateCheckError("Release check timed out")
                    chunk = response.read1(min(65536, MAX_PAGE_BYTES + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > MAX_PAGE_BYTES:
                        raise UpdateCheckError("Release response exceeded check limits")
                payload = b"".join(chunks)
            if len(payload) > MAX_PAGE_BYTES or monotonic() > deadline:
                raise UpdateCheckError("Release response exceeded check limits")
            items: object = json.loads(payload)
            if not isinstance(items, list):
                raise UpdateCheckError("Invalid releases response")
            page_releases = cast(list[object], items)
            releases.extend(page_releases)
            if len(page_releases) < 100:
                return select_release(releases, current)
    except (OSError, URLError, ValueError) as error:
        raise UpdateCheckError("GitHub releases are unavailable") from error
    raise UpdateCheckError("Release listing exceeded the page limit")
