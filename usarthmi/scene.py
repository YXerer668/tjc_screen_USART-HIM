from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import yaml


class SceneError(ValueError):
    """Raised when a scene file is invalid."""


@dataclass(slots=True)
class AssetSpec:
    id: str
    source: str | None = None
    normal: str | None = None
    pressed: str | None = None
    disabled: str | None = None


@dataclass(slots=True)
class WidgetSpec:
    id: str
    type: str
    text: str | None = None
    value: int | None = None
    x: int | None = None
    y: int | None = None
    w: int | None = None
    h: int | None = None
    style: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    bindings: dict[str, Any] = field(default_factory=dict)
    children: list["WidgetSpec"] = field(default_factory=list)
    layout: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PageSpec:
    id: str
    layout: dict[str, Any]
    widgets: list[WidgetSpec]


@dataclass(slots=True)
class SceneModel:
    project: dict[str, Any]
    canvas: dict[str, Any]
    assets: dict[str, AssetSpec]
    pages: list[PageSpec]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "canvas": self.canvas,
            "assets": {
                key: {
                    "id": asset.id,
                    "source": asset.source,
                    "normal": asset.normal,
                    "pressed": asset.pressed,
                    "disabled": asset.disabled,
                }
                for key, asset in self.assets.items()
            },
            "pages": [page_to_dict(page) for page in self.pages],
        }


def page_to_dict(page: PageSpec) -> dict[str, Any]:
    return {
        "id": page.id,
        "layout": page.layout,
        "widgets": [widget_to_dict(widget) for widget in page.widgets],
    }


def widget_to_dict(widget: WidgetSpec) -> dict[str, Any]:
    return {
        "id": widget.id,
        "type": widget.type,
        "text": widget.text,
        "value": widget.value,
        "x": widget.x,
        "y": widget.y,
        "w": widget.w,
        "h": widget.h,
        "style": widget.style,
        "resources": widget.resources,
        "bindings": widget.bindings,
        "layout": widget.layout,
        "children": [widget_to_dict(child) for child in widget.children],
    }


def load_scene(path: str | Path) -> SceneModel:
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    suffix = file_path.suffix.lower()
    raw_text = file_path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        payload = yaml.safe_load(raw_text)
    else:
        payload = json.loads(raw_text)

    scene = validate_scene(payload)
    scene.project.setdefault("_source_dir", str(file_path.parent))
    for asset in scene.assets.values():
        for attr_name in ("source", "normal", "pressed", "disabled"):
            value = getattr(asset, attr_name)
            if not value:
                continue
            asset_path = Path(value)
            if not asset_path.is_absolute():
                setattr(asset, attr_name, str((file_path.parent / asset_path).resolve()))
    return scene


def save_scene_json(scene: SceneModel, path: str | Path) -> Path:
    file_path = Path(path).resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(scene.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return file_path


def validate_scene(payload: dict[str, Any]) -> SceneModel:
    if not isinstance(payload, dict):
        raise SceneError("Scene root must be an object")

    project = payload.get("project")
    canvas = payload.get("canvas")
    pages = payload.get("pages")
    assets = payload.get("assets", {})

    if not isinstance(project, dict):
        raise SceneError("project must be an object")
    if not isinstance(canvas, dict):
        raise SceneError("canvas must be an object")
    if not isinstance(pages, list) or not pages:
        raise SceneError("pages must be a non-empty list")
    if not isinstance(assets, dict):
        raise SceneError("assets must be an object map")

    width = int(canvas.get("width", 0))
    height = int(canvas.get("height", 0))
    if width <= 0 or height <= 0:
        raise SceneError("canvas.width and canvas.height must be positive integers")

    asset_specs: dict[str, AssetSpec] = {}
    for key, asset in assets.items():
        if not isinstance(asset, dict):
            raise SceneError(f"asset '{key}' must be an object")
        source = asset.get("source")
        normal = asset.get("normal")
        pressed = asset.get("pressed")
        disabled = asset.get("disabled")
        if source is not None and (not isinstance(source, str) or not source):
            raise SceneError(f"asset '{key}' source must be a non-empty string when provided")
        for attr_name, value in (("normal", normal), ("pressed", pressed), ("disabled", disabled)):
            if value is not None and (not isinstance(value, str) or not value):
                raise SceneError(f"asset '{key}' {attr_name} must be a non-empty string when provided")
        if not source and not normal:
            raise SceneError(f"asset '{key}' requires source or normal")
        asset_specs[key] = AssetSpec(
            id=str(asset.get("id") or key),
            source=source,
            normal=normal,
            pressed=pressed,
            disabled=disabled,
        )

    page_specs = [_validate_page(page) for page in pages]

    return SceneModel(
        project=project,
        canvas={**canvas, "width": width, "height": height},
        assets=asset_specs,
        pages=page_specs,
    )


def _validate_page(payload: dict[str, Any]) -> PageSpec:
    if not isinstance(payload, dict):
        raise SceneError("Each page must be an object")
    page_id = payload.get("id")
    if not isinstance(page_id, str) or not page_id:
        raise SceneError("page.id must be a non-empty string")
    layout = payload.get("layout") or {"type": "absolute"}
    widgets = payload.get("widgets", [])
    if not isinstance(layout, dict):
        raise SceneError(f"page '{page_id}' layout must be an object")
    if not isinstance(widgets, list):
        raise SceneError(f"page '{page_id}' widgets must be a list")
    return PageSpec(
        id=page_id,
        layout=layout,
        widgets=[_validate_widget(item) for item in widgets],
    )


def _validate_widget(payload: dict[str, Any]) -> WidgetSpec:
    if not isinstance(payload, dict):
        raise SceneError("widget must be an object")

    widget_id = payload.get("id")
    widget_type = payload.get("type")
    if not isinstance(widget_id, str) or not widget_id:
        raise SceneError("widget.id must be a non-empty string")
    if widget_type not in {"text", "image", "button", "number"}:
        raise SceneError(f"widget '{widget_id}' has unsupported type '{widget_type}'")

    for key in ("x", "y", "w", "h"):
        if key in payload and payload[key] is not None:
            payload[key] = int(payload[key])

    children = payload.get("children", [])
    if not isinstance(children, list):
        raise SceneError(f"widget '{widget_id}' children must be a list")

    style = payload.get("style") or {}
    resources = payload.get("resources") or {}
    bindings = payload.get("bindings") or {}
    layout = payload.get("layout") or {}
    if not isinstance(style, dict):
        raise SceneError(f"widget '{widget_id}' style must be an object")
    if not isinstance(resources, dict):
        raise SceneError(f"widget '{widget_id}' resources must be an object")
    if not isinstance(bindings, dict):
        raise SceneError(f"widget '{widget_id}' bindings must be an object")
    if not isinstance(layout, dict):
        raise SceneError(f"widget '{widget_id}' layout must be an object")

    return WidgetSpec(
        id=widget_id,
        type=widget_type,
        text=payload.get("text"),
        value=int(payload["value"]) if payload.get("value") is not None else None,
        x=payload.get("x"),
        y=payload.get("y"),
        w=payload.get("w"),
        h=payload.get("h"),
        style=style,
        resources=resources,
        bindings=bindings,
        layout=layout,
        children=[_validate_widget(item) for item in children],
    )
