"""Build Windows x64 EXE, standard ZIP and complete ZIP release candidates.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib
from urllib.request import urlopen
from zipfile import ZipFile, ZIP_DEFLATED

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Ride-Forces-Analyzer"


def digest(path: Path) -> str:
    result = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def runtime_distributions() -> list[metadata.Distribution]:
    """Collect notices for the declared runtime/extras, never the dev environment."""
    pending = ["ride-forces-analyzer", "pyinstaller"]
    seen: set[str] = set()
    result: list[metadata.Distribution] = []
    while pending:
        name = canonicalize_name(pending.pop())
        if name in seen:
            continue
        seen.add(name)
        distribution = metadata.distribution(name)
        result.append(distribution)
        # The bundler's bootloader exception is shipped; its build dependencies
        # are not bundled in the application and do not belong in runtime notices.
        if name == "pyinstaller":
            continue
        for value in distribution.requires or []:
            requirement = Requirement(value)
            if requirement.marker is None or any(
                requirement.marker.evaluate({"extra": extra})
                for extra in ("", "analysis", "render")
            ):
                pending.append(requirement.name)
    return result


def collect_notices(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    inventory: list[dict[str, object]] = []
    for distribution in runtime_distributions():
        name = canonicalize_name(distribution.metadata["Name"])
        folder = destination / name
        folder.mkdir(exist_ok=True)
        notices: list[str] = []
        for entry in distribution.files or []:
            if (
                not any(
                    token in entry.name.lower()
                    for token in ("license", "copying", "notice", "authors")
                )
                and "licenses" not in entry.parts
            ):
                continue
            source = Path(str(distribution.locate_file(entry)))
            if not source.is_file():
                continue
            # Preserve paths inside each distribution and avoid name collisions.
            relative = Path(*[part for part in entry.parts if part not in ("..", ".")])
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            notices.append(target.relative_to(destination).as_posix())
        (folder / "METADATA.txt").write_text(
            distribution.read_text("METADATA") or "",
            encoding="utf-8",
        )
        inventory.append({"name": name, "version": distribution.version, "notice_files": notices})
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise ValueError("Python runtime license is missing")
    shutil.copyfile(python_license, destination / "PYTHON-LICENSE.txt")
    shutil.copyfile(ROOT / "packaging/QT-NOTICES.txt", destination / "QT-NOTICES.txt")
    shutil.copyfile(ROOT / "packaging/redistribution.json", destination / "REDISTRIBUTION.json")
    (destination / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")


def acquire_ffmpeg(work: Path) -> Path:
    configuration = json.loads((ROOT / "ffmpeg.json").read_text(encoding="utf-8"))
    archive = ROOT / ".tmp/ffmpeg-full.7z"
    if not archive.is_file() or digest(archive) != configuration["sha256"]:
        url = f"https://github.com/GyanD/codexffmpeg/releases/download/{configuration['version']}/ffmpeg-{configuration['version']}-full_build.7z"
        with urlopen(url, timeout=60) as response, archive.open("wb") as target:
            shutil.copyfileobj(response, target)
    if digest(archive) != configuration["sha256"]:
        raise ValueError("FFmpeg publisher archive checksum mismatch")
    extracted = work / "ffmpeg-distribution"
    extracted.mkdir(exist_ok=True)
    subprocess.run(["tar.exe", "-xf", str(archive), "-C", str(extracted)], check=True, timeout=120)
    candidates = list(extracted.glob("*/bin/ffmpeg.exe"))
    if len(candidates) != 1:
        raise ValueError("FFmpeg archive must contain exactly one encoder")
    return candidates[0]


def write_zip(folder: Path, output: Path) -> None:
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, (Path(APP_NAME) / path.relative_to(folder)).as_posix())


def validate_redistribution(manifest: Path) -> None:
    """Verify supplied source files; report documented gaps without blocking builds."""
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if value.get("status") != "verified":
        print("NOTICE: Redistribution material has documented open items:", flush=True)
        for item in value.get("open_items", []):
            print(f"- {item}", flush=True)
    sources = value.get("source_archives")
    if not isinstance(sources, list):
        raise ValueError("Source archives must be a list")
    for entry in sources:
        path = ROOT / entry["path"]
        if not path.resolve().is_relative_to(ROOT / ".tmp"):
            raise ValueError("Corresponding-source downloads must stay under .tmp")
        if (
            not path.is_file()
            and isinstance(entry.get("url"), str)
            and entry["url"].startswith("https://")
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            with urlopen(entry["url"], timeout=60) as response, path.open("wb") as target:
                shutil.copyfileobj(response, target)
        if not path.is_file() or digest(path) != entry["sha256"]:
            raise ValueError("Corresponding-source archive is missing or changed")


def build(work: Path, *, release: bool = False) -> Path:
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise ValueError("Build on native Windows x64")
    work = work.resolve()
    if not work.is_relative_to(ROOT / ".tmp"):
        raise ValueError("Build outputs must stay under .tmp")
    if release:
        validate_redistribution(ROOT / "packaging/redistribution.json")
    work.mkdir(parents=True, exist_ok=True)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    notices = work / "notices"
    collect_notices(notices)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onefile",
            "--windowed",
            "--noupx",
            "--name",
            APP_NAME,
            "--paths",
            str(ROOT / "src"),
            "--paths",
            str(ROOT),
            "--distpath",
            str(work / "bin"),
            "--workpath",
            str(work / "work"),
            "--specpath",
            str(work / "spec"),
            "--collect-data",
            "pint",
            "--add-data",
            f"{notices}:licenses/third-party",
            "--add-data",
            f"{ROOT / 'LICENSE'}:licenses",
            "--add-data",
            f"{ROOT / 'THIRD_PARTY_NOTICES.md'}:licenses",
            str(ROOT / "scripts/windows_entry.py"),
        ],
        cwd=ROOT,
        check=True,
        timeout=1200,
    )
    executable = work / "bin" / f"{APP_NAME}.exe"
    encoder = acquire_ffmpeg(work)
    assets = work / "assets"
    assets.mkdir(exist_ok=True)
    prefix = f"{APP_NAME}-{version}-windows-x64"
    shutil.copyfile(executable, assets / f"{prefix}.exe")
    standard = work / "standard"
    standard.mkdir(exist_ok=True)
    shutil.copyfile(executable, standard / f"{APP_NAME}.exe")
    for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT / filename, standard / filename)
    shutil.copytree(notices, standard / "licenses", dirs_exist_ok=True)
    (standard / "START-HERE.txt").write_text(
        "Start Ride-Forces-Analyzer.exe. No Python installation is needed.\n"
        "Standard: choose your own ffmpeg.exe for video exports.\n"
        "Complete: ffmpeg.exe beside the application is detected automatically.\n"
        "Preferences are stored in LOCALAPPDATA, not in this folder.\n"
        "See LICENSE and THIRD_PARTY_NOTICES.md. No warranty.\n",
        encoding="utf-8",
    )
    write_zip(standard, assets / f"{prefix}-standard.zip")
    complete = work / "complete"
    shutil.copytree(standard, complete, dirs_exist_ok=True)
    shutil.copyfile(encoder, complete / "ffmpeg.exe")
    encoder_notices = complete / "licenses/ffmpeg"
    encoder_notices.mkdir(exist_ok=True)
    for filename in ("LICENSE", "README.txt"):
        source = encoder.parent.parent / filename
        if not source.is_file():
            raise ValueError(f"Publisher FFmpeg notice missing: {filename}")
        shutil.copyfile(source, encoder_notices / filename)
    for option in ("-L", "-buildconf"):
        result = subprocess.run(
            [str(encoder), option],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=30,
        )
        (encoder_notices / f"{option.lstrip('-')}.txt").write_text(
            result.stdout + result.stderr,
            encoding="utf-8",
        )
    if "--enable-nonfree" in (encoder_notices / "buildconf.txt").read_text(encoding="utf-8"):
        raise ValueError("Non-redistributable FFmpeg build")
    write_zip(complete, assets / f"{prefix}-complete.zip")
    if release:
        catalog = json.loads((ROOT / "packaging/redistribution.json").read_text(encoding="utf-8"))
        with ZipFile(
            assets / "corresponding-sources.zip",
            "w",
            compression=ZIP_DEFLATED,
        ) as archive:
            archive.write(ROOT / "packaging/redistribution.json", "redistribution.json")
            archive.writestr(
                "README.txt",
                "This archive contains the available upstream sources.\n"
                "It is not a complete corresponding-source collection.\n"
                "See redistribution.json for documented missing provider material.\n",
            )
            for entry in catalog["source_archives"]:
                source = ROOT / entry["path"]
                archive.write(source, source.name)
    (assets / "WINDOWS-SHA256SUMS.txt").write_text(
        "".join(
            f"{digest(path)}  {path.name}\n"
            for path in sorted(assets.iterdir())
            if path.suffix in (".exe", ".zip")
        ),
        encoding="utf-8",
    )
    print(f"Windows candidates built: {assets}", flush=True)
    for path in sorted(assets.iterdir()):
        print(f"{path.name}: {path.stat().st_size:,} bytes", flush=True)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            for key, name in (
                ("exe", f"{prefix}.exe"),
                ("standard", f"{prefix}-standard.zip"),
                ("complete", f"{prefix}-complete.zip"),
            ):
                stream.write(f"{key}={name}\n")
    return assets


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=ROOT / ".tmp/windows-build")
    parser.add_argument("--release", action="store_true")
    arguments = parser.parse_args()
    build(arguments.work, release=arguments.release)
