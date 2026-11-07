"""Render device-profile illustrations and the limited Mobile preview from plugin feedback.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words ARGB Demi

import argparse
import base64
from functools import cache
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/stream-deck"
IMAGE = "stream-deck-plus-controls.png"
MANIFEST = "stream-deck-reference.json"

# Use fixed contract examples, never a running application or private discovery file.
_FEEDBACK = r"""
import { readFileSync } from 'node:fs';
import { keyFeedback, keyImage } from './plugins/stream-deck/dist/feedback.js';
import { infoFeedback } from './plugins/stream-deck/dist/device-feedback.js';
import { plusFeedback } from './plugins/stream-deck/dist/plus-feedback.js';
import { navigationFeedback } from './plugins/stream-deck/dist/navigation.js';
import { ZipReader, Uint8ArrayReader, TextWriter, Uint8ArrayWriter } from '@zip.js/zip.js';
const fixture = JSON.parse(readFileSync('tests/fixtures/stream_deck_protocol.json', 'utf8')).messages[0];
const client = () => ({ state: structuredClone(fixture), status: 'connected', pending: () => false, error: () => undefined });
const h = client();
const profiles = {};
for (const device of ['plus','neo','mobile']) {
const archive = new ZipReader(new Uint8ArrayReader(readFileSync(`.tmp/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/profiles/${device}.streamDeckProfile`)));
const entries = await archive.getEntries();
const root = JSON.parse(await entries.find(entry => /^[^/]+\/manifest.json$/.test(entry.filename)).getData(new TextWriter()));
const pages = [];
for (const entry of entries.filter(entry => /\/Profiles\/[^/]+\/manifest.json$/.test(entry.filename))) {
 const page = JSON.parse(await entry.getData(new TextWriter()));
 if (!page.Name) continue;
 const stepSize = device === 'plus' ? ({'Playback / Selection': 10, 'Markers / Markers': 20}[page.Name] ?? 1) : 1;
 const stepName = stepSize === 1 ? 'Fine' : stepSize === 10 ? 'Medium' : 'Coarse';
 const pageKeys = [];
 for (const [position, action] of Object.entries(page.Controllers.find(c => c.Type === 'Keypad').Actions)) {
  let feedback;
  if (action.UUID.endsWith('.plus-navigation')) feedback = navigationFeedback(action.Settings, action.Settings.page, h);
  else if (action.UUID.endsWith('.control')) feedback = keyFeedback(h, 'example', action.Settings);
  else if (action.UUID.endsWith('.step-mode')) feedback = {
   title: `${stepName}\n${stepSize} ${stepSize === 1 ? 'sample' : 'samples'}`,
   image: keyImage(stepName.toLowerCase(), undefined)
  };
  else {
   const image = action.States[0].Image;
   const asset = entries.find(candidate => candidate.filename === entry.filename.replace('manifest.json', image));
   const artwork = image.endsWith('.png') ? 'data:image/png;base64,' + Buffer.from(await asset.getData(new Uint8ArrayWriter())).toString('base64')
    : await asset.getData(new TextWriter());
   feedback = {title:action.States[0].Title, image:artwork};
  }
  pageKeys.push({position, ...feedback});
 }
 const result = {name:page.Name, id:entry.filename.split('/').at(-2).toLowerCase(), keys:pageKeys};
 if (device === 'neo') result.infobar = infoFeedback(h, page.Controllers.find(c => c.Type === 'Neo').Actions['1,0'].Settings);
 else if (device === 'plus') result.dials = Object.entries(page.Controllers.find(c => c.Type === 'Encoder')?.Actions ?? {})
  .map(([position, action]) => ({position, ...plusFeedback(h, 'example', action.Settings, stepSize)}));
 pages.push(result);
}
pages.sort((a,b) => {
 const rank = p => root.Pages.Pages.indexOf(p.id) < 0 ? 2 : root.Pages.Pages.indexOf(p.id);
 return rank(a)-rank(b);
});
await archive.close();
profiles[device] = pages;
}
const librarySettings = [{control:'library'}, {control:'display'}, {control:'filter',filter:'park'}, {control:'filter',filter:'status'}];
const markerSettings = ['start','gravity','incline','end'].map(marker => ({control:'marker',marker}));
profiles.plusCases = profiles.plus.map(page => ({name:page.name, dials:page.dials}));
const addCase = (name, client, menu, settings, proposals = []) => profiles.plusCases.push({name,
 dials: settings.map((setting,column) => ({position:`${column},0`, ...plusFeedback(client,'example',{...setting,menu,column},1,proposals[column])}))});
