"""Binary packages preserve notices, reject private data and verify supplied sources."""

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest

from scripts import build_windows
from scripts.check_windows_packages import validate_zip
from ride_forces_analyzer.rendering import encoding


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


def test_binary_release_allows_documented_gaps_but_rejects_changed_sources(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with TemporaryDirectory(dir=".tmp") as directory:
        root = Path(directory).resolve()
        (root / ".tmp").mkdir()
        monkeypatch.setattr(build_windows, "ROOT", root)
        manifest = root / "redistribution.json"
        manifest.write_text(
            '{"status":"pending","source_archives":[],"open_items":["Provider sources unavailable"]}',
            encoding="utf-8",
        )
        build_windows.validate_redistribution(manifest)
        assert "Provider sources unavailable" in capsys.readouterr().out
        source = root / ".tmp/source.zip"
        source.write_bytes(b"synthetic source archive")
        manifest.write_text(
            json.dumps(
                {
                    "status": "pending",
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
