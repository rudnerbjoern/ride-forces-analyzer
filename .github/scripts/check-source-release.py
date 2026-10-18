"""Validate a tagged source archive without extracting or modifying its contents.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import tomllib
from zipfile import ZipFile

REQUIRED_FILES = (
    "pyproject.toml",
    "uv.lock",
    "setup.ps1",
    "start.ps1",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "scripts/build_windows.py",
    "scripts/check_windows_packages.py",
    "scripts/windows_entry.py",
    "scripts/windows_smoke.py",
    "scripts/__init__.py",
    "packaging/redistribution.json",
    "packaging/QT-NOTICES.txt",
    "tests/fixtures/real/README.md",
    "tests/fixtures/real/LICENSE-CC-BY-SA-4.0.txt",
    "docs/images/README.md",
    "docs/images/LICENSE-CC-BY-SA-4.0.txt",
)


def validate_archive(archive: Path, tag: str) -> None:
    with ZipFile(archive) as source:
        names = {name for name in source.namelist() if not name.endswith("/")}
        if not set(REQUIRED_FILES) <= names:
            raise ValueError("Source archive lacks required source/license files")
        for name in names:
            parts = Path(name).parts
            if (
                name.startswith("/")
                or ".." in parts
                or any(part in {".venv", "node_modules", ".git", "exports"} for part in parts)
                or (name.startswith(".tmp/") and name != ".tmp/.gitkeep")
                or name.endswith((".exe", ".dll", ".sqlite3", ".mov", ".mp4"))
            ):
                raise ValueError("Source archive contains unexpected local/binary files")
        project = tomllib.loads(source.read("pyproject.toml").decode("utf-8"))["project"]
        if tag != f"v{project['version']}":
            raise ValueError("Release tag does not match project.version")
        if project.get("license") != "GPL-3.0-or-later":
            raise ValueError("Unexpected project license")
        fixtures = json.loads(source.read("tests/fixtures/schema-inventory.json"))["fixtures"]
        expected = {f"tests/fixtures/real/{name}" for name in fixtures}
        if {name for name in names if name.endswith(".forces")} != expected:
            raise ValueError("Recording inventory differs from source archive")
        for name, entry in fixtures.items():
            data = source.read(f"tests/fixtures/real/{name}")
            if len(data) != entry["byte_count"] or sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("Original recording integrity check failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--tag", required=True)
    arguments = parser.parse_args()
    validate_archive(arguments.archive, arguments.tag)
    digest = sha256(arguments.archive.read_bytes()).hexdigest()
    arguments.archive.with_name("SHA256SUMS.txt").write_text(
        f"{digest}  {arguments.archive.name}\n",
        encoding="utf-8",
    )
    print("Source release passed: version, licenses, source-only contents and recording hashes")