const long = client();
long.state.library.park_filter.value = 'Park A';
long.state.library.park_filter.options.find(option => option.value === 'Park B').label = '<Long park> 🎢 東京 '.repeat(20);
addCase('Library · proposed filters / long text',long,'library',librarySettings,[undefined,undefined,'Park B','video_ready']);
const mixed = client();
for (const [index,status] of [[2,'pending'],[3,'failed']]) {
 Object.assign(mixed.state.markers[index],{status,preview:{sample:60,time_seconds:1.2,label:'00:01.20'},request_id:'example',error:status==='failed'?'analysis_failed':null,
  availability:{preview:{available:true},apply:{available:true},discard:{available:true}}});
}
addCase('Markers · Applied / Preview / Pending / Failed',mixed,'markers',markerSettings);
for (const [reason,label] of Object.entries({input_focus:'Editing',dialog_open:'Dialog open',background:'Background',busy:'Busy'})) {
 const locked = client(); locked.state.availability = {available:false,reason};
 addCase(`Library · ${label}`,locked,'library',librarySettings);
}
const empty = client(); empty.state.playback=null; empty.state.selection=null; empty.state.view=null; empty.state.curves=[]; empty.state.markers=[];
for (const operation of Object.keys(empty.state.controls)) if (!operation.startsWith('library.')) empty.state.controls[operation]={available:false,reason:'no_recording'};
addCase('Playback · no recording',empty,'playback',[{control:'position'},{control:'speed'},{control:'view'},{control:'zoom_selection'}]);
empty.state.target=null; empty.state.library=null; empty.state.availability={available:false,reason:'no_active_window'};
addCase('Library · no Explorer',empty,'library',librarySettings);
const offline=client(); offline.state=undefined; offline.status='disconnected';
addCase('Library · offline',offline,'library',librarySettings);
console.log(JSON.stringify(profiles));
"""


def _feedback() -> dict[str, Any]:
    """Compile the existing TypeScript and render fixed examples without installing it."""
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js from the Windows development setup is required")
    subprocess.run(
        [
            node,
            str(PLUGIN / "scripts/build-plugin.mjs"),
        ],
        cwd=ROOT,
        check=True,
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", _FEEDBACK],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    data: dict[str, Any] = json.loads(result.stdout)
    return data


def _text(
    painter: QPainter,
    rect: QRectF,
    value: str,
    size: int = 14,
    color: str = "#e2e8f0",
    weight: int = 400,
) -> None:
    """Draw one bounded line with the production layout's font size and weight."""
    font = QFont("Segoe UI")
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.DemiBold if weight >= 600 else QFont.Weight.Normal)
    painter.setFont(font)
    painter.setPen(QColor(color))
    value = painter.fontMetrics().elidedText(value, Qt.TextElideMode.ElideRight, int(rect.width()))
    painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, value)


