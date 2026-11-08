"""Prepare explicitly selected application, plugin and interface versions.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words keepends tofile

import argparse
from difflib import unified_diff
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = Path("plugins/stream-deck")
MANIFEST = PLUGIN / "io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/manifest.json"


def _version(value: str, *, plugin: bool = False) -> tuple[int, ...]:
    """Validate a product version and return its numeric release ordering."""
    match = re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:(a|b|rc)(0|[1-9]\d*))?",
        value,
    )
    if match is None or (plugin and match[4]):
        raise ValueError("Expected X.Y.Z (application also accepts aN, bN or rcN)")
    parts = tuple(int(match[index]) for index in (1, 2, 3))
    if any(part > 65535 for part in parts):
        raise ValueError("Version components must not exceed 65535")
    return (*parts, {"a": 0, "b": 1, "rc": 2, None: 3}[match[4]], int(match[5] or 0))


class ReleaseEdits:
    """Collect validated text edits before changing any working-tree files.

    Attributes:
        root: Repository root containing release metadata.
        originals: Original bytes retained for write-failure recovery.
        contents: Proposed UTF-8 contents, preserving original line endings.
    """

    def __init__(self, root: Path) -> None:
        """Create an empty edit plan for a repository root.

        Args:
            root: Checkout or isolated test repository.
        """
        self.root = root
        self.originals: dict[Path, bytes] = {}
        self.contents: dict[Path, str] = {}

    def read(self, relative: str | Path) -> str:
        """Read a file once, including any pending edits.

        Args:
            relative: Repository-relative text file.

        Returns:
            Pending or original UTF-8 text.
        """
        path = Path(relative)
        if path not in self.contents:
            self.originals[path] = (self.root / path).read_bytes()
            self.contents[path] = self.originals[path].decode("utf-8")
        return self.contents[path]

    def replace(self, relative: str | Path, pattern: str, value: str, *, count: int = 1) -> None:
        """Replace an exact number of known version fields, rejecting drift.

        Args:
            relative: Repository-relative text file.
            pattern: Regular expression with the editable value in group one.
            value: Explicitly selected replacement value.
            count: Expected match count; zero requires at least one match.

        Raises:
            ValueError: A required version field is missing or ambiguous.
        """
        text = self.read(relative)
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        if not matches or (count and len(matches) != count):
            raise ValueError(f"Unexpected version fields in {relative}: {len(matches)}")
        for match in reversed(matches):
            text = text[: match.start(1)] + value + text[match.end(1) :]
        self.contents[Path(relative)] = text

    def apply(self, *, dry_run: bool = False) -> list[Path]:
        """Preview or write all validated edits, restoring originals on write errors.

        Args:
            dry_run: Print unified diffs without writing.

        Returns:
            Relative paths whose contents changed.

        Raises:
            OSError: Writing failed; originals are restored where possible.
        """
        changed = [
            path
            for path, text in self.contents.items()
            if text.encode("utf-8") != self.originals[path]
        ]
        if dry_run:
            for path in changed:
                print(
                    "".join(
                        unified_diff(
                            self.originals[path].decode("utf-8").splitlines(keepends=True),
                            self.contents[path].splitlines(keepends=True),
                            fromfile=path.as_posix(),
                            tofile=path.as_posix(),
                        ),
                    ),
                    end="",
                )
            return changed
        written: list[Path] = []
        try:
            for path in changed:
                written.append(path)
                (self.root / path).write_bytes(self.contents[path].encode("utf-8"))
        except OSError:
            for path in reversed(written):
                try:
                    (self.root / path).write_bytes(self.originals[path])
                except OSError as error:
                    print(f"Could not restore {path}: {error}", file=sys.stderr)
            raise
        return changed


def prepare_versions(
    root: Path,
    *,
    app: str | None = None,
    plugin: str | None = None,
) -> ReleaseEdits:
    """Validate selected product versions and prepare synchronized metadata edits.

    Args:
        root: Repository root.
        app: Explicit application target, or None to leave it unchanged.
        plugin: Explicit independent plugin target, or None to leave it unchanged.

    Returns:
        Validated edit plan; no files have been written.

    Raises:
        ValueError: Input, current metadata or expected version fields are invalid.
    """
    edits = ReleaseEdits(root)
    if app is not None:
        previous = tomllib.loads(edits.read("pyproject.toml"))["project"]["version"]
        if _version(app) < _version(previous):
            raise ValueError("Application version must not decrease")
        edits.replace(
            "pyproject.toml",
            r'^\[project\]\r?\nname = "ride-forces-analyzer"\r?\nversion = "([^"]+)"\r?$',
            app,
        )
        edits.replace(
            "src/ride_forces_analyzer/__init__.py",
            rf'^__version__ = "({re.escape(previous)})"\r?$',
            app,
        )
        edits.replace(
            "uv.lock",
            rf'^name = "ride-forces-analyzer"\r?\nversion = "({re.escape(previous)})"\r?$',
            app,
        )
        edits.replace(
            "README.md",
            rf"^Version \*\*({re.escape(previous)})\*\* is a (?:stable|preview) release\.",
            app,
        )
        status = "preview" if _version(app)[0] == 0 or _version(app)[3] < 3 else "stable"
        edits.replace(
            "README.md",
            rf"^Version \*\*{re.escape(app)}\*\* is a (stable|preview) release\.",
            status,
        )
    if plugin is not None:
        previous = json.loads(edits.read(PLUGIN / "package.json"))["version"]
        if _version(plugin, plugin=True) < _version(previous, plugin=True):
            raise ValueError("Plugin version must not decrease")
        edits.replace(PLUGIN / "package.json", rf'"version": "({re.escape(previous)})"', plugin)
        edits.replace(MANIFEST, rf'"Version": "({re.escape(previous)}\.0)"', f"{plugin}.0")
        edits.replace(
            "package-lock.json",
            rf'"plugins/stream-deck": \{{\r?\n\s*"name": "@ride-forces-analyzer/stream-deck",\r?\n\s*"version": "({re.escape(previous)})"',
            plugin,
        )
    return edits


def prepare_interfaces(
    edits: ReleaseEdits,
    *,
    control: int | None = None,
    transport: int | None = None,
) -> None:
    """Synchronize only explicitly approved Stream Deck interface version targets.

    Args:
        edits: Pending product-version edits or an empty repository edit plan.
        control: Owner-approved application protocol target; None preserves its lock.
        transport: Owner-approved discovery/authentication target.

    Raises:
        ValueError: Target decreases a version or a synchronized field has drifted.
    """
    for target, filename, constant in (
        (control, "runtime/control_contract.py", "PROTOCOL_VERSION"),
        (transport, "runtime/stream_deck.py", "TRANSPORT_VERSION"),
    ):
        if target is None:
            continue
        source = f"src/ride_forces_analyzer/{filename}"
        match = re.search(rf"^{constant} = ([0-9]+)\r?$", edits.read(source), re.MULTILINE)
        if match is None or type(target) is not int or target < 1 or target < int(match[1]):
            raise ValueError(f"Invalid or decreasing {constant} target")
        previous = int(match[1])
        edits.replace(source, rf"^{constant} = ({previous})\r?$", str(target))
        if constant == "PROTOCOL_VERSION":
            edits.replace(
                PLUGIN / "src/protocol.ts",
                rf"^export const PROTOCOL_VERSION = ({previous});\r?$",
                str(target),
            )
            edits.replace(
                "tests/fixtures/stream_deck_protocol.json",
                rf'"version": ({previous})\b',
                str(target),
                count=0,
            )
            test = "tests/support/test_control_contract.py"
            edits.replace(test, rf"Protocol version ({previous}) is owner-approved", str(target))
            edits.replace(test, rf"assert PROTOCOL_VERSION == ({previous}), message", str(target))
            edits.replace(test, rf"PROTOCOL_VERSION = ({previous});", str(target))

            edits.replace(
                "docs/architecture/06_runtime_view.md",
                rf"Application protocol `version: ({previous})`",
                str(target),
            )
            edits.replace(
                "docs/architecture/06_runtime_view.md",
                rf"The upcoming release uses protocol ({previous}),",
                str(target),
            )
            edits.replace(
                "docs/implementation/STREAM_DECK.md",
                rf"application protocol version ({previous})\.",
                str(target),
            )
            edits.replace(
                PLUGIN / "README.md",
                rf"Application protocol ({previous}) carries",
                str(target),
            )
        else:
            edits.replace(
                PLUGIN / "src/transport.ts",
                rf"\bversion(?:: | !== )({previous})\b",
                str(target),
                count=5,
            )
            edits.replace(
                "docs/architecture/06_runtime_view.md",
                rf"discovery/authentication version ({previous})\.",
                str(target),
            )
            edits.replace(
                "docs/implementation/STREAM_DECK.md",
                rf"Discovery/authentication version ({previous});",
                str(target),
            )
            edits.replace(
                PLUGIN / "README.md",
                rf"discovery/authentication stays at ({previous})\.",
                str(target),
            )


def refresh_screenshots(root: Path) -> None:
    """Run existing reference generators sequentially after version preparation.

    Args:
        root: Repository containing the updated version files and generators.

    Raises:
        OSError: A generator cannot start or the image guide cannot be written.
        ValueError: The image guide's version statement has changed unexpectedly.
        subprocess.SubprocessError: A generator fails or exceeds its time limit.
    """
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    guide = ReleaseEdits(root)
    guide.replace(
        "docs/images/README.md",
        r"^Workspace and appearance screenshots show version ([^\r\n]+)\.\r?$",
        version,
    )
    for arguments in (
        ("scripts/generate_app_screenshots.py",),
        ("scripts/generate_app_screenshots.py", "--details"),
        ("scripts/generate_app_screenshots.py", "--themes"),
        ("scripts/generate_export_screenshots.py",),
        ("scripts/generate_stream_deck_screenshots.py",),
    ):
        print(f"Refreshing screenshots: {' '.join(arguments)}", flush=True)
        subprocess.run([sys.executable, *arguments], cwd=root, check=True, timeout=300)
    guide.apply()


def main() -> None:
    """Prepare explicit version targets and refresh references, or preview metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-version")
    parser.add_argument("--plugin-version")
    parser.add_argument(
        "--control-protocol",
        type=int,
        help="Explicit owner-approved application protocol target",
    )
    parser.add_argument(
        "--transport-protocol",
        type=int,
        help="Explicit owner-approved discovery/authentication target",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    args = parser.parse_args()
    if all(
        value is None
        for value in (
            args.app_version,
            args.plugin_version,
            args.control_protocol,
            args.transport_protocol,
        )
    ):
        parser.error("Select at least one explicit version target")
    try:
        edits = prepare_versions(ROOT, app=args.app_version, plugin=args.plugin_version)
        prepare_interfaces(edits, control=args.control_protocol, transport=args.transport_protocol)
        changed = edits.apply(dry_run=args.dry_run)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{'Previewed' if args.dry_run else 'Updated'} {len(changed)} files.", flush=True)
    if not args.dry_run:
        try:
            refresh_screenshots(ROOT)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            parser.exit(
                1,
                f"Screenshot refresh failed: {error}\n"
                "Version edits and any generated images are retained for inspection. "
                "Fix the failure and rerun the same preparation command.\n",
            )
        print("Reference screenshots refreshed.")
    print(
        "Run the affected project checks before delivery; no Git operations or publication were performed.",
    )


if __name__ == "__main__":
    main()
