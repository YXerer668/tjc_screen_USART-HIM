from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from usarthmi.layout import resolve_page_layout
from usarthmi.preview import render_scene_preview
from usarthmi.scene import WidgetSpec, load_scene
from PIL import Image


class SceneLayoutTests(unittest.TestCase):
    def test_json_and_yaml_scene_match(self) -> None:
        base = Path(__file__).resolve().parents[1] / "examples" / "menu_demo"
        scene_json = load_scene(base / "scene.json")
        scene_yaml = load_scene(base / "scene.yaml")
        self.assertEqual(scene_json.to_dict(), scene_yaml.to_dict())

    def test_absolute_layout(self) -> None:
        widgets = [WidgetSpec(id="a", type="text", x=10, y=20, w=30, h=40)]
        placed = resolve_page_layout(widgets, {"type": "absolute"}, 800, 480)
        self.assertEqual((placed[0].x, placed[0].y, placed[0].w, placed[0].h), (10, 20, 30, 40))

    def test_row_layout(self) -> None:
        widgets = [
            WidgetSpec(id="a", type="text", h=30),
            WidgetSpec(id="b", type="text", h=30),
        ]
        placed = resolve_page_layout(widgets, {"type": "row", "gap": 10}, 210, 30)
        self.assertEqual((placed[0].x, placed[0].w), (0, 100))
        self.assertEqual((placed[1].x, placed[1].w), (110, 100))

    def test_column_layout(self) -> None:
        widgets = [
            WidgetSpec(id="a", type="text", w=40),
            WidgetSpec(id="b", type="text", w=40),
        ]
        placed = resolve_page_layout(widgets, {"type": "column", "gap": 10}, 40, 210)
        self.assertEqual((placed[0].y, placed[0].h), (0, 100))
        self.assertEqual((placed[1].y, placed[1].h), (110, 100))

    def test_grid_layout(self) -> None:
        widgets = [WidgetSpec(id=f"w{i}", type="button") for i in range(4)]
        placed = resolve_page_layout(widgets, {"type": "grid", "columns": 2, "gap": 10}, 210, 210)
        self.assertEqual((placed[0].x, placed[0].y), (0, 0))
        self.assertEqual((placed[1].x, placed[1].y), (110, 0))
        self.assertEqual((placed[2].x, placed[2].y), (0, 110))

    def test_stack_layout(self) -> None:
        widgets = [WidgetSpec(id="bg", type="image"), WidgetSpec(id="fg", type="text")]
        placed = resolve_page_layout(widgets, {"type": "stack"}, 320, 240)
        for widget in placed:
            self.assertEqual((widget.x, widget.y, widget.w, widget.h), (0, 0, 320, 240))

    def test_anchor_layout(self) -> None:
        widget = WidgetSpec(
            id="br",
            type="button",
            w=40,
            h=20,
            layout={"type": "anchor", "right": 10, "bottom": 5},
        )
        placed = resolve_page_layout([widget], {"type": "anchor"}, 200, 100)
        self.assertEqual((placed[0].x, placed[0].y), (150, 75))

    def test_scene_preview_renders_png(self) -> None:
        base = Path(__file__).resolve().parents[1] / "examples" / "menu_demo"
        scene = load_scene(base / "scene.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "preview.png"
            render_scene_preview(scene, target)
            self.assertTrue(target.exists())
            with Image.open(target) as image:
                self.assertEqual(image.size, (800, 480))


if __name__ == "__main__":
    unittest.main()