def _svg(painter: QPainter, value: str, rect: QRectF) -> None:
    """Draw a production SVG and reject invalid artwork before publishing the image."""
    if value.startswith("data:image/svg+xml;base64,"):
        value = base64.b64decode(value.split(",", 1)[1]).decode("utf-8")
    elif not value.lstrip().startswith("<"):
        value = (
            ROOT / ".tmp/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin" / value
        ).read_text(encoding="utf-8")
    renderer = QSvgRenderer(QByteArray(value.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("Invalid Stream Deck example SVG")
    painter.save()
    painter.setClipRect(rect)
    renderer.render(painter, rect)
    painter.restore()


def _profile_key(painter: QPainter, key: dict[str, Any], rect: QRectF) -> None:
    """Draw one production key image with its two-line native caption."""
    if key["image"].startswith("data:image/png;base64,"):
        image = QImage.fromData(base64.b64decode(key["image"].split(",", 1)[1]))
        painter.drawImage(rect, image)
    else:
        _svg(painter, key["image"], rect)
    scale = rect.width() / 100
    for index, line in enumerate(key["title"].split("\n")[:2]):
        _text(
            painter,
            QRectF(
                rect.x() + 4 * scale,
                rect.y() + (65 + index * 14) * scale,
                92 * scale,
                15 * scale,
            ),
            line,
            int(11 * scale),
        )


@cache
def _plus_layout(name: str) -> dict[str, Any]:
    """Read a built Plus layout for production feedback rendering.

    Args:
        name: Plugin-relative layout path.

    Returns:
        The compiled layout definition.

    Raises:
        OSError: The built layout cannot be read.
        ValueError: The layout contains invalid JSON.
    """
    path = ROOT / ".tmp/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _touch_field(
    painter: QPainter,
    layout: dict[str, Any],
    dial: dict[str, Any],
    left: float,
    top: float,
    scale: float = 1,
) -> None:
    """Draw the production Plus layout without changing its optical axes.

    Args:
        painter: Destination painter.
        layout: Production layout items.
        dial: Production feedback payload.
        left: Field's horizontal origin.
        top: Field's vertical origin.
        scale: Display scale; one preserves the native 200 by 100 pixels.
    """
    layout = _plus_layout(dial["layout"]) if "layout" in dial else layout
    for field in layout["items"]:
        x, y, width, height = field["rect"]
        rect = QRectF(left + x * scale, top + y * scale, width * scale, height * scale)
        value = dial[field["key"]]
        if field["type"] == "pixmap":
            _svg(painter, value, rect)
        else:
            _text(
                painter,
                rect,
                value["value"] if isinstance(value, dict) else value,
                round(field["font"]["size"] * scale),
                value.get("color", field["color"]) if isinstance(value, dict) else field["color"],
                field["font"].get("weight", 400),
            )


def _render_native_strips(output: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Render all views and state examples at one physical pixel per native pixel.

    Args:
        output: Destination directory.
        cases: Fixed production feedback cases.

    Returns:
        Image dimensions, native field size and covered cases.

    Raises:
        OSError: The image cannot be saved.
    """
    layout = json.loads((PLUGIN / "devices/layouts/plus.json").read_text(encoding="utf-8"))
    canvas = QImage(840, 60 + len(cases) * 140, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#0b1422"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        _text(
            painter,
            QRectF(20, 6, 800, 24),
            "Plus · native 200×100 fields · software examples",
            18,
            weight=600,
        )
        for index, case in enumerate(cases):
            top = 60 + index * 140
            _text(painter, QRectF(20, top - 26, 800, 22), case["name"], 14)
            for dial in case["dials"]:
                column = int(dial["position"].split(",")[0])
                _touch_field(painter, layout, dial, 20 + column * 200, top)
    finally:
        painter.end()
    filename = "stream-deck-plus-touch-strips.png"
    if not canvas.save(str(output / filename)):
        raise OSError("Cannot save native Plus strip examples")
    return {
        "image": filename,
        "size": [canvas.width(), canvas.height()],
        "field_size": [200, 100],
        "cases": [case["name"] for case in cases],
    }


def _render_neo(output: Path, pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Render real Neo profile pages, InfoBar layout and native Touch Point positions."""
    layout = json.loads((PLUGIN / "devices/layouts/neo.json").read_text(encoding="utf-8"))
    canvas = QImage(1220, 100 + ((len(pages) + 1) // 2) * 390, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#0b1422"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        _text(
            painter,
            QRectF(28, 15, 1160, 38),
            "Stream Deck Neo · Keys, InfoBar and Touch Points",
            24,
            weight=600,
        )
        _text(
            painter,
            QRectF(28, 55, 1160, 26),
            "Software illustration · fixed examples · native page navigation · not a hardware photograph",
            color="#9fb6cf",
        )
        for index, page in enumerate(pages):
            x, y = 28 + (index % 2) * 594, 100 + (index // 2) * 390
            painter.setBrush(QColor("#142237"))
            painter.setPen(QColor("#34506d"))
            painter.drawRoundedRect(QRectF(x, y, 566, 374), 18, 18)
            _text(painter, QRectF(x + 22, y + 8, 522, 30), page["name"], 18, weight=600)
            for key in page["keys"]:
                column, row = map(int, key["position"].split(","))
                left, top = x + 55 + column * 116, y + 45 + row * 112
                _profile_key(painter, key, QRectF(left, top, 100, 100))
            left, top, scale = x + 109, y + 277, 1.5
            painter.fillRect(QRectF(left, top, 348, 75), QColor("#0b1422"))
            for field in layout["items"]:
                a, b, width, height = field["rect"]
                rect = QRectF(left + a * scale, top + b * scale, width * scale, height * scale)
                if field["type"] == "pixmap":
                    _svg(painter, page["infobar"][field["key"]], rect)
                else:
                    _text(
                        painter,
                        rect,
                        page["infobar"][field["key"]],
                        int(field["font"]["size"] * scale),
                        field["color"],
                    )
            for center, arrow in ((x + 68, "‹"), (x + 498, "›")):
                painter.setBrush(QColor("#203e5d"))
                painter.setPen(QColor("#78cfff"))
                painter.drawEllipse(QRectF(center - 21, top + 16, 42, 42))
                _text(painter, QRectF(center - 8, top + 14, 24, 42), arrow, 30, "#bcecff", 600)
    finally:
        painter.end()
    filename = "stream-deck-neo-controls.png"
    if not canvas.save(str(output / filename)):
        raise OSError("Cannot save the Neo controls image")
    return {
        "image": filename,
        "size": [canvas.width(), canvas.height()],
        "native_pages": ["Start", "Quick controls"],
        "touch_points": {"left": "Previous native page", "right": "Next native page"},
        "pages": [
            {
                "name": page["name"],
                "keys": [
                    {key: value for key, value in item.items() if key != "image"}
                    for item in page["keys"]
                ],
                "infobar": {key: value for key, value in page["infobar"].items() if key != "icon"},
            }
            for page in pages
        ],
    }


def _render_plus(output: Path, pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Render every real Plus page with aligned keys, touch fields and four dials."""
    layout = json.loads((PLUGIN / "devices/layouts/plus.json").read_text(encoding="utf-8"))
    canvas = QImage(1620, 100 + ((len(pages) + 1) // 2) * 490, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#0b1422"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        _text(
            painter,
            QRectF(28, 15, 1564, 38),
            "Stream Deck + · All profile pages, touch strip and dials",
            24,
            weight=600,
        )
        _text(
            painter,
            QRectF(28, 55, 1564, 26),
            "Software illustration from the actual profile · fixed example values · not a hardware photograph or acceptance result",
            color="#9fb6cf",
        )
        for index, page in enumerate(pages):
            x = 425 if index == len(pages) - 1 and len(pages) % 2 else 28 + (index % 2) * 794
            y = 100 + (index // 2) * 490
            painter.setBrush(QColor("#142237"))
            painter.setPen(QColor("#34506d"))
            painter.drawRoundedRect(QRectF(x, y, 770, 470), 18, 18)
            _text(painter, QRectF(x + 22, y + 8, 726, 30), page["name"], 18, weight=600)
            for key in page["keys"]:
                column, row = map(int, key["position"].split(","))
                _profile_key(
                    painter,
                    key,
                    QRectF(x + 80 + column * 170, y + 45 + row * 112, 100, 100),
                )
            painter.fillRect(QRectF(x + 45, y + 280, 680, 85), QColor("#0b1422"))
            for dial in page["dials"]:
                column = int(dial["position"].split(",")[0])
                _touch_field(painter, layout, dial, x + 45 + column * 170, y + 280, 0.85)
            assigned = {
                int(dial["position"].split(",")[0]) for dial in page["dials"] if dial["title"]
            }
            for column in range(4):
                center = x + 130 + column * 170
                painter.setBrush(QColor("#203e5d" if column in assigned else "#122033"))
                painter.setPen(QColor("#78cfff" if column in assigned else "#34506d"))
                painter.drawEllipse(QRectF(center - 25, y + 383, 50, 50))
                painter.drawLine(int(center), int(y + 386), int(center), int(y + 396))
                _text(painter, QRectF(center - 4, y + 438, 20, 20), str(column + 1), 12, "#9fb6cf")
    finally:
        painter.end()
    if not canvas.save(str(output / IMAGE)):
        raise OSError("Cannot save the Plus controls image")
    return {
        "image": IMAGE,
        "size": [canvas.width(), canvas.height()],
        "touch_field_scale": 0.85,
        "pages": [
            {
                "name": page["name"],
                "keys": [
                    {key: value for key, value in item.items() if key != "image"}
                    for item in page["keys"]
                ],
                "dials": [
                    {
                        key: value
                        for key, value in dial.items()
                        if key not in {"icon", "band", "statusIcon"}
                    }
                    for dial in page["dials"]
                ],
            }
            for page in pages
        ],
    }


def _render_mobile(output: Path, pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Render the limited Mobile profile as four six-key page previews."""
    canvas = QImage(1040, 100 + ((len(pages) + 1) // 2) * 320, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#0b1422"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        _text(
            painter,
            QRectF(28, 15, 984, 38),
            "Stream Deck Mobile · Six-key preview",
            24,
            weight=600,
        )
        _text(
            painter,
            QRectF(28, 55, 984, 26),
            "Software illustration · fixed examples · six-key landscape layout · not a hardware photograph",
            color="#9fb6cf",
        )
        for index, page in enumerate(pages):
            x, y = 28 + (index % 2) * 504, 100 + (index // 2) * 320
            painter.setBrush(QColor("#142237"))
            painter.setPen(QColor("#34506d"))
            painter.drawRoundedRect(QRectF(x, y, 480, 300), 18, 18)
            _text(painter, QRectF(x + 22, y + 8, 436, 30), page["name"], 18, weight=600)
            for key in page["keys"]:
                column, row = map(int, key["position"].split(","))
                _profile_key(
                    painter,
                    key,
                    QRectF(x + 60 + column * 130, y + 45 + row * 120, 100, 100),
                )
    finally:
        painter.end()
    filename = "stream-deck-mobile-controls.png"
    if not canvas.save(str(output / filename)):
        raise OSError("Cannot save the Mobile preview image")
    return {
        "image": filename,
        "size": [canvas.width(), canvas.height()],
        "key_layout": {"rows": 2, "columns": 3},
        "pages": [
            {
                "name": page["name"],
                "keys": [
                    {key: value for key, value in item.items() if key != "image"}
                    for item in page["keys"]
                ],
            }
            for page in pages
        ],
    }


def _render_overview(output: Path, pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a readable README close-up of the actual Plus Playback page."""
    index = next(index for index, page in enumerate(pages) if page["name"] == "Playback / Navigate")
    source = QImage(str(output / IMAGE))
    panel = source.copy(28 + (index % 2) * 794, 100 + (index // 2) * 490, 770, 470)
    canvas = QImage(1040, 730, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#0b1422"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    try:
        _text(
            painter,
            QRectF(28, 14, 984, 38),
            "Stream Deck + · Playback at your fingertips",
            24,
            weight=600,
        )
        _text(
            painter,
            QRectF(28, 56, 984, 26),
            "Software illustration · fixed example values · not a hardware photograph",
            color="#9fb6cf",
        )
        painter.drawImage(QRectF(28, 100, 984, 600), panel)
    finally:
        painter.end()
    filename = "stream-deck-overview.png"
    if not canvas.save(str(output / filename)):
        raise OSError("Cannot save the Stream Deck overview image")
    return {"image": filename, "size": [1040, 730], "device": "plus", "page": "Playback / Navigate"}


def render_reference(output: Path) -> None:
    """Write Plus/Neo illustrations and the limited Mobile preview and their fixed example-value manifest.

    Args:
        output: Destination directory for the PNG images and their shared JSON manifest.

    Raises:
        OSError: Inputs cannot be read or outputs cannot be written.
        RuntimeError: The locked Node.js development tools are unavailable.
        subprocess.CalledProcessError: Compilation or production feedback fails.
        ValueError: A generated SVG is invalid.
    """
    data = _feedback()
    application = QGuiApplication.instance() or QGuiApplication([])
    assert isinstance(application, QGuiApplication)
    output.mkdir(parents=True, exist_ok=True)
    plus = _render_plus(output, data["plus"])
    inputs = [
        "scripts/render_stream_deck_reference.py",
        "tests/fixtures/stream_deck_protocol.json",
        "plugins/stream-deck/src/feedback.ts",
        "plugins/stream-deck/src/device-feedback.ts",
        "plugins/stream-deck/src/plus-feedback.ts",
        "plugins/stream-deck/src/navigation.ts",
        "plugins/stream-deck/devices/layouts/plus.json",
        "plugins/stream-deck/devices/layouts/neo.json",
        "plugins/stream-deck/scripts/build-profiles.mjs",
        "plugins/stream-deck/scripts/build-plugin.mjs",
        "plugins/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/manifest.json",
        "plugins/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/imgs/plugin@2x.png",
    ]
    inputs.extend(
        f"plugins/stream-deck/devices/backgrounds/{menu}.svg"
        for menu in ("library", "playback", "curves", "markers")
    )
    manifest = {
        "image": IMAGE,
        "kind": "software illustration; not hardware acceptance",
        "language": "en",
        "size": plus["size"],
        "font": "Segoe UI",
        "plus": plus,
        "inputs": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs},
    }
    manifest["neo"] = _render_neo(output, data["neo"])
    manifest["mobile"] = _render_mobile(output, data["mobile"])
    manifest["overview"] = _render_overview(output, data["plus"])
    manifest["native_strips"] = _render_native_strips(output, data["plusCases"])
    (output / MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Rendered {IMAGE}, stream-deck-plus-touch-strips.png, stream-deck-neo-controls.png, stream-deck-mobile-controls.png and stream-deck-overview.png: fixed software examples, no device or application connection",
    )


def main() -> None:
    """Render the documentation example at the standard or explicitly selected destination."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/images")
    arguments = parser.parse_args()
    render_reference(arguments.output.resolve())


if __name__ == "__main__":
    main()
