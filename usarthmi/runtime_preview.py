from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

from PIL import Image
import serial

from .layout import resolve_page_layout
from .scene import SceneModel, WidgetSpec
from .transport import SerialTransportError, TERMINATOR


@dataclass(slots=True)
class RuntimePreviewResult:
    port: str
    baud: int
    page_id: str
    command_count: int
    commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "baud": self.baud,
            "page_id": self.page_id,
            "command_count": self.command_count,
            "commands": self.commands,
        }


def build_scene_runtime_commands(scene: SceneModel, page_id: str = "page0") -> list[str]:
    width = int(scene.canvas["width"])
    height = int(scene.canvas["height"])
    background = int(scene.canvas.get("background_color", 65535))
    widgets = _resolve_scene_widgets(scene, page_id)
    asset_lookup = _build_asset_lookup(scene)

    commands = [
        "page 0",
        f"page0.bco={background}",
        "ref 0",
        "ref_stop",
        f"fill 0,0,{width},{height},{background}",
    ]

    for widget in widgets:
        commands.extend(_widget_to_runtime_commands(widget, asset_lookup))

    commands.append("ref_star")
    return commands


def push_scene_runtime_preview(
    scene: SceneModel,
    port: str,
    baud: int = 9600,
    page_id: str = "page0",
    timeout_ms: int = 800,
    delay_ms: int = 70,
) -> RuntimePreviewResult:
    commands = build_scene_runtime_commands(scene, page_id=page_id)
    timeout_s = max(timeout_ms, 1) / 1000.0
    delay_s = max(delay_ms, 1) / 1000.0

    try:
        with serial.Serial(
            port,
            baud,
            timeout=timeout_s,
            write_timeout=timeout_s,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        ) as ser:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            for command in commands:
                ser.write(_encode_runtime_command(command))
                ser.flush()
                time.sleep(delay_s)
                if ser.in_waiting:
                    ser.read_all()
    except serial.SerialException as exc:
        raise SerialTransportError(str(exc)) from exc

    return RuntimePreviewResult(
        port=port,
        baud=baud,
        page_id=page_id,
        command_count=len(commands),
        commands=commands,
    )


def _resolve_scene_widgets(scene: SceneModel, page_id: str) -> list[WidgetSpec]:
    page = next((item for item in scene.pages if item.id == page_id), None)
    if page is None:
        raise ValueError(f"Page '{page_id}' not found in scene")
    return resolve_page_layout(page.widgets, page.layout, int(scene.canvas["width"]), int(scene.canvas["height"]))


def _widget_to_runtime_commands(widget: WidgetSpec, asset_lookup: dict[str, dict[str, Any]]) -> list[str]:
    x = int(widget.x or 0)
    y = int(widget.y or 0)
    w = int(widget.w or 0)
    h = int(widget.h or 0)
    if w <= 0 or h <= 0:
        return []

    background = int(widget.style.get("background_color", 65535))
    foreground = int(widget.style.get("foreground_color", 0))
    shadow = _rgb_to_rgb565(_shade_rgb(_rgb565_to_rgb(background), -28))
    band = _rgb_to_rgb565(_shade_rgb(_rgb565_to_rgb(background), -20))

    if widget.type == "text":
        text_y = max(y - 2, 0)
        text_h = h + 6
        return [
            _xstr_command(x, text_y, w, text_h, foreground, background, widget.text or "", xcenter=0, ycenter=1),
        ]

    if widget.type == "number":
        value_text = str(widget.value if widget.value is not None else 0)
        return [
            f"fill {x + 4},{y + 6},{w},{h},{shadow}",
            f"fill {x},{y},{w},{h},{background}",
            _xstr_command(x, y, w, h, foreground, background, value_text, xcenter=1, ycenter=1),
        ]

    if widget.type in {"button", "image"}:
        asset_key = widget.resources.get("asset", "")
        accent = _asset_accent_color(asset_lookup.get(asset_key), fallback=foreground or _rgb_to_rgb565((64, 128, 255)))
        icon_label = _asset_label(widget, asset_key)
        commands = [
            f"fill {x + 4},{y + 6},{w},{h},{shadow}",
            f"fill {x},{y},{w},{h},{background}",
        ]

        icon_w = max(min(w // 3, 56), 42)
        icon_h = max(min(h // 3, 36), 28)
        icon_x = x + (w - icon_w) // 2
        icon_y = y + 14
        commands.append(f"fill {icon_x},{icon_y},{icon_w},{icon_h},{accent}")
        commands.append(_xstr_command(icon_x, icon_y, icon_w, icon_h, 65535, accent, icon_label, xcenter=1, ycenter=1))

        if widget.type == "button" and widget.text:
            band_h = min(32, max(24, h // 3))
            band_y = y + h - band_h
            commands.append(f"fill {x},{band_y},{w},{band_h},{band}")
            commands.append(_xstr_command(x, band_y, w, band_h, foreground, band, widget.text, xcenter=1, ycenter=1))
        return commands

    return []


def _encode_runtime_command(command: str) -> bytes:
    return command.encode("gbk", errors="ignore") + TERMINATOR


def _xstr_command(
    x: int,
    y: int,
    w: int,
    h: int,
    foreground: int,
    background: int,
    text: str,
    xcenter: int,
    ycenter: int,
    font_id: int = 0,
    sta: int = 1,
) -> str:
    safe_text = text.replace('"', '\\"')
    return f'xstr {x},{y},{w},{h},{font_id},{foreground},{background},{xcenter},{ycenter},{sta},"{safe_text}"'


def _asset_label(widget: WidgetSpec, asset_key: str) -> str:
    if asset_key:
        return asset_key[:2].upper()
    if widget.text:
        return widget.text[:2].upper()
    return widget.id[:2].upper()


def _asset_accent_color(asset_info: dict[str, Any] | None, fallback: int) -> int:
    if not asset_info:
        return fallback

    variant = asset_info.get("variants", {}).get("normal") or asset_info
    source = variant.get("normalized_png") or variant.get("source")
    if not source:
        return fallback
    image_path = Path(source)
    if not image_path.exists():
        return fallback

    image = Image.open(image_path).convert("RGBA")
    red = green = blue = alpha_total = 0
    pixel_count = 0
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            red += r
            green += g
            blue += b
            alpha_total += a
            pixel_count += 1
    if pixel_count == 0:
        return fallback

    avg = (
        min(red // pixel_count + 16, 255),
        min(green // pixel_count + 16, 255),
        min(blue // pixel_count + 16, 255),
    )
    return _rgb_to_rgb565(avg)


def _build_asset_lookup(scene: SceneModel) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for key, asset in scene.assets.items():
        variants: dict[str, dict[str, Any]] = {}
        for variant_name, source in (
            ("normal", asset.normal or asset.source),
            ("pressed", asset.pressed),
            ("disabled", asset.disabled),
        ):
            if source:
                variants[variant_name] = {"source": source}
        lookup[key] = {"id": asset.id, "variants": variants}
    return lookup


def _shade_rgb(rgb: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
    return tuple(max(min(channel + delta, 255), 0) for channel in rgb)


def _rgb565_to_rgb(value: int) -> tuple[int, int, int]:
    red = ((value >> 11) & 0x1F) * 255 // 31
    green = ((value >> 5) & 0x3F) * 255 // 63
    blue = (value & 0x1F) * 255 // 31
    return red, green, blue


def _rgb_to_rgb565(rgb: tuple[int, int, int]) -> int:
    red, green, blue = rgb
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
