"""The theme reference stays on the same source sample as layouts evolve."""

from hashlib import sha256
from collections.abc import Iterator
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import shutil

from PIL import Image
import pytest

from tests.support.recordings import REAL_FIXTURE_DIRECTORY

SOURCE = REAL_FIXTURE_DIRECTORY / "VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces"
SOURCE_SHA256 = "f48157cadbfeb374eeadf48112b0bbfc1e8b47c580cb303342cf65977054ad04"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/render_export_reference.py"


@pytest.fixture
def reference_directory() -> Iterator[Path]:
    root = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(dir=root / ".tmp") as directory:
        yield Path(directory)


def test_reference_rejects_changed_recording(reference_directory: Path) -> None:
    changed = reference_directory / "tests/fixtures/real" / SOURCE.name
    changed.parent.mkdir(parents=True)
    changed.write_bytes(SOURCE.read_bytes() + b"\n")
    script = reference_directory / "scripts" / SCRIPT.name
    script.parent.mkdir()
    shutil.copyfile(SCRIPT, script)
    output = reference_directory / "output"
    result = subprocess.run(
        [sys.executable, str(script), "--output", str(output)],
        cwd=reference_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "source hash differs" in result.stderr
    assert not output.exists()


def test_reference_cli_uses_fixed_sample_from_another_directory(reference_directory: Path) -> None:
    output = reference_directory / "reference"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=reference_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("sample 8575, replay 02:20.04") == 5
    manifest = json.loads((output / "voltron-reference.json").read_text(encoding="utf-8"))
    assert b"\r" not in (output / "voltron-reference.json").read_bytes()
    assert manifest["recording"] == "Voltron Nevera"
    assert manifest["source_file"] == SOURCE.name
    assert manifest["sample"] == 8575
    assert manifest["smoothing"] == 11
    assert manifest["replay"] == "02:20.04"
    assert manifest["replay_seconds"] == 140.08
    assert manifest["recording_seconds"] == 171.5
    assert (manifest["first"], manifest["last"]) == (1571, 10374)
    assert manifest["source_sha256"] == SOURCE_SHA256
    assert manifest["language"] == "en" and manifest["aspect"] == "landscape"
    assert manifest["profile_window_seconds"] == {
        "ribbon": 12.0,
        "corners": 12.0,
        "hud": 30.0,
        "orbit": 12.0,
        "column": 12.0,
    }
    assert manifest["values"] == pytest.approx(
        [4.365497903276147, -0.6689254689866224, -0.420851349258314],
    )
    assert manifest["orientation_degrees"] == pytest.approx(62.85439946067607)
    assert len(list(output.glob("*.png"))) == 11
    for layout in ("ribbon", "corners", "hud", "orbit", "column"):
        with Image.open(output / f"voltron-{layout}.png") as image:
            assert image.size == (3840, 2160)
        with Image.open(output / f"voltron-{layout}-detail.png") as image:
            assert max(image.size) <= 1440
    assert sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256
