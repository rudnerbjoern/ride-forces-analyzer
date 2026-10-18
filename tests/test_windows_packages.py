"""Binary packages preserve notices, reject private data and verify supplied sources."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest

from scripts import build_windows
from scripts.check_windows_packages import validate_zip
from ride_forces_analyzer.rendering import encoding


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
