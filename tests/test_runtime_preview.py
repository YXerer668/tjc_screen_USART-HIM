from __future__ import annotations

from pathlib import Path
import unittest

from usarthmi.runtime_preview import build_scene_runtime_commands
from usarthmi.scene import load_scene


class RuntimePreviewTests(unittest.TestCase):
    def test_runtime_preview_commands_cover_scene_widgets(self) -> None:
        base = Path(__file__).resolve().parents[1] / "examples" / "menu_demo"
        scene = load_scene(base / "scene.json")
        commands = build_scene_runtime_commands(scene)
        self.assertGreater(len(commands), 10)
        self.assertEqual(commands[0], "page 0")
        self.assertEqual(commands[-1], "ref_star")
        self.assertIn("page0.bco=65535", commands)
        self.assertTrue(any("USART HMI MENU" in command for command in commands))
        self.assertTrue(any("SETTINGS" in command for command in commands))


if __name__ == "__main__":
    unittest.main()
