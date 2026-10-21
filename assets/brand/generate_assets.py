#!/usr/bin/env python3
"""Create web-ready KURANEA artwork from the three unmodified supplied PNGs."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
GENERATED = ROOT / "generated"
THEME_BRAND = ROOT.parents[1] / "themes" / "kuranea" / "assets" / "img" / "brand"
NAVY = (11, 27, 48)
PAPER = (250, 248, 243)


def save_png(image: Image.Image, path: Path) -> None:
    image.save(path, format="PNG", optimize=True, compress_level=9)


def trim_alpha(image: Image.Image, padding: int) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value >= 12 else 0).getbbox()
    if bbox is None:
        raise ValueError("Source logo has no visible pixels")
    left, top, right, bottom = bbox
    return image.crop((max(0, left - padding), max(0, top - padding), min(image.width, right + padding), min(image.height, bottom + padding)))


def contain_on_square(image: Image.Image, size: int, background: tuple[int, int, int]) -> Image.Image:
    canvas = Image.new("RGB", (size, size), background)
    contained = ImageOps.contain(image.convert("RGBA"), (size, size), Image.Resampling.LANCZOS)
    x = (size - contained.width) // 2
    y = (size - contained.height) // 2
    canvas.paste(contained, (x, y), contained.getchannel("A"))
    return canvas


def recolor_navy_for_dark_background(image: Image.Image) -> Image.Image:
    """Keep the official geometry and gold; lift only dark blue pixels for contrast."""
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    hsv_pixels = rgba.convert("HSV").load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            hue, saturation, value = hsv_pixels[x, y]
            if 125 <= hue <= 180 and saturation >= 45 and value <= 170:
                lift = 0.76 + (value / 255) * 0.24
                pixels[x, y] = (
                    round(247 * lift),
                    round(244 * lift),
                    round(235 * lift),
                    alpha,
                )
    return rgba


def write_webp(image: Image.Image, path: Path) -> None:
    image.save(path, format="WEBP", lossless=True, method=6)


def main() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    THEME_BRAND.mkdir(parents=True, exist_ok=True)

    logo = Image.open(SOURCE / "kuranea-logo.png").convert("RGBA")
    logo = trim_alpha(logo, padding=52)
    desktop = ImageOps.contain(logo, (1440, 420), Image.Resampling.LANCZOS)
    mobile = ImageOps.contain(logo, (720, 210), Image.Resampling.LANCZOS)
    light = recolor_navy_for_dark_background(logo)

    for name, image in (
        ("kuranea-logo-desktop.png", desktop),
        ("kuranea-logo-mobile.png", mobile),
        ("kuranea-logo-light.png", light),
    ):
        save_png(image, GENERATED / name)
        write_webp(image, GENERATED / name.replace(".png", ".webp"))
    save_png(desktop, THEME_BRAND / "kuranea-logo-desktop.png")
    save_png(mobile, THEME_BRAND / "kuranea-logo-mobile.png")
    save_png(light, THEME_BRAND / "kuranea-logo-light.png")
    write_webp(desktop, THEME_BRAND / "kuranea-logo-desktop.webp")
    write_webp(mobile, THEME_BRAND / "kuranea-logo-mobile.webp")
    write_webp(light, THEME_BRAND / "kuranea-logo-light.webp")

    symbol = trim_alpha(Image.open(SOURCE / "kuranea-favicon.png").convert("RGBA"), padding=10)
    # Give the official transparent symbol a quiet paper field for small browser glyphs.
    for size, filename in ((16, "favicon-16x16.png"), (32, "favicon-32x32.png")):
        icon = contain_on_square(symbol, size, PAPER)
        save_png(icon, GENERATED / filename)
        save_png(icon, THEME_BRAND / filename)
    icon32 = Image.open(GENERATED / "favicon-32x32.png").convert("RGBA")
    icon32.save(GENERATED / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32)])
    icon32.save(THEME_BRAND / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32)])

    app = Image.open(SOURCE / "kuranea-pwa-icon.png").convert("RGB")
    for size, filename in ((192, "pwa-192x192.png"), (512, "pwa-512x512.png")):
        icon = ImageOps.fit(app, (size, size), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        save_png(icon, GENERATED / filename)
        save_png(icon, THEME_BRAND / filename)
    # The standard icon already fills the canvas; the maskable derivative shrinks
    # the official full-bleed artwork to keep the central K mark inside the 80% safe area.
    maskable_source = ImageOps.contain(app, (410, 410), Image.Resampling.LANCZOS)
    maskable = Image.new("RGB", (512, 512), NAVY)
    maskable.paste(maskable_source, ((512 - maskable_source.width) // 2, (512 - maskable_source.height) // 2))
    save_png(maskable, GENERATED / "pwa-maskable-512x512.png")
    save_png(maskable, THEME_BRAND / "pwa-maskable-512x512.png")

    apple = ImageOps.fit(app, (180, 180), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    save_png(apple, GENERATED / "apple-touch-icon.png")
    save_png(apple, THEME_BRAND / "apple-touch-icon.png")

    og = Image.new("RGB", (1200, 630), PAPER)
    og_logo = ImageOps.contain(logo, (1060, 340), Image.Resampling.LANCZOS)
    og.paste(og_logo, ((1200 - og_logo.width) // 2, (630 - og_logo.height) // 2), og_logo.getchannel("A"))
    draw = ImageDraw.Draw(og)
    draw.line((180, 568, 1020, 568), fill=(180, 154, 97), width=2)
    save_png(og, GENERATED / "og-brand.png")
    save_png(og, THEME_BRAND / "og-brand.png")

    hashes = []
    for path in sorted(GENERATED.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            hashes.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (GENERATED / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    print(f"Generated official KURANEA assets in {GENERATED}")


if __name__ == "__main__":
    main()
