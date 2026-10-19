"""Fixed native screenshot scene, repeatability and source/profile preservation."""

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image

from tests.support.recordings import REAL_FIXTURE_DIRECTORY

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/capture_app_reference.py"
SOURCE = REAL_FIXTURE_DIRECTORY / "VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces"
SOURCE_SHA256 = "f48157cadbfeb374eeadf48112b0bbfc1e8b47c580cb303342cf65977054ad04"


def test_capture_cli_is_repeatable_and_preserves_original_and_preferences() -> None:
    with TemporaryDirectory(dir=ROOT / ".tmp") as directory:
        work = Path(directory)
        profile = work / "personal-profile"
        profile.mkdir()
        sentinel = profile / "keep.txt"
        sentinel.write_text("Keep personal settings unchanged", encoding="utf-8")
        environment = {**os.environ, "LOCALAPPDATA": str(profile), "QT_SCALE_FACTOR": "2"}
        captures: list[dict[str, bytes]] = []
        for name in ("first", "second"):
            output = work / name
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=work,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            manifest = json.loads((output / "app-reference.json").read_text(encoding="utf-8"))
            assert manifest["source_sha256"] == SOURCE_SHA256
            assert manifest["sample"] == 4960 and manifest["selection"] == [4200, 5100]
            assert manifest["smoothing"] == 11 and manifest["language"] == "en"
            assert manifest["layout"] == "ribbon" and manifest["fps"] == 50
            pixels: dict[str, bytes] = {}
            for filename, size in (
                ("workspace-dark.png", (1600, 1100)),
                ("workspace-light.png", (1600, 1100)),
                ("export-preview.png", (1500, 1000)),
            ):
                with Image.open(output / filename) as image:
                    assert image.size == size
                    pixels[filename] = image.convert("RGB").tobytes()
            assert len(list(output.glob("*.png"))) == 3
            captures.append(pixels)
        assert captures[0] == captures[1]
        assert list(profile.iterdir()) == [sentinel]
        assert sentinel.read_text(encoding="utf-8") == "Keep personal settings unchanged"
        assert sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256


def test_capture_rejects_changed_source_before_writing_images() -> None:
    with TemporaryDirectory(dir=ROOT / ".tmp") as directory:
        work = Path(directory)
        changed = work / "tests/fixtures/real" / SOURCE.name
        changed.parent.mkdir(parents=True)
        changed.write_bytes(SOURCE.read_bytes() + b"\n")
        copied_script = work / "scripts" / SCRIPT.name
        copied_script.parent.mkdir()
        shutil.copyfile(SCRIPT, copied_script)
        output = work / "output"
        result = subprocess.run(
            [sys.executable, str(copied_script), "--output", str(output)],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        assert result.returncode != 0
        assert "source hash differs" in result.stderr
        assert not output.exists()
