"""The documented Plus/Neo examples use production graphics without personal device state."""

# cspell:words ARGB Demi

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, cast

from PIL import Image
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QPainter

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/generate_stream_deck_screenshots.py"


def test_localized_labels_fit_native_fonts_and_render_together() -> None:
    exported = subprocess.run(
        ["node", str(ROOT / "plugins/stream-deck/tests/helpers/localized-feedback.mjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert exported.returncode == 0, exported.stdout + exported.stderr
    application = QGuiApplication.instance() or QGuiApplication(["localized-feedback-check"])
    assert application is not None
    directory = ROOT / ".tmp/stream-deck-localization"
    data = json.loads((directory / "surfaces.json").read_text(encoding="utf-8"))
    plugin = ROOT / ".tmp/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin"
    spec = importlib.util.spec_from_file_location("localized_reference", SCRIPT)
    assert spec is not None and spec.loader is not None
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    image = QImage(800, 1500, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#101d30"))
    painter = QPainter(image)
    overflows: list[str] = []
    for language_index, language in enumerate(("en", "de", "fr")):
        top = language_index * 500
        for index, key in enumerate(item for item in data["keys"] if item["language"] == language):
            font = QFont("Segoe UI")
            font.setPixelSize(14)
            for line in key["title"].split("\n"):
                if QFontMetricsF(font).horizontalAdvance(line) > 92:
                    overflows.append(f"{language}/{key['operation']}: {line}")
            if index < 8:
                getattr(renderer, "_profile_key")(painter, key, QRectF(index * 100, top, 100, 100))
        cases = [item for item in data["surfaces"] if item["language"] == language]
        for case in cases:
            feedback = case["feedback"]
            layout = json.loads((plugin / feedback["layout"]).read_text(encoding="utf-8"))
            for field in layout["items"]:
                if field["type"] != "text":
                    continue
                if field["key"] in {"value", "detail"} and case["control"] in {"library", "filter"}:
                    continue
                value = feedback[field["key"]]
                value = cast(dict[str, Any], value)["value"] if isinstance(value, dict) else value
                font = QFont("Segoe UI")
                font.setPixelSize(field["font"]["size"])
                font.setWeight(
                    QFont.Weight.DemiBold
                    if field["font"].get("weight", 400) >= 600
                    else QFont.Weight.Normal,
                )
                if QFontMetricsF(font).horizontalAdvance(value) > field["rect"][2]:
                    overflows.append(f"{language}/{case['control']}/{field['key']}: {value}")
        for index, case in enumerate(item for item in cases if item["connection"] == "connected"):
            getattr(renderer, "_touch_field")(
                painter,
                {},
                case["feedback"],
                (index % 4) * 200,
                top + 110 + (index // 4) * 100,
            )
        neo_layout = json.loads((plugin / "layouts/neo.json").read_text(encoding="utf-8"))
        for case in (item for item in data["neo"] if item["language"] == language):
            for field in neo_layout["items"]:
                if field["type"] != "text" or (
                    field["key"] == "value" and case["section"] == "library"
                ):
                    continue
                font = QFont("Segoe UI")
                font.setPixelSize(field["font"]["size"])
                value = case["feedback"][field["key"]]
                if QFontMetricsF(font).horizontalAdvance(value) > field["rect"][2]:
                    overflows.append(f"{language}/Neo/{case['section']}/{field['key']}: {value}")
        for index, case in enumerate(
            item
            for item in data["neo"]
            if item["language"] == language and item["section"] in {"start", "view", "markers"}
        ):
            getattr(renderer, "_touch_field")(
                painter,
                neo_layout,
                case["feedback"],
                index * 250,
                top + 430,
            )
    painter.end()
    assert image.save(str(directory / "native-labels.png"))
    assert not overflows, "Localized device text exceeds its native field:\n" + "\n".join(overflows)


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
        assert manifest["language"] == "en" and manifest["size"] == [1620, 1570]
        for name, digest in manifest["inputs"].items():
            assert sha256((ROOT / name).read_bytes()).hexdigest() == digest
        plus = manifest["plus"]
        assert manifest["overview"] == {
            "image": "stream-deck-overview.png",
            "size": [1040, 730],
            "device": "plus",
            "page": "Playback / Navigate",
        }
        with Image.open(output / manifest["overview"]["image"]) as image:
            assert list(image.size) == manifest["overview"]["size"]
        assert plus["image"] == "stream-deck-plus-controls.png"
        assert plus["size"] == manifest["size"]
        pages = {page["name"]: page for page in plus["pages"]}
        assert all(key["title"] != "Home" for page in plus["pages"] for key in page["keys"])
        assert list(pages) == [
            "Library",
            "Playback / Navigate",
            "Playback / Selection",
            "Curves",
            "Markers / Markers",
            "Markers / View",
        ]
        assert [dial["title"] for dial in pages["Library"]["dials"]] == [
            "Library",
            "",
            "Park",
            "Status",
        ]
        assert [dial["position"] for dial in pages["Library"]["dials"]] == [
            "0,0",
            "1,0",
            "2,0",
            "3,0",
        ]
        park, status = pages["Library"]["dials"][2:]
        assert park["value"] == "All parks" and park["detail"] == "Active: All parks"
        assert status["value"] == "All statuses"
        assert status["detail"] == "Active: All statuses"
        assert park["status"]["value"] == status["status"]["value"] == "Ready"
        assert park["hint"] == status["hint"] == "Press: Filter · Touch: All"
        assert [dial["title"] for dial in pages["Playback / Selection"]["dials"]] == [
            "Selection start",
            "Selection end",
            "Zoom",
            "Zoom selection",
        ]
        for page in pages.values():
            keys = {key["position"]: key for key in page["keys"]}
            assert [keys[f"{column},0"]["title"].split("\n")[0] for column in range(4)] == [
                "Library",
                "Playback",
                "Curves",
                "Markers",
            ]
            assert sum(keys[f"{column},0"]["selected"] for column in range(4)) == 1
        library_keys = {key["position"]: key["title"] for key in pages["Library"]["keys"]}
        assert [library_keys[f"{column},1"] for column in range(4)] == [
            "Open\n1/2",
            "New\nwindow",
            "Import…",
            "Reset\nfilters",
        ]
        for page, label, size in (
            ("Playback / Navigate", "Fine", 1),
            ("Playback / Selection", "Medium", 10),
            ("Markers / Markers", "Coarse", 20),
        ):
            title = next(key for key in pages[page]["keys"] if key["position"] == "3,1")["title"]
            assert title == f"{label}\n{size} {'sample' if size == 1 else 'samples'}"
            assert "sample" not in pages[page]["dials"][0]["status"]["value"]
        native = manifest["native_strips"]
        assert native["field_size"] == [200, 100]
        assert set(pages) <= set(native["cases"])
        assert "Markers · Applied / Preview / Pending / Failed" in native["cases"]
        assert "Library · offline" in native["cases"]
        with Image.open(output / native["image"]) as image:
            assert list(image.size) == native["size"]
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
        landscape = [[titles.get(f"{column},{row}") for column in range(3)] for row in range(2)]
        assert landscape == [
            ["Back", "Previous\n1/2", "Next\n1/2"],
            ["Import…", "Open\n1/2", "New\nwindow"],
        ]
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
            assert image.size == (1620, 1570)
