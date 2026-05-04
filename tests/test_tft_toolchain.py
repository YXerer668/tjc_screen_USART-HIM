from __future__ import annotations

from pathlib import Path
import unittest

from usarthmi.tft_toolchain import inspect_tft, list_supported_tft_models


class TftToolchainTests(unittest.TestCase):
    def test_list_models_contains_target_family(self) -> None:
        models = list_supported_tft_models()
        self.assertIn("TJC8048X543_011", models)

    def test_inspect_sample_tft(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "github_refs"
            / "Gaggiuino_35"
            / "Nextion_43"
            / "Nextion_43_18MAY2024_0_Deg.tft"
        )
        if not sample.exists():
            self.skipTest("optional third-party sample TFT is not present")
        info = inspect_tft(sample)
        self.assertEqual(info["model"], "NX4827P043_011")
        self.assertIn("Header1", info["parsed"])
        self.assertTrue(info["embedded_font_runs"])
        first_font = info["embedded_font_runs"][0]["entries"][0]
        self.assertEqual(first_font["font_name"], "Roboto B 12")
        self.assertEqual(first_font["encoding_name"], "iso-8859-1")


if __name__ == "__main__":
    unittest.main()
