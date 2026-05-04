from __future__ import annotations

from pathlib import Path
import unittest

from usarthmi.font_toolchain import collect_scene_text
from usarthmi.scene import load_scene


class FontToolchainTests(unittest.TestCase):
    def test_collect_scene_text_includes_widget_labels(self) -> None:
        base = Path(__file__).resolve().parents[1] / "examples" / "menu_demo"
        scene = load_scene(base / "scene.json")
        text = collect_scene_text(scene)
        self.assertIn("USART HMI MENU", text)
        self.assertIn("SETTINGS", text)
        self.assertIn("SYSTEM", text)


if __name__ == "__main__":
    unittest.main()
