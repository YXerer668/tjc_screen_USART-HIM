from __future__ import annotations

from dataclasses import replace
from hashlib import sha1
import json
from pathlib import Path
from typing import Any

from PIL import Image

from .hmi_inspect import inspect_hmi
from .layout import resolve_page_layout
from .page_format import find_block_by_objname, load_page_file, parse_page_data
from .preview import render_scene_preview
from .scene import SceneModel, save_scene_json, widget_to_dict


class EditorError(RuntimeError):
    """Raised when scene build or page patching fails."""


def import_asset(source: str | Path, out_dir: str | Path) -> dict[str, Any]:
    src = Path(source).resolve()
    out_base = Path(out_dir).resolve()
    out_base.mkdir(parents=True, exist_ok=True)

    image = Image.open(src).convert("RGBA")
    digest = sha1(src.read_bytes()).hexdigest()[:12]
    png_path = out_base / f"{src.stem}_{digest}.png"
    raw_path = out_base / f"{src.stem}_{digest}.rgb565"
    image.save(png_path)
    raw_path.write_bytes(_image_to_rgb565(image))
    return {
        "source": str(src),
        "normalized_png": str(png_path),
        "rgb565": str(raw_path),
        "width": image.width,
        "height": image.height,
        "digest": digest,
        "resource_id": int(digest[:4], 16) & 0xFFFF,
    }


def build_scene(scene: SceneModel, seed_hmi: str | Path, out_dir: str | Path) -> dict[str, Any]:
    seed_path = Path(seed_hmi).resolve()
    build_dir = Path(out_dir).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = build_dir / "assets"
    asset_dir.mkdir(exist_ok=True)

    normalized_pages = []
    for page in scene.pages:
        normalized_widgets = resolve_page_layout(
            page.widgets,
            page.layout,
            int(scene.canvas["width"]),
            int(scene.canvas["height"]),
        )
        normalized_pages.append(replace(page, widgets=normalized_widgets))

    normalized_scene = SceneModel(
        project=scene.project,
        canvas=scene.canvas,
        assets=scene.assets,
        pages=normalized_pages,
    )

    manifest_assets: dict[str, Any] = {}
    for asset_key, asset in scene.assets.items():
        manifest_assets[asset_key] = _import_scene_asset(asset, asset_dir)

    output_hmi = build_dir / "output.hmi"
    build_hmi(normalized_scene, manifest_assets, seed_path, output_hmi)
    preview_png = render_scene_preview(normalized_scene, build_dir / "preview.png", manifest_assets=manifest_assets)

    normalized_path = build_dir / "scene.normalized.json"
    save_scene_json(normalized_scene, normalized_path)

    manifest = {
        "seed_hmi": str(seed_path),
        "output_hmi": str(output_hmi),
        "output_tft": None,
        "preview_png": str(preview_png),
        "assets": manifest_assets,
        "pages": [
            {
                "id": page.id,
                "widgets": [widget_to_dict(widget) for widget in page.widgets],
            }
            for page in normalized_pages
        ],
        "warnings": [
            "Image assets are normalized and assigned resource ids, but true HMI/TFT image resource packing is still experimental.",
            "output_tft is not emitted yet; output_hmi is the primary artifact of this build.",
        ],
    }
    manifest_path = build_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_hmi(scene: SceneModel, manifest_assets: dict[str, Any], seed_hmi: Path, output_hmi: Path) -> None:
    inspection = inspect_hmi(seed_hmi)
    seed_bytes = seed_hmi.read_bytes()
    seed_entries = inspection.entries
    page_entry = next(entry for entry in seed_entries if entry.name == "0.pa")
    page_data = seed_bytes[page_entry.data_offset : page_entry.data_offset + page_entry.length]
    page = parse_page_data(page_data)

    seed_page_block = next(block.clone() for block in page.blocks if block.type_code == "y")
    unknown_blocks = [block.clone() for block in page.blocks if block.type_code not in {"y"}]

    template_page_button = load_page_file(r"C:\Program Files (x86)\USART HMI\keyboardch\800480\1.page")
    template_page_text = load_page_file(r"C:\Program Files (x86)\USART HMI\keyboardch\800480\2.page")
    button_proto = find_block_by_objname(template_page_button, "b0").clone()
    number_proto = find_block_by_objname(template_page_button, "loadpageid").clone()
    text_proto = find_block_by_objname(template_page_text, "t0").clone()

    # Update page styling from scene canvas.
    if "background_color" in scene.canvas:
        seed_page_block.set_int("bco", int(scene.canvas["background_color"]), width=2)

    next_id = 100
    generated_blocks = []
    page0 = next(page for page in scene.pages if page.id == "page0")
    for widget in page0.widgets:
        if widget.type == "button":
            block = button_proto.clone()
            _apply_common_widget_fields(block, widget, next_id)
            _apply_textual_fields(block, widget)
            _apply_color_fields(block, widget)
            _apply_asset_fields(block, widget, manifest_assets)
        elif widget.type == "image":
            block = button_proto.clone()
            _apply_common_widget_fields(block, widget, next_id)
            block.set_int("disup", 1, width=1)
            block.set_string("txt", "", encoding="gbk")
            _apply_asset_fields(block, widget, manifest_assets)
        elif widget.type == "number":
            block = number_proto.clone()
            _apply_common_widget_fields(block, widget, next_id)
            block.set_int("val", int(widget.value or 0), width=4)
            _apply_color_fields(block, widget)
        elif widget.type == "text":
            block = text_proto.clone()
            _apply_common_widget_fields(block, widget, next_id)
            _apply_textual_fields(block, widget)
            _apply_color_fields(block, widget)
        else:
            continue

        _clear_existing_events(block)
        generated_blocks.append(block)
        next_id += 1

    page.blocks = [seed_page_block] + unknown_blocks + generated_blocks
    rebuilt_page = page.serialize()
    rebuilt_hmi = _replace_hmi_entry(seed_bytes, seed_entries, "0.pa", rebuilt_page)
    output_hmi.write_bytes(rebuilt_hmi)


