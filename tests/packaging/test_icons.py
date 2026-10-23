"""Native icon containers retain the same transparent artwork as the window icon."""

# cspell:words icns getimage getchannel getpixel

from pathlib import Path

from PIL import Image, IcoImagePlugin

from ride_forces_analyzer.ui.icons import ICON_SIZES, render_icon
from scripts.build_icons import build_icons


def test_native_formats_preserve_sizes_transparency_and_shared_artwork(
    export_directory: Path,
) -> None:
    icons = build_icons(export_directory / "icons")

    def expected(size: int) -> bytes:
        image = render_icon(size)
        return bytes(image.constBits())

    with Image.open(icons / "app-icon.ico") as icon:
        assert isinstance(icon, IcoImagePlugin.IcoImageFile)
        assert icon.ico.sizes() == {(size, size) for size in ICON_SIZES if size <= 256}
        for size in (16, 32, 256):
            assert icon.ico.getimage((size, size)).convert("RGBA").tobytes() == expected(size)
    with Image.open(icons / "app-icon.icns") as icon:
        assert icon.size == (1024, 1024)
        assert icon.convert("RGBA").tobytes() == expected(1024)
    with Image.open(icons / "app-icon.png") as icon:
        assert icon.size == (512, 512)
        assert icon.convert("RGBA").tobytes() == expected(512)
        assert icon.getchannel("A").getpixel((0, 0)) == 0
