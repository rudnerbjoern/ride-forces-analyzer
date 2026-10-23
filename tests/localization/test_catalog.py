"""Catalog integrity, safe formatting and reproducible localized overlay labels."""

from ride_forces_analyzer.analysis.recording import source_app_configuration

# cspell:words Messpunkte Fahrtzeit Vorgabe Deutsch Neigung geladen autouse textbbox Rechts Beschleunigung Bremsen
# cspell:words Préréglage chargé Inclinaison

from dataclasses import replace
from collections.abc import Iterator
from string import Formatter
from typing import Any, Literal, get_args

from PIL import ImageDraw
import pytest

from ride_forces_analyzer.explorer import ExplorerData, format_sample_time, load_recording
from ride_forces_analyzer.i18n import (
    LANGUAGES,
    LANGUAGE_CHOICES,
    Language,
    get_language,
    set_language,
    tr,
    diagnostic_message,
)
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSettings,
    PROFILES,
    prepare_export,
)
from ride_forces_analyzer.translations_de import DIAGNOSTIC_GERMAN, GERMAN
from ride_forces_analyzer.translations_fr import DIAGNOSTIC_FRENCH, FRENCH
from ride_forces_analyzer.storage.export_models import SavedPreset, SavedBatch
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.rendering.batches import make_job
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from pathlib import Path
import ast
import re


@pytest.fixture(scope="module", name="manta")
def localized_recording() -> ExplorerData:
    """Share immutable recording data; language and patches remain isolated per test."""
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    assert isinstance(data, ExplorerData)
    return data


@pytest.fixture(autouse=True)
def english_after_test() -> Iterator[None]:
    previous = get_language()
    yield
    set_language(previous)


@pytest.mark.parametrize("catalog", [GERMAN, FRENCH], ids=["de", "fr"])
def test_catalog_preserves_placeholders(catalog: dict[str, str]) -> None:
    def fields(value: str) -> list[tuple[str | None, str | None, str | None]]:
        return sorted(
            (name, spec, conversion)
            for _, name, spec, conversion in Formatter().parse(value)
            if name is not None
        )

    assert catalog.keys() == GERMAN.keys()
    for source, translated in catalog.items():
        assert translated.strip(), source
        assert fields(translated) == fields(source), source


def test_language_registration_matches_the_typed_public_contract() -> None:
    assert set(LANGUAGES) == set(get_args(Language))
    assert LANGUAGE_CHOICES == tuple(LANGUAGES)


def test_declared_diagnostics_and_literal_ui_templates_have_translations() -> None:
    root = Path("src/ride_forces_analyzer")
    codes: set[str] = set()
    for path in (root / "importers").glob("*.py"):
        codes.update(re.findall(r'"([A-Z][A-Z0-9_]{3,})"', path.read_text(encoding="utf-8")))
    assert codes - {"DEFAULT_LIMITS"} <= DIAGNOSTIC_GERMAN.keys()
    assert DIAGNOSTIC_FRENCH.keys() == DIAGNOSTIC_GERMAN.keys()
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
                    assert first.value in FRENCH, (path, node.lineno, first.value)


def test_french_formatting_and_diagnostics_preserve_opaque_source_values() -> None:
    set_language("fr")
    assert str(tr("{0:,}", 12345)) == "12\u202f345"
    assert str(tr("{0:+.2f} g", 1.234)) == "+1,23 g"
    assert str(tr("Loaded preset: {0}", "Name {0} 1.25")) == "Préréglage chargé : Name {0} 1.25"
    assert format_sample_time(123, 50) == "00:02.23"
    assert (
        diagnostic_message("GRAVITY_UNAVAILABLE", "original")
        == DIAGNOSTIC_FRENCH["GRAVITY_UNAVAILABLE"]
    )
    assert diagnostic_message("UNKNOWN_FUTURE_CODE", "original") == "original"


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


@pytest.mark.parametrize("language", ["de", "fr"])
def test_saved_language_roundtrip_is_explicit(
    manta: ExplorerData,
    export_directory: Path,
    language: Language,
) -> None:
    assert manta.analysis is not None
    chosen = SavedPreset(
        name=language,
        settings=ExportSettings(language=language, layout="orbit"),
        analysis_configuration=source_app_configuration(),
        schema_version=1,
        smoothing_window=11,
        range_mode="markers",
    )
    store = ExportStore(export_directory / "languages.sqlite3")
    store.save_preset(chosen)
    store.save_batch(
        SavedBatch(name="Mixed", jobs=(make_job(manta.analysis, chosen),), schema_version=1),
    )
    assert ExportStore(store.path).presets()[0].settings.language == language
    assert ExportStore(store.path).batch("Mixed").jobs[0].preset.settings.language == language


@pytest.mark.parametrize("layout", [profile[0] for profile in PROFILES])
@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
@pytest.mark.parametrize("language", ["de", "fr"])
def test_overlay_labels_fit_and_language_is_reproducible(
    manta: ExplorerData,
    layout: ExportLayout,
    aspect: Literal["landscape", "portrait"],
    language: Language,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    settings = ExportSettings(layout=layout, aspect=aspect, language=language)
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
    timeline = prepare_export(manta.analysis, settings, 3500, 3700)
    set_language("en")
    first = OverlayRenderer(timeline).render_sample(3600)
    set_language("de")
    second = OverlayRenderer(timeline).render_sample(3600)
    first_pixels = first.tobytes()
    assert first_pixels == second.tobytes()
    assert calls and any(
        ("Neigung" if language == "de" else "Inclinaison") in text for text, _, _ in calls
    )
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
    assert first_pixels != english.tobytes()
