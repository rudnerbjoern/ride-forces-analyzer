"""Build native Linux tarballs and macOS app ZIPs with the locked PyInstaller.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words onedir rideforcesanalyzer codesign Rsrc arcname

import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tarfile
import tomllib

from ride_forces_analyzer.runtime_paths import runtime_target
from scripts.build_windows import APP_NAME, ROOT, collect_notices, digest


def build(work: Path, *, expected_target: str | None = None) -> Path:
    """Build for the native target only; never attempt cross-compilation."""
    target = runtime_target()
    if target not in ("linux-x64", "macos-x64", "macos-arm64"):
        raise ValueError("Build on native Linux x64 or macOS x64/arm64")
    if expected_target is not None and target != expected_target:
        raise ValueError(f"Expected native target {expected_target}, found {target}")
    work = work.resolve()
    if not work.is_relative_to(ROOT / ".tmp"):
        raise ValueError("Build outputs must stay under .tmp")
    work.mkdir(parents=True, exist_ok=True)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    notices = work / "notices"
    collect_notices(notices)
    macos = target.startswith("macos-")
    arguments = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
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
    ]
    if macos:
        arguments += [
            "--windowed",
            "--osx-bundle-identifier",
            "io.github.rudnerbjoern.rideforcesanalyzer",
            "--target-architecture",
            "arm64" if target.endswith("arm64") else "x86_64",
        ]
    arguments.append(str(ROOT / "scripts/windows_entry.py"))
    subprocess.run(
        arguments,
        cwd=ROOT,
        check=True,
        timeout=1200,
        env={**os.environ, "PYINSTALLER_CONFIG_DIR": str(work / "cache")},
    )
    assets = work / "assets"
    assets.mkdir(exist_ok=True)
    prefix = f"{APP_NAME}-{version}-{target}"
    if macos:
        bundle = work / "bin" / f"{APP_NAME}.app"
        info_path = bundle / "Contents/Info.plist"
        with info_path.open("rb") as source:
            info = plistlib.load(source)
        info["CFBundleShortVersionString"] = version
        info["CFBundleVersion"] = version
        info["LSMinimumSystemVersion"] = "15.0"
        with info_path.open("wb") as output:
            plistlib.dump(info, output)
        subprocess.run(
            ["codesign", "--force", "--sign", "-", "--timestamp=none", str(bundle)],
            check=True,
            timeout=120,
        )
        subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", str(bundle)],
            check=True,
            timeout=120,
        )
        archive = assets / f"{prefix}.zip"
        subprocess.run(
            ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(archive)],
            check=True,
            timeout=120,
        )
    else:
        bundle = work / "bin" / APP_NAME
        (bundle / "START-HERE.txt").write_text(
            "Run ./Ride-Forces-Analyzer from this extracted directory.\n"
            "Keep _internal beside the executable. Install FFmpeg separately for video export.\n"
            "See _internal/licenses for licenses and third-party notices.\n",
            encoding="utf-8",
        )
        archive = assets / f"{prefix}.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            output.add(bundle, arcname=APP_NAME)
    checksum = assets / f"{target.upper()}-SHA256SUMS.txt"
    checksum.write_text(f"{digest(archive)}  {archive.name}\n", encoding="utf-8")
    if filename := os.environ.get("GITHUB_OUTPUT"):
        with Path(filename).open("a", encoding="utf-8") as output:
            output.write(f"package={archive.name}\nchecksums={checksum.name}\n")
    print(
        json.dumps({"target": target, "package": str(archive), "sha256": digest(archive)}),
        flush=True,
    )
    return assets


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=ROOT / ".tmp/posix-build")
    parser.add_argument("--expected-target")
    args = parser.parse_args()
    build(args.work, expected_target=args.expected_target)