def _apply_common_widget_fields(block, widget, next_id: int) -> None:
    block.set_string("objname", widget.id, encoding="ascii")
    block.set_int("id", next_id, width=1)
    block.set_int("x", int(widget.x or 0), width=2)
    block.set_int("y", int(widget.y or 0), width=2)
    block.set_int("w", int(widget.w or 0), width=2)
    block.set_int("h", int(widget.h or 0), width=2)
    block.set_int("endx", int(widget.x or 0) + int(widget.w or 0) - 1, width=2)
    block.set_int("endy", int(widget.y or 0) + int(widget.h or 0) - 1, width=2)


def _apply_textual_fields(block, widget) -> None:
    if widget.text is not None:
        block.set_string("txt", widget.text, encoding="gbk")
        block.set_int("txt_maxl", max(len(widget.text), 1), width=2)
    font_id = widget.style.get("font_id")
    if font_id is not None:
        block.set_int("font", int(font_id), width=1)


def _apply_color_fields(block, widget) -> None:
    if "background_color" in widget.style and block.get_field("bco"):
        block.set_int("bco", int(widget.style["background_color"]), width=2)
    if "foreground_color" in widget.style and block.get_field("pco"):
        block.set_int("pco", int(widget.style["foreground_color"]), width=2)
    if "border_color" in widget.style and block.get_field("borderc"):
        block.set_int("borderc", int(widget.style["border_color"]), width=2)
    if "style" in widget.style and block.get_field("style"):
        block.set_int("style", int(widget.style["style"]), width=1)


def _apply_asset_fields(block, widget, manifest_assets: dict[str, Any]) -> None:
    asset_ref = widget.resources.get("asset")
    if not asset_ref:
        return
    asset_info = manifest_assets.get(asset_ref)
    if not asset_info:
        raise EditorError(f"Asset '{asset_ref}' not imported")
    normal_id = int(_variant_resource_id(asset_info, "normal"))
    pressed_id = int(_variant_resource_id(asset_info, "pressed", fallback="normal"))
    disabled_id = _variant_resource_id(asset_info, "disabled")
    if block.get_field("pic"):
        block.set_int("pic", normal_id, width=2)
    if block.get_field("picc"):
        block.set_int("picc", pressed_id, width=2)
    if disabled_id is not None:
        if block.get_field("pic2"):
            block.set_int("pic2", int(disabled_id), width=2)
        if block.get_field("picc2"):
            block.set_int("picc2", int(disabled_id), width=2)


def _replace_hmi_entry(seed_bytes: bytes, entries, target_name: str, replacement: bytes) -> bytes:
    target = next((entry for entry in entries if entry.name == target_name), None)
    if target is None:
        raise EditorError(f"Entry '{target_name}' not found in seed HMI")

    result = bytearray(seed_bytes)
    target_end = target.data_offset + target.length
    last_end = max(entry.data_offset + entry.length for entry in entries)
    if target_end == last_end:
        result[target.data_offset:target_end] = replacement
        new_offset = target.data_offset
    else:
        new_offset = len(result)
        result.extend(replacement)

    base = target.dir_offset
    result[base + 16 : base + 20] = int(new_offset).to_bytes(4, "little")
    result[base + 20 : base + 24] = len(replacement).to_bytes(4, "little")
    return bytes(result)


def _image_to_rgb565(image: Image.Image) -> bytes:
    output = bytearray()
    for red, green, blue, alpha in image.getdata():
        if alpha == 0:
            red = green = blue = 0
        value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        output.extend(value.to_bytes(2, "little"))
    return bytes(output)


def _clear_existing_events(block) -> None:
    prefixes = []
    for token in block.event_tokens:
        if token.startswith("codes"):
            prefix = token.rsplit("-", 1)[0] + "-"
            if prefix not in prefixes:
                prefixes.append(prefix)
    for prefix in prefixes:
        block.set_event(prefix, [])


def _import_scene_asset(asset, out_dir: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "id": asset.id,
        "source": asset.source,
        "variants": {},
    }

    if asset.normal or asset.pressed or asset.disabled:
        if asset.normal:
            manifest["variants"]["normal"] = import_asset(asset.normal, out_dir)
        if asset.pressed:
            manifest["variants"]["pressed"] = import_asset(asset.pressed, out_dir)
        if asset.disabled:
            manifest["variants"]["disabled"] = import_asset(asset.disabled, out_dir)
        if "normal" not in manifest["variants"] and asset.source:
            manifest["variants"]["normal"] = import_asset(asset.source, out_dir)
    else:
        manifest["variants"]["normal"] = import_asset(asset.source, out_dir)

    primary = manifest["variants"]["normal"]
    manifest.update(
        {
            "normalized_png": primary["normalized_png"],
            "rgb565": primary["rgb565"],
            "width": primary["width"],
            "height": primary["height"],
            "digest": primary["digest"],
            "resource_id": primary["resource_id"],
        }
    )
    return manifest


def _variant_resource_id(asset_info: dict[str, Any], variant: str, fallback: str | None = None) -> int | None:
    variants = asset_info.get("variants", {})
    if variant in variants:
        return int(variants[variant]["resource_id"])
    if fallback and fallback in variants:
        return int(variants[fallback]["resource_id"])
    if variant == "normal" and "resource_id" in asset_info:
        return int(asset_info["resource_id"])
    return None
