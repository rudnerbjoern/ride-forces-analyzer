"""Binary packages preserve notices, reject private data and verify supplied sources."""

# cspell:words filevers prodvers qpdf libqpdf imageformats qjpeg qwindows qtbase hiddenimports datas

import ast
import json
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
from zipfile import ZipFile

import pytest

from scripts import build_windows
from scripts.check_windows_packages import validate_zip
from ride_forces_analyzer.rendering import encoding


def test_qt_gui_hook_excludes_only_pdf_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    binaries = [
        ("plugins/imageformats/qpdf.dll", "PySide6/plugins/imageformats"),
        ("plugins/imageformats/libqpdf.so", "PySide6/Qt/plugins/imageformats"),
        ("plugins/imageformats/libqpdf.dylib", "PySide6/Qt/plugins/imageformats"),
        ("plugins/imageformats/qjpeg.dll", "PySide6/plugins/imageformats"),
        ("plugins/platforms/qwindows.dll", "PySide6/plugins/platforms"),
    ]
    hook = (
        Path(build_windows.__file__).resolve().parents[1] / "packaging/hooks/hook-PySide6.QtGui.py"
    )

    def dependencies(
        filename: str,
    ) -> tuple[list[str], list[tuple[str, str]], list[tuple[str, str]]]:
        assert Path(filename) == hook
        return ["PySide6.QtCore"], binaries, [("translations/qtbase_de.qm", "translations")]

    qt_hook = ModuleType("PyInstaller.utils.hooks.qt")
    monkeypatch.setattr(qt_hook, "add_qt6_dependencies", dependencies, raising=False)
    monkeypatch.setitem(sys.modules, "PyInstaller", None)
    monkeypatch.setitem(sys.modules, qt_hook.__name__, qt_hook)
    result = runpy.run_path(str(hook))
    assert result["binaries"] == binaries[3:]
    assert result["hiddenimports"] == ["PySide6.QtCore"]
    assert result["datas"] == [("translations/qtbase_de.qm", "translations")]


@pytest.mark.parametrize("version,flags", [("1.1.0", 0), ("1.2.3", 0), ("1.2.3rc2", 2)])
def test_version_resource_preserves_unicode_and_project_version(
    export_directory: Path,
    version: str,
    flags: int,
) -> None:
    resource = build_windows.write_version_info(export_directory / "version.txt", version)
    tree = ast.parse(resource.read_text(encoding="utf-8"), mode="eval")
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    strings = {
        ast.literal_eval(node.args[0]): ast.literal_eval(node.args[1])
        for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "StringStruct"
    }
    assert strings == {
        "CompanyName": "Björn Rudner",
        "FileDescription": "Ride force analysis and video overlays",
        "FileVersion": version,
        "InternalName": "Ride-Forces-Analyzer",
        "LegalCopyright": "Copyright © 2026 Björn Rudner",
        "OriginalFilename": "Ride-Forces-Analyzer.exe",
        "ProductName": "Ride Forces Analyzer",
        "ProductVersion": version,
    }
    fixed = next(
        node
        for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "FixedFileInfo"
    )
    values = {item.arg: ast.literal_eval(item.value) for item in fixed.keywords}
    numeric = (1, 1, 0, 0) if version == "1.1.0" else (1, 2, 3, 0)
    assert values == {"filevers": numeric, "prodvers": numeric, "flags": flags}


def test_windows_version_rejects_unrepresentable_components(export_directory: Path) -> None:
    with pytest.raises(ValueError, match="resource limits"):
        build_windows.write_version_info(export_directory / "version.txt", "1.2.65536")


