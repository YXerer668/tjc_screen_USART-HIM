from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from usarthmi.tft_font_pack import inspect_tft_font_run, pack_tft_font_run


class TftFontPackTests(unittest.TestCase):
    def test_pack_and_inspect_generated_fonts(self) -> None:
        base = Path(__file__).resolve().parents[1]
        fonts = [
            base / "build_font_demo.zi",
            base / "build_font_scene.zi",
        ]
        if not all(path.exists() for path in fonts):
            self.skipTest("optional generated .zi font fixtures are not present")
        with tempfile.TemporaryDirectory() as temp_dir:
            packed = Path(temp_dir) / "fonts_run.bin"
            result = pack_tft_font_run([str(path) for path in fonts], out_path=packed)
            self.assertEqual(result["font_count"], 2)
            self.assertTrue(packed.exists())

            inspected = inspect_tft_font_run(packed)
            self.assertEqual(inspected["font_count"], 2)
            self.assertEqual(inspected["entries"][0]["font_name"], "SimSun32subset")
            self.assertEqual(inspected["entries"][1]["font_name"], "SimSun32scene")


if __name__ == "__main__":
    unittest.main()
