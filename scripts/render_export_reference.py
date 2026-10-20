"""Regenerate the Manta documentation images at one fixed source sample.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words segoeui LANCZOS getchannel getextrema WINDIR

import argparse
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ride_forces_analyzer.analysis.recording import (
    RecordingAnalysis,
    prepare_recording_analysis,
    source_app_configuration,
)
from ride_forces_analyzer.explorer import format_sample_time
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.layouts import export_region
from ride_forces_analyzer.rendering.model import ExportSettings, PROFILES, prepare_export

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/real/Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces"
SOURCE_SHA256 = "30cf81c360cb28f45ee97234779689bdcdd7ec3aa8fa148645a4b015771be6c6"
SAMPLE = 4782  # Zero-based source index: never search for a new peak.
SMOOTHING = 11


def load_reference(source: Path = SOURCE) -> RecordingAnalysis:
    if sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Manta source hash differs from the fixed reference recording")
    imported = import_forces(source)
    if not isinstance(imported, ImportSuccess):
        raise ValueError("Cannot import the Manta reference recording")
    configuration = source_app_configuration()
    configuration = replace(
        configuration,
        smoothing=replace(configuration.smoothing, parameters=(("window_samples", SMOOTHING),)),
    )
    analysis = prepare_recording_analysis(
        imported,
        configuration,
        revision=1,
        calculation_time=datetime.now(UTC),
    )
    if analysis.forces.smoothed.channels is None:
        reason = analysis.forces.smoothed.availability.reason
        raise ValueError(reason.message if reason else "Manta calibration unavailable")
    return analysis


def render_reference(output: Path) -> None:
    analysis = load_reference()
    first, last = analysis.source.recording.indices.start, analysis.source.recording.indices.end
    rate = analysis.time.basis.sample_rate
    assert rate is not None
    replay = format_sample_time(SAMPLE - first, rate.value)
    sample = analysis.sample(SAMPLE).smoothed
    if sample is None:
        raise ValueError("Manta reference sample unavailable")
    values = (sample.vertical, sample.lateral, sample.longitudinal)
    output.mkdir(parents=True, exist_ok=True)
    background = Image.new("RGBA", (3840, 2160), "#22313e")
    draw = ImageDraw.Draw(background)
    for y in range(0, 2160, 120):
        for x in range(0, 3840, 120):
            if (x // 120 + y // 120) % 2:
                draw.rectangle((x, y, x + 119, y + 119), fill="#334654")
    sheet = Image.new("RGB", (1920, 900), "#101923")
    sheet_draw = ImageDraw.Draw(sheet)
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
    font = ImageFont.truetype(str(font_path), 27)
    small = ImageFont.truetype(str(font_path), 22)
    for index, (layout, title) in enumerate(PROFILES):
        settings = ExportSettings(
            layout=layout,
            language="en",
            aspect="landscape",
            fps=50,
            window_seconds=12.0,
            output="transparent",
            invert_vertical=True,
            invert_lateral=layout == "column",
        )
        timeline = prepare_export(analysis, settings, first, last)
        frame = OverlayRenderer(timeline).render_sample(SAMPLE)
        if frame.size != settings.dimensions or frame.getchannel("A").getextrema()[0] != 0:
            raise ValueError(f"Invalid reference canvas/transparency: {title}")
        composite = Image.alpha_composite(background, frame).convert("RGB")
        composite.save(output / f"manta-{layout}.png", optimize=True)
        x, y, width, height = export_region(settings)
        detail = composite.crop((x, y, x + width, y + height))
        detail.thumbnail((1440, 1440), Image.Resampling.LANCZOS)
        detail.save(output / f"manta-{layout}-detail.png", optimize=True)
        left, top = index % 3 * 640, index // 3 * 450
        sheet_draw.text((left + 20, top + 15), title, font=font, fill="#eff6ff")
        sheet.paste(
            composite.resize((608, 342), Image.Resampling.LANCZOS),
            (left + 16, top + 62),
        )
        sheet_draw.text(
            (left + 20, top + 412),
            f"Manta | {replay} | {values[0]:+.2f} g vertical",
            font=small,
            fill="#aec5d8",
        )
        print(f"Rendered {title}: sample {SAMPLE}, replay {replay}", flush=True)
    sheet_draw.text((1300, 485), "ONE SAMPLE. FIVE LAYOUTS.", font=font, fill="#eff6ff")
    for line, text in enumerate(
        (
            f"Replay {replay} at {rate.value:g} Hz",
            f"Vertical {values[0]:+.2f} g",
            f"Lateral {values[1]:+.2f} g",
            f"Longitudinal {values[2]:+.2f} g",
            f"Default {SMOOTHING}-sample smoothing",
            "Checkerboard = transparency",
        ),
    ):
        sheet_draw.text((1300, 550 + line * 40), text, font=small, fill="#aec5d8")
    sheet.save(output / "manta-export-themes.png", optimize=True)
    manifest = {
        "sample": SAMPLE,
        "replay": replay,
        "recording_seconds": SAMPLE / rate.value,
        "replay_seconds": (SAMPLE - first) / rate.value,
        "rate": rate.value,
        "values": values,
        "source_sha256": SOURCE_SHA256,
        "smoothing": SMOOTHING,
        "first": first,
        "last": last,
        "language": "en",
        "aspect": "landscape",
        "fps": 50,
        "window_seconds": 12.0,
        "profiles": [layout for layout, _ in PROFILES],
    }
    (output / "manta-reference.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved reference images and manifest to {output}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/images",
        help="Destination; replaces the named reference images (default: docs/images)",
    )
    args = parser.parse_args()
    render_reference(Path(args.output))


if __name__ == "__main__":
    main()