@pytest.mark.parametrize("previous_archive", [False, True])
def test_release_build_outputs_only_windows_downloads_and_checksums(
    monkeypatch: pytest.MonkeyPatch,
    previous_archive: bool,
) -> None:
    with TemporaryDirectory(dir=".tmp") as directory:
        root = Path(directory).resolve()
        work = root / ".tmp/build"
        assets = work / "assets"
        assets.mkdir(parents=True)
        if previous_archive:
            (assets / "corresponding-sources.zip").write_bytes(b"previous build")
        (root / "packaging").mkdir()
        (root / "packaging/redistribution.json").write_text(
            '{"status":"verified","source_archives":[]}',
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            (root / name).write_text("synthetic notices", encoding="utf-8")
        distribution = root / ".tmp/encoder"
        (distribution / "bin").mkdir(parents=True)
        encoder = distribution / "bin/ffmpeg.exe"
        encoder.write_bytes(b"synthetic encoder")
        for name in ("LICENSE", "README.txt"):
            (distribution / name).write_text("synthetic notices", encoding="utf-8")

        def notices(destination: Path) -> None:
            destination.mkdir()

        def acquire_encoder(destination: Path) -> Path:
            return encoder

        def run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if "PyInstaller" in arguments:
                assert arguments[arguments.index("--additional-hooks-dir") + 1] == str(
                    root / "packaging/hooks",
                )
                assert Path(arguments[arguments.index("--icon") + 1]).read_bytes()[:4] == (
                    b"\x00\x00\x01\x00"
                )
                assert (
                    f"{build_windows.ICON_SOURCE}:ride_forces_analyzer/ui/presentation" in arguments
                )
                version_info = Path(arguments[arguments.index("--version-file") + 1])
                assert "StringStruct('FileVersion', '1.2.3')" in version_info.read_text(
                    encoding="utf-8",
                )
                destination = Path(arguments[arguments.index("--distpath") + 1])
                destination.mkdir()
                (destination / f"{build_windows.APP_NAME}.exe").write_bytes(b"synthetic app")
            return subprocess.CompletedProcess(arguments, 0, "synthetic encoder notices", "")

        monkeypatch.setattr(build_windows, "ROOT", root)
        monkeypatch.setattr(build_windows, "collect_notices", notices)
        monkeypatch.setattr(build_windows, "acquire_ffmpeg", acquire_encoder)
        monkeypatch.setattr(subprocess, "run", run)
        result = build_windows.build(work, release=True)
        prefix = f"{build_windows.APP_NAME}-1.2.3-windows-x64"
        downloads = {f"{prefix}.exe", f"{prefix}-standard.zip", f"{prefix}-complete.zip"}
        assert {path.name for path in result.iterdir()} == downloads | {"WINDOWS-SHA256SUMS.txt"}
        checksum_names = {
            line.split("  ", 1)[1]
            for line in (result / "WINDOWS-SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        }
        assert checksum_names == downloads


@pytest.mark.parametrize(
    "unexpected",
    ["../escape", "Ride-Forces-Analyzer/private.forces", "Ride-Forces-Analyzer/ffmpeg.exe"],
)
def test_standard_zip_rejects_unsafe_private_or_encoder_content(unexpected: str) -> None:
    with TemporaryDirectory(dir=".tmp") as directory:
        archive = Path(directory) / "standard.zip"
        with ZipFile(archive, "w") as output:
            output.writestr(unexpected, b"synthetic")
        with pytest.raises(ValueError):
            validate_zip(archive, complete=False)


def test_binary_release_validates_sources_and_rejects_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory(dir=".tmp") as directory:
        root = Path(directory).resolve()
        (root / ".tmp").mkdir()
        monkeypatch.setattr(build_windows, "ROOT", root)
        manifest = root / "redistribution.json"
        manifest.write_text(
            '{"status":"accepted","source_archives":[]}',
            encoding="utf-8",
        )
        build_windows.validate_redistribution(manifest)
        source = root / ".tmp/source.zip"
        source.write_bytes(b"synthetic source archive")
        manifest.write_text(
            json.dumps(
                {
                    "status": "accepted",
                    "source_archives": [
                        {"path": ".tmp/source.zip", "sha256": build_windows.digest(source)},
                    ],
                },
            ),
            encoding="utf-8",
        )
        build_windows.validate_redistribution(manifest)
        source.write_bytes(b"changed")
        with pytest.raises(ValueError, match="changed"):
            build_windows.validate_redistribution(manifest)


def test_frozen_export_prefers_adjacent_encoder_and_respects_explicit_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory(dir=".tmp") as directory:
        root = Path(directory).resolve()
        bundled = root / "ffmpeg.exe"
        bundled.write_bytes(b"synthetic encoder")
        explicit = root / "chosen.exe"
        explicit.write_bytes(b"synthetic encoder")
        monkeypatch.setattr(encoding.sys, "frozen", True, raising=False)
        monkeypatch.setattr(encoding.sys, "executable", str(root / "app.exe"))

        def path_encoder(name: str) -> str:
            return "unexpected-path.exe"

        monkeypatch.setattr(encoding.shutil, "which", path_encoder)
        assert encoding.find_ffmpeg() == bundled
        assert encoding.find_ffmpeg(explicit) == explicit
