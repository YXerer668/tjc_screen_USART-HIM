from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .layout import resolve_page_layout
from .scene import SceneModel, WidgetSpec


def render_scene_preview(
    scene: SceneModel,
    out_path: str | Path,
    page_id: str = "page0",
    manifest_assets: dict[str, Any] | None = None,
) -> Path:
    width = int(scene.canvas["width"])
    height = int(scene.canvas["height"])
    background = int(scene.canvas.get("background_color", 65535))
    image = Image.new("RGBA", (width, height), _rgb565_to_rgb(background) + (255,))
    draw = ImageDraw.Draw(image)
    asset_lookup = _build_asset_lookup(scene, manifest_assets or {})

    page = next(page for page in scene.pages if page.id == page_id)
    widgets = resolve_page_layout(page.widgets, page.layout, width, height)

    for widget in widgets:
        _draw_widget(draw, image, widget, asset_lookup)

    target = Path(out_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(target)
    return target


def _draw_widget(
    draw: ImageDraw.ImageDraw,
    canvas: Image.Image,
    widget: WidgetSpec,
    manifest_assets: dict[str, Any],
) -> None:
    x = int(widget.x or 0)
    y = int(widget.y or 0)
    w = int(widget.w or 0)
    h = int(widget.h or 0)
    if w <= 0 or h <= 0:
        return

    background = _rgb565_to_rgb(int(widget.style.get("background_color", 65535)))
    foreground = _rgb565_to_rgb(int(widget.style.get("foreground_color", 0)))
    border = _rgb565_to_rgb(int(widget.style.get("border_color", 0xC618)))
    shadow = tuple(max(channel - 28, 0) for channel in background)

    if widget.type == "text":
        draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill=background)
        _draw_text(draw, widget.text or "", (x, y, x + w, y + h), foreground, anchor="lt")
        return

    if widget.type == "number":
        draw.rounded_rectangle((x + 4, y + 6, x + w + 4, y + h + 6), radius=16, fill=shadow)
        draw.rounded_rectangle((x, y, x + w, y + h), radius=16, fill=background, outline=border, width=2)
        value_text = str(widget.value if widget.value is not None else 0)
        _draw_text(draw, value_text, (x, y, x + w, y + h), foreground, anchor="mm")
        return

    if widget.type in {"button", "image"}:
        draw.rounded_rectangle((x + 4, y + 6, x + w + 4, y + h + 6), radius=18, fill=shadow)
        draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=background, outline=border, width=2)

        asset_ref = widget.resources.get("asset")
        asset_info = manifest_assets.get(asset_ref) if asset_ref else None
        _paste_widget_asset(canvas, widget, asset_info)

        if widget.type == "button" and widget.text:
            band_h = min(34, max(24, h // 3))
            band_color = tuple(max(channel - 24, 0) for channel in background)
            draw.rounded_rectangle((x, y + h - band_h, x + w, y + h), radius=18, fill=band_color)
            _draw_text(draw, widget.text, (x, y + h - band_h, x + w, y + h), foreground, anchor="mm")
        return


def _paste_widget_asset(canvas: Image.Image, widget: WidgetSpec, asset_info: dict[str, Any] | None) -> None:
    if not asset_info:
        return
    variant = asset_info.get("variants", {}).get("normal") or asset_info
    png_path = variant.get("normalized_png")
    if not png_path:
        return

    source = Path(png_path)
    if not source.exists():
        return

    image = Image.open(source).convert("RGBA")
    x = int(widget.x or 0)
    y = int(widget.y or 0)
    w = int(widget.w or 0)
    h = int(widget.h or 0)
    pad = 14

    target_h = h - pad * 2
    if widget.type == "button" and widget.text:
        target_h -= min(34, max(24, h // 3))
    target_w = w - pad * 2
    if target_w <= 8 or target_h <= 8:
        return

    image.thumbnail((target_w, target_h))
    paste_x = x + (w - image.width) // 2
    paste_y = y + pad + max((target_h - image.height) // 2, 0)
    canvas.alpha_composite(image, (paste_x, paste_y))


def _build_asset_lookup(scene: SceneModel, manifest_assets: dict[str, Any]) -> dict[str, Any]:
    if manifest_assets:
        return manifest_assets

    lookup: dict[str, Any] = {}
    for key, asset in scene.assets.items():
        source = asset.normal or asset.source
        if not source:
            continue
        lookup[key] = {
            "variants": {
                "normal": {
                    "normalized_png": source,
                }
            }
        }
    return lookup


def _draw_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    color: tuple[int, int, int],
    anchor: str = "mm",
) -> None:
    x1, y1, x2, y2 = box
    width = max(x2 - x1, 1)
    height = max(y2 - y1, 1)
    font = _load_font(max(min(height - 8, 32), 14))

    if anchor == "lt":
        draw.text((x1 + 8, y1 + 6), text, fill=color, font=font)
        return

    draw.text(((x1 + x2) // 2, (y1 + y2) // 2), text, fill=color, font=font, anchor="mm")


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\nsimsun.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _rgb565_to_rgb(value: int) -> tuple[int, int, int]:
    red = ((value >> 11) & 0x1F) * 255 // 31
    green = ((value >> 5) & 0x3F) * 255 // 63
    blue = (value & 0x1F) * 255 // 31
    return red, green, blue
