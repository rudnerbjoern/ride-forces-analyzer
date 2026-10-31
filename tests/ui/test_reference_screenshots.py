"""Native screenshot scenes retain source identities, settings and isolated profiles."""

# cspell:words getextrema

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from textwrap import dedent

from scripts import capture_app_reference

from PIL import Image
import pytest

from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES
from ride_forces_analyzer.storage.preferences import Appearance

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/capture_app_reference.py"
SOURCE = REAL_FIXTURE_DIRECTORY / "VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces"
SOURCE_SHA256 = "f48157cadbfeb374eeadf48112b0bbfc1e8b47c580cb303342cf65977054ad04"


def test_capture_cli_preserves_reference_scene_source_and_preferences() -> None:
    with TemporaryDirectory(dir=ROOT / ".tmp") as directory:
        work = Path(directory)
        profile = work / "personal-profile"
        profile.mkdir()
        sentinel = profile / "keep.txt"
        sentinel.write_text("Keep personal settings unchanged", encoding="utf-8")
        environment = {**os.environ, "LOCALAPPDATA": str(profile), "QT_SCALE_FACTOR": "2"}
        output = work / "reference"
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
        assert manifest["position"] == "bottom" and manifest["extent"] == "full_frame"
        pov_manifest = json.loads((output / "pov-reference.json").read_text(encoding="utf-8"))
        assert pov_manifest["preview_background"] == "pov-toutatis"
        photo_hash = sha256(capture_app_reference.POV_SOURCE.read_bytes()).hexdigest()
        assert pov_manifest["preview_background_sha256"] == photo_hash
        first, last = pov_manifest["preview_interval"]
        assert pov_manifest["preview_sample"] == first + round(0.6 * (last - first))
        for filename, size in (
            ("workspace-dark.png", (1600, 1100)),
            ("workspace-light.png", (1600, 1100)),
            ("export-preview.png", (1500, 1000)),
            ("export-preview-pov.png", (1500, 1000)),
        ):
            with Image.open(output / filename) as image:
                assert image.size == size
                assert image.convert("RGB").getextrema() != ((0, 0), (0, 0), (0, 0))
        assert len(list(output.glob("*.png"))) == 4
        assert list(profile.iterdir()) == [sentinel]
        assert sentinel.read_text(encoding="utf-8") == "Keep personal settings unchanged"
        assert sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256


def test_theme_capture_uses_the_same_scene_for_each_appearance() -> None:
    with TemporaryDirectory(dir=ROOT / ".tmp") as directory:
        output = Path(directory) / "themes"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--themes", "--output", str(output)],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        manifest = json.loads((output / "appearance-reference.json").read_text(encoding="utf-8"))
        assert manifest["source_sha256"] == SOURCE_SHA256
        assert manifest["sample"] == 4960 and manifest["selection"] == [4200, 5100]
        assert manifest["smoothing"] == 11 and manifest["language"] == "en"
        assert set(manifest["themes"]) == {
            appearance.value for appearance in Appearance if appearance is not Appearance.SYSTEM
        }
        pixels: set[bytes] = set()
        assert manifest["workspace_size"] == [800, 650]
        assert manifest["includes_window_frame"] is True
        for filename in manifest["themes"].values():
            with Image.open(output / filename) as image:
                assert image.width >= 800 and image.height > 650
                pixels.add(sha256(image.convert("RGB").tobytes()).digest())
        assert len(pixels) == len(manifest["themes"])
        assert len(list(output.glob("*.png"))) == len(manifest["themes"])


def test_capture_rejects_changed_source_before_writing_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory(dir=ROOT / ".tmp") as directory:
        work = Path(directory)
        changed = work / SOURCE.name
        changed.write_bytes(SOURCE.read_bytes() + b"\n")
        monkeypatch.setattr(capture_app_reference, "SOURCE", changed)
        output = work / "output"
        with pytest.raises(ValueError, match="source hash differs"):
            capture_app_reference.capture_reference(output)
        assert not output.exists()


def test_detail_capture_preserves_sources_scales_and_missing_context_fallback() -> None:
    """Real UI crops retain source identities and honest smoothing comparison axes."""
    with TemporaryDirectory(dir=ROOT / ".tmp") as directory:
        work = Path(directory)
        output = work / "details"
        wrapper = dedent("""
            import sys
            from runpy import run_path
            from ride_forces_analyzer.explorer import ExplorerData
            original = ExplorerData.vertical_context_label
            ExplorerData.vertical_context_label = (
                lambda self, index: None if index % 2 == 0 else original(self, index)
            )
            script = sys.argv.pop(1)
            sys.argv[0] = script
            run_path(script, run_name="__main__")
        """)
        command = [sys.executable, "-c", wrapper, str(SCRIPT), "--details", "--output", str(output)]
        result = subprocess.run(
            command,
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        manifest = json.loads((output / "readme-reference.json").read_text(encoding="utf-8"))
        assert set(manifest) == {"VoltronNevera", "Taron", "Manta"}
        for name, sample in (("VoltronNevera", 4960), ("Taron", 3399), ("Manta", 4782)):
            source = next(REAL_FIXTURE_DIRECTORY.glob(name + "-*.forces"))
            assert manifest[name]["sample"] == sample
            assert manifest[name]["source_sha256"] == REAL_FIXTURES[source.name][1]
            assert sha256(source.read_bytes()).hexdigest() == REAL_FIXTURES[source.name][1]
        assert {"Floater Airtime", "Ejector Airtime"} <= set(manifest["VoltronNevera"]["contexts"])
        assert all(isinstance(label, str) for label in manifest["VoltronNevera"]["contexts"])
        assert manifest["Taron"]["cards"][2] == ["Longitudinal", "+1.08 g", "Acceleration"]
        smoothing = manifest["Manta"]
        assert smoothing["smoothing"] == [1, 11, 31]
        assert [panel["smoothing"] for panel in smoothing["panels"]] == [1, 11, 31]
        for panel in smoothing["panels"]:
            assert panel["force_range"] == smoothing["force_range"]
            assert panel["time_range"] == smoothing["time_range"] == [93.0, 98.0]
        for filename in (
            "voltron-airtime-detail.png",
            "taron-force-cards.png",
            "manta-smoothing-comparison.png",
        ):
            with Image.open(output / filename) as image:
                assert image.width >= 800
                assert image.height >= 40
                assert image.convert("RGB").getextrema() != ((0, 0), (0, 0), (0, 0))
        with Image.open(output / "manta-smoothing-comparison.png") as image:
            assert image.height % 3 == 0
            height = image.height // 3
            # Exclude the headings: each actual curve differs on the same scale.
            panels = [
                image.crop((0, row * height + 32, image.width, (row + 1) * height)).tobytes()
                for row in range(3)
            ]
            assert len(set(panels)) == 3
