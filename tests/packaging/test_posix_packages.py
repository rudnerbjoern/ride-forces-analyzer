"""Native archive contracts are testable on the Windows development host."""

from io import BytesIO
from configparser import ConfigParser
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile
from zipfile import ZipFile

import pytest

from scripts import build_posix
from scripts.check_posix_packages import extract, validate_member


@pytest.mark.parametrize("target", ["linux-x64", "macos-x64", "macos-arm64"])
def test_native_builder_preserves_version_notices_and_archive_layout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    target: str,
) -> None:
    root = tmp_path
    (root / "pyproject.toml").write_text('[project]\nversion="1.2.3"\n', encoding="utf-8")
    work = root / ".tmp/build"
    desktop = root / "packaging/linux/ride-forces-analyzer.desktop"
    desktop.parent.mkdir(parents=True)
    shutil.copyfile(
        Path(build_posix.__file__).resolve().parents[1]
        / "packaging/linux/ride-forces-analyzer.desktop",
        desktop,
    )
    monkeypatch.setattr(build_posix, "ROOT", root)
    monkeypatch.setattr(build_posix, "runtime_target", lambda: target)

    def notices(folder: Path) -> None:
        folder.mkdir()
        (folder / "inventory.json").write_text("[]", encoding="utf-8")

    def run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "PyInstaller" in arguments:
            assert arguments[arguments.index("--additional-hooks-dir") + 1] == str(
                root / "packaging/hooks",
            )
            assert f"{build_posix.ICON_SOURCE}:ride_forces_analyzer/ui" in arguments
            if target.startswith("macos-"):
                icon = Path(arguments[arguments.index("--icon") + 1])
                assert icon.read_bytes()[:4] == b"icns"
                info = work / "bin" / f"{build_posix.APP_NAME}.app/Contents/Info.plist"
                info.parent.mkdir(parents=True)
                resources = info.parent / "Resources"
                resources.mkdir()
                shutil.copyfile(icon, resources / icon.name)
                with info.open("wb") as output:
                    plistlib.dump(
                        {"CFBundleName": build_posix.APP_NAME, "CFBundleIconFile": icon.name},
                        output,
                    )
            else:
                bundle = work / "bin" / build_posix.APP_NAME
                bundle.mkdir(parents=True)
                executable = bundle / build_posix.APP_NAME
                executable.write_bytes(b"synthetic native executable")
                executable.chmod(0o755)
        if arguments[0] == "ditto":
            bundle = Path(arguments[-2])
            with ZipFile(arguments[-1], "w") as output:
                output.write(bundle / "Contents/Info.plist", f"{bundle.name}/Contents/Info.plist")
                output.write(
                    bundle / "Contents/Resources/app-icon.icns",
                    f"{bundle.name}/Contents/Resources/app-icon.icns",
                )
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(build_posix, "collect_notices", notices)
    monkeypatch.setattr(build_posix.subprocess, "run", run)
    assets = build_posix.build(work, expected_target=target)
    extension = ".tar.gz" if target == "linux-x64" else ".zip"
    archive = assets / f"{build_posix.APP_NAME}-1.2.3-{target}{extension}"
    assert archive.is_file()
    checksum = assets / f"{target.upper()}-SHA256SUMS.txt"
    assert (
        checksum.read_text(encoding="utf-8") == f"{build_posix.digest(archive)}  {archive.name}\n"
    )
    if target.startswith("macos-"):
        with ZipFile(archive) as source:
            info = plistlib.loads(source.read(f"{build_posix.APP_NAME}.app/Contents/Info.plist"))
            assert info["CFBundleIconFile"] == "app-icon.icns"
            assert source.read(f"{build_posix.APP_NAME}.app/Contents/Resources/app-icon.icns")[
                :4
            ] == (b"icns")
        assert info["CFBundleVersion"] == info["CFBundleShortVersionString"] == "1.2.3"
        assert info["LSMinimumSystemVersion"] == "15.0"
        assert info["CFBundleName"] == info["CFBundleDisplayName"] == "Ride Forces Analyzer"
        assert info["CFBundleDocumentTypes"] == [
            {
                "CFBundleTypeName": "Ride recording",
                "CFBundleTypeExtensions": ["forces", "zforces"],
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
            },
        ]
        assert info["NSHumanReadableCopyright"] == "Copyright © 2026 Björn Rudner"
        assert info["RideForcesAnalyzerAuthor"] == "Björn Rudner"
        assert info["RideForcesAnalyzerDescription"] == "Ride force analysis and video overlays"
    else:
        with tarfile.open(archive) as source:
            content = source.extractfile(f"{build_posix.APP_NAME}/{build_posix.APP_NAME}")
            assert content is not None
            assert content.read() == b"synthetic native executable"
            launcher = source.extractfile(f"{build_posix.APP_NAME}/ride-forces-analyzer.desktop")
            assert launcher is not None
            entry = ConfigParser(interpolation=None)
            entry.read_string(launcher.read().decode("utf-8"))
            fields = entry["Desktop Entry"]
            assert fields["Name"] == "Ride Forces Analyzer"
            assert fields["Comment"] == "Ride force analysis and video overlays"
            assert fields["X-RideForcesAnalyzer-Version"] == "1.2.3"
            assert fields["X-RideForcesAnalyzer-Author"] == "Björn Rudner"
            assert fields["X-RideForcesAnalyzer-Copyright"] == "Copyright © 2026 Björn Rudner"
            assert fields["Exec"] == "Ride-Forces-Analyzer %f"
            assert fields["Icon"] == "ride-forces-analyzer"
            assert fields["Comment[de]"]
            for suffix in ("png", "svg"):
                icon = source.extractfile(f"{build_posix.APP_NAME}/ride-forces-analyzer.{suffix}")
                assert icon is not None and icon.read()


@pytest.mark.parametrize("target", [None, "windows-x64", "linux-arm64"])
def test_native_builder_rejects_unsupported_hosts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    target: str | None,
) -> None:
    monkeypatch.setattr(build_posix, "runtime_target", lambda: target)
    with pytest.raises(ValueError, match="native Linux"):
        build_posix.build(tmp_path)


def test_native_builder_rejects_wrong_architecture_before_building(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(build_posix, "runtime_target", lambda: "macos-arm64")
    with pytest.raises(ValueError, match="Expected native target"):
        build_posix.build(tmp_path, expected_target="macos-x64")


@pytest.mark.parametrize(
    "name,target",
    [
        ("../escape", None),
        ("/absolute", None),
        ("app/source.forces", None),
        ("app/preferences.sqlite3", None),
        ("app/.git/config", None),
        ("app/link", "../../escape"),
        ("app/link", "/absolute"),
    ],
)
def test_package_paths_and_links_cannot_expose_private_or_external_data(
    name: str,
    target: str | None,
) -> None:
    with pytest.raises(ValueError):
        validate_member(name, target)


def test_linux_archive_extracts_runtime_bytes_and_rejects_changed_data(tmp_path: Path) -> None:
    archive = tmp_path / "app.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        entry = tarfile.TarInfo("app/runtime")
        entry.size = 7
        entry.mode = 0o755
        output.addfile(entry, BytesIO(b"runtime"))
    destination = tmp_path / "extracted"
    destination.mkdir()
    extract(archive, destination)
    assert (destination / "app/runtime").read_bytes() == b"runtime"
    with tarfile.open(archive, "w:gz") as output:
        entry = tarfile.TarInfo("app/recording.forces")
        entry.size = 2
        output.addfile(entry, BytesIO(json.dumps({}).encode()))
    with pytest.raises(ValueError):
        extract(archive, destination)
