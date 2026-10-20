"""Extract and execute native Linux/macOS packages without a source Python runtime.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words codesign

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import stat
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from ride_forces_analyzer import __version__
from ride_forces_analyzer.runtime_paths import runtime_target
from scripts.build_windows import APP_NAME, ROOT, digest


def validate_member(name: str, target: str | None = None) -> None:
    """Reject escaping archive paths, links and recording/development data."""
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or not path.parts
        or ":" in name
        or any(part in (".git", ".venv", "node_modules") for part in path.parts)
        or path.suffix in (".forces", ".sqlite3")
    ):
        raise ValueError("Unsafe or private package member")
    if target is not None:
        resolved = posixpath.normpath(str(path.parent / target))
        if (
            target.startswith("/")
            or "\\" in target
            or resolved == ".."
            or resolved.startswith("../")
        ):
            raise ValueError("Package link escapes its extraction directory")


def extract(archive: Path, destination: Path) -> None:
    """Preserve executable permissions and app-framework links on the native OS."""
    if archive.name.endswith(".tar.gz"):
        with tarfile.open(archive) as source:
            members = source.getmembers()
            if len({entry.name for entry in members}) != len(members):
                raise ValueError("Duplicate package member")
            for entry in members:
                validate_member(entry.name, entry.linkname if entry.issym() else None)
            source.extractall(destination, filter="data")
    else:
        with ZipFile(archive) as source:
            members = source.infolist()
            if len({entry.filename for entry in members}) != len(members):
                raise ValueError("Duplicate package member")
            for entry in members:
                target = (
                    source.read(entry).decode("utf-8")
                    if stat.S_ISLNK(entry.external_attr >> 16)
                    else None
                )
                validate_member(entry.filename, target)
        subprocess.run(
            ["ditto", "-x", "-k", str(archive), str(destination)],
            check=True,
            timeout=120,
        )


def check(assets: Path, recording: Path, *, expected_target: str | None = None) -> None:
    """Check hashes, notices, native GUI/import/rendering and an external CPU encode."""
    target = runtime_target()
    if target not in ("linux-x64", "macos-x64", "macos-arm64"):
        raise ValueError("Check on native Linux x64 or macOS x64/arm64")
    if expected_target is not None and expected_target != target:
        raise ValueError("Package target does not match the native checker")
    assets, recording = assets.resolve(), recording.resolve()
    if not recording.is_file():
        raise ValueError("Choose an existing recording")
    extension = ".tar.gz" if target == "linux-x64" else ".zip"
    filename = f"{APP_NAME}-{__version__}-{target}{extension}"
    archive = assets / filename
    expected_checksum = f"{digest(archive)}  {filename}"
    if (assets / f"{target.upper()}-SHA256SUMS.txt").read_text(
        encoding="utf-8",
    ).strip() != expected_checksum:
        raise ValueError("Native package checksum mismatch")
    encoder = shutil.which("ffmpeg")
    if encoder is None:
        raise ValueError("Install an external FFmpeg for the native package encode check")
    with TemporaryDirectory(dir=ROOT / ".tmp", prefix="native-smoke-") as temporary:
        root = Path(temporary)
        payload = root / "payload"
        payload.mkdir()
        extract(archive, payload)
        macos = target.startswith("macos-")
        bundle = payload / (f"{APP_NAME}.app" if macos else APP_NAME)
        executable = bundle / "Contents/MacOS" / APP_NAME if macos else bundle / APP_NAME
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("Extracted executable or its execute permission is missing")
        licenses = (
            bundle / "Contents/Resources/licenses" if macos else bundle / "_internal/licenses"
        )
        for name in (
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
            "third-party/inventory.json",
            "third-party/PYTHON-LICENSE.txt",
            "third-party/QT-NOTICES.txt",
            "third-party/REDISTRIBUTION.json",
        ):
            if not (licenses / name).is_file():
                raise ValueError(f"Missing native package notice: {name}")
        if macos:
            subprocess.run(
                ["codesign", "--verify", "--deep", "--strict", str(bundle)],
                check=True,
                timeout=120,
            )
        environment = dict(os.environ)
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "QT_PLUGIN_PATH",
            "QT_QPA_PLATFORM_PLUGIN_PATH",
            "QT_QPA_PLATFORM",
            "LD_LIBRARY_PATH",
            "LD_LIBRARY_PATH_ORIG",
            "DYLD_LIBRARY_PATH",
            "DYLD_FRAMEWORK_PATH",
        ):
            environment.pop(name, None)
        environment["PATH"] = "/usr/bin:/bin"
        environment["HOME"] = str(root / "home")
        Path(environment["HOME"]).mkdir()
        environment["XDG_DATA_HOME"] = str(root / "data")
        environment["XDG_CONFIG_HOME"] = str(root / "config")
        environment["XDG_CACHE_HOME"] = str(root / "cache")
        report = root / "report.json"
        process = subprocess.run(
            [
                str(executable),
                "--self-test",
                str(report),
                "--recording",
                str(recording),
                "--with-ffmpeg",
                "--ffmpeg",
                str(Path(encoder).resolve()),
            ],
            cwd=Path("/"),
            env=environment,
            check=False,
            timeout=180,
        )
        if not report.is_file():
            raise ValueError(f"Native package produced no report (exit {process.returncode})")
        result = json.loads(report.read_text(encoding="utf-8"))
        verification = assets.parent / "verification"
        verification.mkdir(exist_ok=True)
        shutil.copyfile(report, verification / f"{target}.json")
        if (
            process.returncode != 0
            or result.get("version") != __version__
            or not all(
                result.get(name) is True
                for name in ("passed", "gui", "german_light", "render", "encode")
            )
        ):
            raise ValueError(f"Native package self-test failed: {result}")
        print(f"PASS {target}: {json.dumps(result)}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("--recording", required=True, type=Path)
    parser.add_argument("--expected-target")
    args = parser.parse_args()
    check(args.assets, args.recording, expected_target=args.expected_target)
