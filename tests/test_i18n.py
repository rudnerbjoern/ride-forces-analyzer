"""Catalog integrity, safe formatting and reproducible localized overlay labels."""

# cspell:words Messpunkte Fahrtzeit Vorgabe Deutsch Neigung geladen autouse textbbox Rechts Beschleunigung Bremsen

from dataclasses import replace
from collections.abc import Iterator
from string import Formatter
from typing import Any, Literal

from PIL import ImageDraw
import pytest

from ride_forces_analyzer.explorer import ExplorerData, format_sample_time
from ride_forces_analyzer.i18n import get_language, set_language, tr
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSettings,
    PROFILES,
    prepare_export,
)
from ride_forces_analyzer.translations import DIAGNOSTIC_GERMAN, GERMAN
from ride_forces_analyzer.storage.export_models import SavedPreset, SavedBatch
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.rendering.batches import make_job
from pathlib import Path
import json
import ast
import re
from test_rendering import (
    manta as manta,
    export_directory as export_directory,
)


@pytest.fixture(autouse=True)
def english_after_test() -> Iterator[None]:
    previous = get_language()
    yield
    set_language(previous)


@pytest.mark.parametrize("source", tuple(GERMAN))
def test_german_catalog_preserves_placeholders(source: str) -> None:
    def fields(value: str) -> list[tuple[str | None, str | None, str | None]]:
        return sorted(
            (name, spec, conversion)
            for _, name, spec, conversion in Formatter().parse(value)
            if name is not None
        )

    translated = GERMAN[source]
    assert translated.strip()
    assert fields(translated) == fields(source)


def test_declared_diagnostics_and_literal_ui_templates_have_translations() -> None:
    root = Path("src/ride_forces_analyzer")
    codes: set[str] = set()
    for path in (root / "importers").glob("*.py"):
        codes.update(re.findall(r'"([A-Z][A-Z0-9_]{3,})"', path.read_text(encoding="utf-8")))
    assert codes - {"DEFAULT_LIMITS"} <= DIAGNOSTIC_GERMAN.keys()
    for path in [
        *(root / "ui").glob("*.py"),
        *(root / "rendering").glob("*.py"),
        root / "explorer.py",
    ]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and node.args:
                function = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                first = node.args[0]
                if (
                    function in ("tr", "_tr")
                    and isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                ):
                    assert first.value in GERMAN, (path, node.lineno, first.value)


def test_language_formats_numbers_but_preserves_source_values_and_clock() -> None:
    set_language("en")
    text = tr("{0} samples", 12345)
    nested = tr(
        "Calibrated forces · {0}\nAlign the exported clip with your Onride video in Resolve.",
        text,
    )
    assert str(text) == "12345 samples"
    set_language("de")
    assert str(text) == "12345 Messpunkte"
    assert "12345 Messpunkte" in str(nested)
    assert tr("{0:+.2f} g", 1.234) == "+1,23 g"
    source_name = "Ride {0} · Left · Links"
    assert str(tr("Loaded preset: {0}", source_name)) == "Vorgabe geladen: " + source_name
    assert format_sample_time(4597, 50.0) == "01:31.47"
    assert tr("Replay {0}", "01:31.47") == "Fahrtzeit 01:31.47"


def test_diagnostic_translation_keeps_original_messages(manta: ExplorerData) -> None:
    original = manta.notes
    diagnostics = manta.source.diagnostics
    set_language("de")
    localized = manta.localized_notes
    for item in diagnostics:
        assert item.code in localized and item.json_path in localized
    assert manta.notes == original and manta.source.diagnostics is diagnostics
    set_language("en")
    assert manta.localized_notes == original


def test_saved_language_roundtrip_and_old_presets_default_to_english(
    manta: ExplorerData,
    export_directory: Path,
) -> None:
    chosen = SavedPreset(name="Deutsch", settings=ExportSettings(language="de", layout="orbit"))
    payload = json.loads(chosen.model_dump_json())
    del payload["settings"]["language"]
    assert SavedPreset.model_validate_json(json.dumps(payload)).settings.language == "en"
    store = ExportStore(export_directory / "languages.sqlite3")
    store.save_preset(chosen)
    store.save_batch(SavedBatch(name="Mixed", jobs=(make_job(manta, chosen),)))
    assert ExportStore(store.path).presets()[0].settings.language == "de"
    assert ExportStore(store.path).batch("Mixed").jobs[0].preset.settings.language == "de"


@pytest.mark.parametrize("layout", [profile[0] for profile in PROFILES])
@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_german_overlay_labels_fit_and_language_is_reproducible(
    manta: ExplorerData,
    layout: ExportLayout,
    aspect: Literal["landscape", "portrait"],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = ExportSettings(layout=layout, aspect=aspect, language="de")
    calls: list[tuple[str, tuple[int, int], tuple[float, float, float, float]]] = []
    original = ImageDraw.ImageDraw.text

    def checked_text(
        self: ImageDraw.ImageDraw,
        xy: tuple[float, float],
        text: str,
        **kwargs: Any,
    ) -> None:
        # Record actual raster glyph geometry, including anchors and font metrics.
        bounds = self.textbbox(xy, text, font=kwargs.get("font"), anchor=kwargs.get("anchor"))
        calls.append((str(text), getattr(self, "_image").size, bounds))
        original(self, xy, text, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", checked_text)
    timeline = prepare_export(manta, settings, 3500, 3700)
    set_language("en")
    first = OverlayRenderer(timeline).render_sample(3600)
    set_language("de")
    second = OverlayRenderer(timeline).render_sample(3600)
    assert first.tobytes() == second.tobytes()
    assert calls and any("Neigung" in text for text, _, _ in calls)
    assert not any("Hz" in text or "fps" in text for text, _, _ in calls)
    assert not any("G-ORBIT" in text for text, _, _ in calls)
    if layout == "orbit":
        assert not any("Replay" in text or "Fahrtzeit" in text for text, _, _ in calls)
        assert not any(
            text
            in {
                "Right",
                "Left",
                "Acceleration",
                "Braking",
                "Rechts",
                "Links",
                "Beschleunigung",
                "Bremsen",
            }
            for text, _, _ in calls
        )
    for text, (width, height), (left, top, right, bottom) in calls:
        assert 0 <= left <= right <= width and 0 <= top <= bottom <= height, (
            text,
            (left, top, right, bottom),
            (width, height),
        )
    english = OverlayRenderer(
        replace(timeline, settings=replace(settings, language="en")),
    ).render_sample(3600)
    assert first.tobytes() != english.tobytes()
