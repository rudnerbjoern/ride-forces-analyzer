"""The documented Plus/Neo examples use production graphics without personal device state."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/render_stream_deck_reference.py"


def test_reference_cli_is_reproducible_from_fixed_contract_examples() -> None:
    with TemporaryDirectory(dir=ROOT / ".tmp") as directory:
        work = Path(directory)
        output = work / "reference"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--output", str(output)],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "no device or application connection" in result.stdout
        raw = (output / "stream-deck-reference.json").read_bytes()
        assert b"\r" not in raw
        manifest = json.loads(raw)
        assert manifest["kind"] == "software illustration; not hardware acceptance"
        assert manifest["language"] == "en" and manifest["size"] == [1620, 2060]
        for name, digest in manifest["inputs"].items():
            assert sha256((ROOT / name).read_bytes()).hexdigest() == digest
        plus = manifest["plus"]
        assert manifest["overview"] == {
            "image": "stream-deck-overview.png",
            "size": [1040, 730],
            "device": "plus",
            "page": "Playback",
        }
        with Image.open(output / manifest["overview"]["image"]) as image:
            assert list(image.size) == manifest["overview"]["size"]
        assert plus["image"] == "stream-deck-plus-controls.png"
        assert plus["size"] == manifest["size"]
        pages = {page["name"]: page for page in plus["pages"]}
        assert set(pages) == {
            "Start",
            "Library",
            "Explorer",
            "Playback",
            "Selection",
            "View / Curves",
            "Markers",
        }
        assert {dial["position"]: dial["title"] for dial in pages["Playback"]["dials"]} == {
            "0,0": "Position",
            "1,0": "View",
            "2,0": "Speed",
        }
        assert [dial["title"] for dial in pages["Markers"]["dials"]] == [
            "Start",
            "Gravity",
            "Incline",
            "End",
        ]
        assert "Preview" in pages["Markers"]["dials"][1]["status"]
        assert "Applied #50" in pages["Markers"]["dials"][1]["detail"]
        assert [dial["title"] for dial in pages["Selection"]["dials"]] == [
            "Selection start",
            "Selection end",
        ]
        assert not pages["Start"]["dials"] and not pages["Explorer"]["dials"]
        assert (
            next(key for key in pages["Playback"]["keys"] if key["position"] == "1,1")["title"]
            == "Fine\n1 sample"
        )
        mobile = manifest["mobile"]
        assert mobile["image"] == "stream-deck-mobile-controls.png"
        assert mobile["key_layout"] == {"rows": 2, "columns": 3}
        assert [page["name"] for page in mobile["pages"]] == [
            "Start",
            "Library",
            "Playback",
            "View",
        ]
        assert all(len(page["keys"]) <= 6 for page in mobile["pages"])
        library = next(page for page in mobile["pages"] if page["name"] == "Library")
        titles = {key["position"]: key["title"] for key in library["keys"]}
        assert titles["1,0"] == "Previous\n1/2"
        assert titles["2,0"] == "Next\n1/2"
        assert titles["0,1"] == "Open\n1/2"
        assert all(key["title"] != "Home" for page in mobile["pages"] for key in page["keys"])
        with Image.open(output / mobile["image"]) as image:
            assert list(image.size) == mobile["size"] == [1040, 740]
        neo = manifest["neo"]
        assert neo["image"] == "stream-deck-neo-controls.png"
        assert neo["native_pages"] == ["Start", "Quick controls"]
        assert neo["touch_points"] == {"left": "Previous native page", "right": "Next native page"}
        assert len(neo["pages"]) == 14
        pages = {page["name"]: page for page in neo["pages"]}
        assert all(page["infobar"]["title"] for page in pages.values())
        gravity = pages["Gravity marker"]
        assert "Preview" in gravity["infobar"]["title"]
        assert "Applied #50" in gravity["infobar"]["status"]
        steps = {key["position"]: key["title"].split("\n")[0] for key in gravity["keys"]}
        assert steps["1,0"] == "Gravity -10" and steps["2,0"] == "Gravity +10"
        assert steps["1,1"] == "Gravity -1" and steps["2,1"] == "Gravity +1"
        assert steps["0,0"] == "Back" and steps["3,1"] == "Home"
        with Image.open(output / neo["image"]) as image:
            assert list(image.size) == neo["size"] == [1220, 2830]
        with Image.open(output / manifest["image"]) as image:
            assert image.size == (1620, 2060)
