"""Build Windows x64 EXE, standard ZIP and complete ZIP release candidates.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words filevers prodvers

import argparse
from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from urllib.request import urlopen
from zipfile import ZipFile, ZIP_DEFLATED

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from ride_forces_analyzer.ui.presentation.icons import ICON_SOURCE
from scripts.build_icons import build_icons
from scripts.license_bundle import BUNDLE_NAME, LicenseBundle, read_notice

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Ride-Forces-Analyzer"
PRODUCT_NAME = "Ride Forces Analyzer"
DESCRIPTION = "Ride force analysis and video overlays"
AUTHOR = "Björn Rudner"
COPYRIGHT = "Copyright © 2026 Björn Rudner"


def write_version_info(destination: Path, version: str) -> Path:
    """Write PyInstaller's UTF-8 Windows version resource from the project version.

    Release components fill the four 16-bit binary fields; the full version text
    retains prerelease suffixes. Reject values Windows cannot represent.

    Args:
        destination: Requested output path; replacement follows the explicit overwrite
            policy.
        version: Version string to format or validate.

    Returns:
        Path to the generated Windows version-resource file.

    Raises:
        ValueError: Version exceeds Windows resource limits.
        OSError: If the required filesystem operation fails.
    """
    parsed = Version(version)
    if len(parsed.release) > 4 or any(part > 65535 for part in parsed.release):
        raise ValueError("Version exceeds Windows resource limits")
    numeric = parsed.release + (0,) * (4 - len(parsed.release))
    fields = {
        "CompanyName": AUTHOR,
        "FileDescription": DESCRIPTION,
        "FileVersion": version,
        "InternalName": APP_NAME,
        "LegalCopyright": COPYRIGHT,
        "OriginalFilename": f"{APP_NAME}.exe",
        "ProductName": PRODUCT_NAME,
        "ProductVersion": version,
    }
    strings = ",\n".join(f"StringStruct({key!r}, {value!r})" for key, value in fields.items())
    destination.write_text(
        "VSVersionInfo(\n"
        f"ffi=FixedFileInfo(filevers={numeric!r}, prodvers={numeric!r}, "
        f"flags={2 if parsed.is_prerelease else 0}),\n"
        "kids=[StringFileInfo([StringTable('040904B0', [\n"
        f"{strings}\n"
        "])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])\n",
        encoding="utf-8",
    )
    return destination


def digest(path: Path) -> str:
    """Calculate a file's SHA-256 digest using bounded reads.

    Args:
        path: Filesystem path read or written by this operation.

    Returns:
        Hexadecimal SHA-256 digest of the file.

    Raises:
        OSError: If the required filesystem operation fails.
    """
    result = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def runtime_distributions() -> list[metadata.Distribution]:
    """Collect notices for the declared runtime/extras, never the dev environment.

    Returns:
        Installed distributions belonging to the declared runtime dependency set.
    """
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


def collect_notices(destination: Path) -> LicenseBundle:
    """Write the installed runtime inventory and deduplicated upstream license texts.

    Args:
        destination: Single UTF-8 notice file to create.

    Returns:
        Collection reusable when adding Complete-package FFmpeg notices.

    Raises:
        OSError: An upstream notice cannot be read.
        ValueError: A runtime component or Python license has no notice text.
    """
    bundle = LicenseBundle()
    for distribution in sorted(
        runtime_distributions(),
        key=lambda item: canonicalize_name(item.metadata["Name"]),
    ):
        name = canonicalize_name(distribution.metadata["Name"])
        declared = distribution.metadata.get("License-Expression") or "Included upstream notices"
        sources: list[tuple[str, str, str]] = []
        for entry in sorted(distribution.files or [], key=str):
            if (
                not any(
                    token in entry.name.lower()
                    for token in ("license", "copying", "notice", "authors")
                )
                and "licenses" not in entry.parts
            ):
                continue
            source = Path(str(distribution.locate_file(entry)))
            if source.is_file():
                kind = (
                    declared
                    if re.fullmatch(r"[A-Za-z0-9.-]+", declared)
                    else "Additional component notices"
                )
                sources.append((entry.as_posix(), kind, read_notice(source)))
        if license_text := distribution.metadata.get("License"):
            sources.append(("METADATA License field", "Additional component notices", license_text))
        bundle.add(name, distribution.version, declared, sources)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        python_license = (
            Path(sys.base_prefix)
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "LICENSE.txt"
        )
    if not python_license.is_file():
        raise ValueError("Python runtime license is missing")
    bundle.add(
        "Python",
        platform.python_version(),
        "PSF and bundled-component terms",
        [("Python LICENSE.txt", "Python and bundled-component terms", read_notice(python_license))],
    )
    qt = re.split(
        r"^===== (.+) =====\n",
        read_notice(ROOT / "packaging/QT-NOTICES.txt"),
        flags=re.MULTILINE,
    )
    qt_sources = [("QT-NOTICES introduction", "Qt scope", qt[0])]
    for qt_source, text in zip(qt[1::2], qt[2::2], strict=True):
        kind = Path(qt_source).stem if "/LICENSES/" in qt_source else "Additional component notices"
        qt_sources.append((qt_source, kind, text))
    bundle.add(
        "Qt/PySide source notices",
        metadata.version("PySide6"),
        "Module-specific upstream terms",
        qt_sources,
    )
    bundle.add(
        "Redistribution catalog",
        "",
        "Accepted delivery scope and limitations",
        [
            (
                "packaging/redistribution.json",
                "Redistribution scope",
                read_notice(ROOT / "packaging/redistribution.json"),
            ),
        ],
    )
    bundle.write(destination)
    return bundle


def acquire_ffmpeg(work: Path) -> Path:
    """Verify and extract the configured publisher's FFmpeg binary archive.

    Args:
        work: Temporary build directory inside the repository's temporary area.

    Returns:
        Path to the verified, extracted encoder executable.

    Raises:
        OSError: If the required filesystem operation fails.
        ValueError: FFmpeg publisher archive checksum mismatch. FFmpeg archive must
            contain exactly one encoder.
        subprocess.CalledProcessError: If the checked subprocess exits unsuccessfully.
    """
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
    """Write the prepared package directory as a ZIP archive.

    Args:
        folder: Directory to inspect.
        output: Output directory or path for generated artifacts.

    Returns:
        None.
    """
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, (Path(APP_NAME) / path.relative_to(folder)).as_posix())


def validate_redistribution(manifest: Path) -> None:
    """Verify the supplied source archives against the manifest.

    Args:
        manifest: Manifest describing the package contents.

    Returns:
        None.

    Raises:
        OSError: If the required filesystem operation fails.
        ValueError: Source archives must be a list. Corresponding-source downloads must
            stay under .tmp. Corresponding-source archive is missing or changed.
    """
    value = json.loads(manifest.read_text(encoding="utf-8"))
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
    """Build the platform's native release package and checksum inventory.

    Args:
        work: Temporary build directory inside the repository's temporary area.
        release: Whether to apply the release source-archive verification gate.

    Returns:
        Path to the generated distribution artifact.

    Raises:
        ValueError: Build on native Windows x64. Build outputs must stay under .tmp. If
            the supplied settings or operation state are invalid. Non-redistributable
            FFmpeg build.
        OSError: If the required filesystem operation fails.
        subprocess.CalledProcessError: If the checked subprocess exits unsuccessfully.
    """
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
    notices = work / BUNDLE_NAME
    bundle = collect_notices(notices)
    icons = build_icons(work / "icons")
    version_info = write_version_info(work / "version-info.txt", version)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onefile",
            "--windowed",
            "--noupx",
            "--icon",
            str(icons / "app-icon.ico"),
            "--version-file",
            str(version_info),
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
            "--hidden-import",
            "ride_forces_analyzer.storage.library",
            "--hidden-import",
            "sqlalchemy.dialects.sqlite",
            "--add-data",
            f"{ROOT / 'src/ride_forces_analyzer/storage/library_migrations'}:ride_forces_analyzer/storage/library_migrations",
            "--additional-hooks-dir",
            str(ROOT / "packaging/hooks"),
            "--add-data",
            f"{ICON_SOURCE}:ride_forces_analyzer/ui/presentation",
            "--add-data",
            f"{ROOT / 'src/ride_forces_analyzer/rendering/pov'}:ride_forces_analyzer/rendering/pov",
            "--add-data",
            f"{ROOT / 'ASSET_LICENSES.md'}:ride_forces_analyzer/rendering/pov",
            "--add-data",
            f"{notices}:.",
            "--add-data",
            f"{ROOT / 'LICENSE'}:.",
            "--add-data",
            f"{ROOT / 'THIRD_PARTY_NOTICES.md'}:.",
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
    (assets / "corresponding-sources.zip").unlink(missing_ok=True)
    prefix = f"{APP_NAME}-{version}-windows-x64"
    shutil.copyfile(executable, assets / f"{prefix}.exe")
    standard = work / "standard"
    if standard.exists():
        shutil.rmtree(standard)
    standard.mkdir()
    shutil.copyfile(executable, standard / f"{APP_NAME}.exe")
    for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md", "ASSET_LICENSES.md"):
        shutil.copyfile(ROOT / filename, standard / filename)
    shutil.copyfile(notices, standard / BUNDLE_NAME)
    (standard / "START-HERE.txt").write_text(
        "Start Ride-Forces-Analyzer.exe. No Python installation is needed.\n"
        "Standard: choose your own ffmpeg.exe for video exports.\n"
        "Complete: ffmpeg.exe beside the application is detected automatically.\n"
        "Preferences are stored in LOCALAPPDATA, not in this folder.\n"
        "See THIRD-PARTY-LICENSES.txt for library licenses; LICENSE for the app. No warranty.\n",
        encoding="utf-8",
    )
    write_zip(standard, assets / f"{prefix}-standard.zip")
    complete = work / "complete"
    if complete.exists():
        shutil.rmtree(complete)
    shutil.copytree(standard, complete)
    shutil.copyfile(encoder, complete / "ffmpeg.exe")
    encoder_notices: list[tuple[str, str, str]] = []
    for filename in ("LICENSE", "README.txt"):
        source = encoder.parent.parent / filename
        if not source.is_file():
            raise ValueError(f"Publisher FFmpeg notice missing: {filename}")
        encoder_notices.append(
            (f"FFmpeg/{filename}", "FFmpeg publisher notices", read_notice(source)),
        )
    for option in ("-L", "-buildconf"):
        result = subprocess.run(
            [str(encoder), option],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=30,
        )
        text = result.stdout + result.stderr
        if option == "-buildconf" and "--enable-nonfree" in text:
            raise ValueError("Non-redistributable FFmpeg build")
        encoder_notices.append(
            (f"FFmpeg/{option.lstrip('-')}.txt", "FFmpeg build information", text),
        )
    encoder_version = json.loads((ROOT / "ffmpeg.json").read_text(encoding="utf-8"))["version"]
    bundle.add(
        "FFmpeg",
        encoder_version,
        "Publisher license and actual build information",
        encoder_notices,
    )
    bundle.write(complete / BUNDLE_NAME)
    write_zip(complete, assets / f"{prefix}-complete.zip")
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
