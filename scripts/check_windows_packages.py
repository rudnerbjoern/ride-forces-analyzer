"""Verify and execute the actual Windows release candidates in isolated folders.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.build_windows import APP_NAME, ROOT, digest


def validate_zip(path: Path, *, complete: bool) -> None:
    """Validate Windows ZIP paths, required notices and package contents.

    Args:
        path: Filesystem path read or written by this operation.
        complete: Whether the package is expected to include the bundled encoder.

    Returns:
        None.

    Raises:
        ValueError: Duplicate package entries. Unsafe package entry. Private or
            development data in package. Standard package unexpectedly bundles FFmpeg.
            Missing executable or notices. Corrupt ZIP member.
    """
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate package entries")
        for name in names:
            parts = name.replace("\\", "/").split("/")
            if parts[0] != APP_NAME or any(
                part in ("..", ".", "") or ":" in part for part in parts
            ):
                raise ValueError("Unsafe package entry")
            if any(part in (".git", ".venv", "node_modules") for part in parts) or name.endswith(
                (".forces", ".sqlite3"),
            ):
                raise ValueError("Private or development data in package")
        required = {
            f"{APP_NAME}/{APP_NAME}.exe",
            f"{APP_NAME}/LICENSE",
            f"{APP_NAME}/THIRD_PARTY_NOTICES.md",
            f"{APP_NAME}/licenses/inventory.json",
            f"{APP_NAME}/licenses/PYTHON-LICENSE.txt",
            f"{APP_NAME}/licenses/QT-NOTICES.txt",
            f"{APP_NAME}/licenses/REDISTRIBUTION.json",
        }
        if complete:
            required |= {
                f"{APP_NAME}/ffmpeg.exe",
                f"{APP_NAME}/licenses/ffmpeg/LICENSE",
                f"{APP_NAME}/licenses/ffmpeg/README.txt",
                f"{APP_NAME}/licenses/ffmpeg/buildconf.txt",
            }
        elif any(name.lower().endswith("/ffmpeg.exe") for name in names):
            raise ValueError("Standard package unexpectedly bundles FFmpeg")
        if not required <= set(names):
            raise ValueError("Missing executable or notices")
        if archive.testzip() is not None:
            raise ValueError("Corrupt ZIP member")


def check(assets: Path, recording: Path) -> None:
    """Run the configured package or update checks and report their result.

    Args:
        assets: Directory containing the native package assets to verify.
        recording: Path of the source recording.

    Returns:
        None.

    Raises:
        ValueError: Choose an existing recording for package verification. Windows
            artifact checksum mismatch. Duplicate checksum entry. Windows checksum
            inventory is incomplete. Expected one EXE, standard ZIP and complete ZIP. If
            the supplied settings or operation state are invalid.
        OSError: If the required filesystem operation fails.
    """
    if not recording.is_file():
        raise ValueError("Choose an existing recording for package verification")
    assets = assets.resolve()
    checksum = assets / "WINDOWS-SHA256SUMS.txt"
    recorded: set[str] = set()
    for line in checksum.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if Path(name).name != name or digest(assets / name) != expected:
            raise ValueError("Windows artifact checksum mismatch")
        if name in recorded:
            raise ValueError("Duplicate checksum entry")
        recorded.add(name)
    if recorded != {path.name for path in assets.iterdir() if path.suffix in (".exe", ".zip")}:
        raise ValueError("Windows checksum inventory is incomplete")
    executables = list(assets.glob("*.exe"))
    standards = list(assets.glob("*-standard.zip"))
    completes = list(assets.glob("*-complete.zip"))
    if len(executables) != 1 or len(standards) != 1 or len(completes) != 1:
        raise ValueError("Expected one EXE, standard ZIP and complete ZIP")
    for path, complete in ((standards[0], False), (completes[0], True)):
        validate_zip(path, complete=complete)
    with TemporaryDirectory(dir=ROOT / ".tmp", prefix="windows-smoke-") as temporary:
        root = Path(temporary)
        for kind, source in (
            ("exe", executables[0]),
            ("standard", standards[0]),
            ("complete", completes[0]),
        ):
            folder = root / kind
            folder.mkdir()
            if kind == "exe":
                executable = folder / source.name
                shutil.copyfile(source, executable)
            else:
                with ZipFile(source) as archive:
                    archive.extractall(folder)
                executable = folder / APP_NAME / f"{APP_NAME}.exe"
            report = root / f"{kind}.json"
            environment = {
                key: value
                for key, value in os.environ.items()
                if key
                not in {"PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"}
            }
            environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
            environment["LOCALAPPDATA"] = str(root / f"{kind}-preferences")
            arguments = [
                str(executable),
                "--self-test",
                str(report),
                "--recording",
                str(recording.resolve()),
            ]
            if kind == "complete":
                arguments.append("--with-ffmpeg")
            process = subprocess.run(
                arguments,
                cwd=folder,
                env=environment,
                check=False,
                timeout=120,
            )
            if not report.is_file():
                raise ValueError(
                    f"Frozen {kind} failed before producing diagnostics (exit {process.returncode})",
                )
            verification = assets.parent / "verification"
            verification.mkdir(exist_ok=True)
            shutil.copyfile(report, verification / report.name)
            result = json.loads(report.read_text(encoding="utf-8"))
            if process.returncode != 0:
                raise ValueError(f"Frozen {kind} self-test failed: {result}")
            if (
                result.get("passed") is not True
                or result.get("render") is not True
                or (kind == "complete" and result.get("encode") is not True)
            ):
                raise ValueError(f"Frozen {kind} self-test failed: {result}")
            print(f"PASS {kind}: {json.dumps(result)}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("--recording", required=True, type=Path)
    arguments = parser.parse_args()
    check(arguments.assets, arguments.recording)
