from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .scene import WidgetSpec


class LayoutError(ValueError):
    """Raised when a widget tree cannot be laid out."""


def resolve_page_layout(widgets: list[WidgetSpec], layout: dict, width: int, height: int) -> list[WidgetSpec]:
    placed = [replace(widget) for widget in widgets]
    _resolve_children(placed, layout or {"type": "absolute"}, 0, 0, width, height)
    return placed


def _resolve_children(widgets: list[WidgetSpec], layout: dict, x: int, y: int, width: int, height: int) -> None:
    mode = (layout.get("type") or "absolute").lower()
    padding = int(layout.get("padding", 0))
    gap = int(layout.get("gap", 0))
    inner_x = x + padding
    inner_y = y + padding
    inner_w = max(width - 2 * padding, 0)
    inner_h = max(height - 2 * padding, 0)

    if mode == "absolute":
        for widget in widgets:
            _resolve_absolute_widget(widget, inner_x, inner_y, inner_w, inner_h)
        return

    if mode == "row":
        _resolve_row(widgets, inner_x, inner_y, inner_w, inner_h, gap)
        return

    if mode == "column":
        _resolve_column(widgets, inner_x, inner_y, inner_w, inner_h, gap)
        return

    if mode == "grid":
        _resolve_grid(widgets, inner_x, inner_y, inner_w, inner_h, gap, layout)
        return

    if mode == "stack":
        for widget in widgets:
            widget.x = inner_x
            widget.y = inner_y
            widget.w = widget.w if widget.w is not None else inner_w
            widget.h = widget.h if widget.h is not None else inner_h
            _resolve_nested(widget)
        return

    if mode == "anchor":
        for widget in widgets:
            _resolve_anchor(widget, inner_x, inner_y, inner_w, inner_h)
        return

    raise LayoutError(f"Unsupported layout type: {mode}")


def _resolve_absolute_widget(widget: WidgetSpec, x: int, y: int, width: int, height: int) -> None:
    if widget.layout.get("type") == "anchor":
        _resolve_anchor(widget, x, y, width, height)
    else:
        widget.x = x + int(widget.x or 0)
        widget.y = y + int(widget.y or 0)
        if widget.w is None or widget.h is None:
            raise LayoutError(f"Widget '{widget.id}' requires w/h in absolute layout")
    _resolve_nested(widget)


def _resolve_row(widgets: list[WidgetSpec], x: int, y: int, width: int, height: int, gap: int) -> None:
    widths = _split_dimension(widgets, width, gap, primary="w")
    cursor = x
    for widget, resolved_w in zip(widgets, widths, strict=False):
        widget.x = cursor
        widget.y = y
        widget.w = resolved_w
        widget.h = widget.h if widget.h is not None else height
        cursor += resolved_w + gap
        _resolve_nested(widget)


def _resolve_column(widgets: list[WidgetSpec], x: int, y: int, width: int, height: int, gap: int) -> None:
    heights = _split_dimension(widgets, height, gap, primary="h")
    cursor = y
    for widget, resolved_h in zip(widgets, heights, strict=False):
        widget.x = x
        widget.y = cursor
        widget.w = widget.w if widget.w is not None else width
        widget.h = resolved_h
        cursor += resolved_h + gap
        _resolve_nested(widget)


def _resolve_grid(
    widgets: list[WidgetSpec],
    x: int,
    y: int,
    width: int,
    height: int,
    gap: int,
    layout: dict,
) -> None:
    columns = int(layout.get("columns", 1))
    if columns <= 0:
        raise LayoutError("grid layout requires columns > 0")
    rows = max((len(widgets) + columns - 1) // columns, 1)
    cell_w = (width - gap * (columns - 1)) // columns
    cell_h = (height - gap * (rows - 1)) // rows
    for index, widget in enumerate(widgets):
        row = index // columns
        col = index % columns
        widget.x = x + col * (cell_w + gap)
        widget.y = y + row * (cell_h + gap)
        widget.w = widget.w if widget.w is not None else cell_w
        widget.h = widget.h if widget.h is not None else cell_h
        _resolve_nested(widget)


def _resolve_anchor(widget: WidgetSpec, x: int, y: int, width: int, height: int) -> None:
    anchors = widget.layout
    resolved_w = widget.w or int(anchors.get("w", 0))
    resolved_h = widget.h or int(anchors.get("h", 0))
    if resolved_w <= 0 or resolved_h <= 0:
        raise LayoutError(f"Widget '{widget.id}' anchor layout requires w/h")

    left = anchors.get("left")
    right = anchors.get("right")
    top = anchors.get("top")
    bottom = anchors.get("bottom")
    center_x = anchors.get("center_x")
    center_y = anchors.get("center_y")

    if left is not None:
        widget.x = x + int(left)
    elif right is not None:
        widget.x = x + width - resolved_w - int(right)
    elif center_x is not None:
        widget.x = x + (width - resolved_w) // 2 + int(center_x)
    else:
        widget.x = x

    if top is not None:
        widget.y = y + int(top)
    elif bottom is not None:
        widget.y = y + height - resolved_h - int(bottom)
    elif center_y is not None:
        widget.y = y + (height - resolved_h) // 2 + int(center_y)
    else:
        widget.y = y

    widget.w = resolved_w
    widget.h = resolved_h
    _resolve_nested(widget)


def _resolve_nested(widget: WidgetSpec) -> None:
    if not widget.children:
        return
    _resolve_children(widget.children, widget.layout or {"type": "absolute"}, widget.x or 0, widget.y or 0, widget.w or 0, widget.h or 0)


def _split_dimension(widgets: Iterable[WidgetSpec], total: int, gap: int, primary: str) -> list[int]:
    widget_list = list(widgets)
    if not widget_list:
        return []
    fixed = []
    flex_widgets = []
    for widget in widget_list:
        size = getattr(widget, primary)
        if size is None:
            flex_widgets.append(widget)
        else:
            fixed.append(int(size))
    remaining = total - sum(fixed) - gap * (len(widget_list) - 1)
    if remaining < 0:
        remaining = 0
    share = remaining // max(len(flex_widgets), 1) if flex_widgets else 0
    sizes = []
    for widget in widget_list:
        size = getattr(widget, primary)
        sizes.append(int(size) if size is not None else share)
    return sizes

