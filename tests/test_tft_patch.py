from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from usarthmi.tft_checksum import inspect_tft_checksum
from usarthmi.tft_patch import patch_added_object_tft, patch_basic_tft


CASE_ROOT = Path(r"C:\Users\SinYu\Desktop\case_for_codex")
EXTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "reverse_usarthmi"
    / "case_compare"
)


@unittest.skipUnless(CASE_ROOT.exists() and EXTRACT_ROOT.exists(), "local TJC case fixtures are not available")
class TftPatchTests(unittest.TestCase):
    def test_basic_patch_reproduces_known_cases_exactly(self) -> None:
        baseline_tft = CASE_ROOT / "case_00_baseline" / "lcd_test.tft"
        baseline_pa = EXTRACT_ROOT / "case_00_baseline" / "extract" / "0.pa"
        for case_name in (
            "case_01_t0_text_hello",
            "case_02_t0_x_plus10",
            "case_03_b0_text_test",
        ):
            with self.subTest(case=case_name), tempfile.TemporaryDirectory() as temp_dir:
                out = Path(temp_dir) / f"{case_name}.tft"
                patch_basic_tft(
                    baseline_tft,
                    baseline_pa=baseline_pa,
                    target_pa=EXTRACT_ROOT / case_name / "extract" / "0.pa",
                    out_tft=out,
                )
                generated = out.read_bytes()
                official = (CASE_ROOT / case_name / "lcd_test.tft").read_bytes()
                self.assertEqual(generated, official)

    def test_added_object_patch_reproduces_known_cases_exactly(self) -> None:
        baseline_tft = CASE_ROOT / "case_00_baseline" / "lcd_test.tft"
        baseline_pa = EXTRACT_ROOT / "case_00_baseline" / "extract" / "0.pa"
        for case_name in (
            "case_04_add_text",
            "case_05_add_button",
            "case_06_add_picture",
        ):
            with self.subTest(case=case_name), tempfile.TemporaryDirectory() as temp_dir:
                out = Path(temp_dir) / f"{case_name}.tft"
                patch_added_object_tft(
                    baseline_tft,
                    baseline_pa=baseline_pa,
                    target_pa=EXTRACT_ROOT / case_name / "extract" / "0.pa",
                    out_tft=out,
                )
                generated = out.read_bytes()
                official = (CASE_ROOT / case_name / "lcd_test.tft").read_bytes()
                self.assertEqual(generated, official)

    def test_checksum_matches_official_cases(self) -> None:
        for case_name in (
            "case_00_baseline",
            "case_01_t0_text_hello",
            "case_02_t0_x_plus10",
            "case_03_b0_text_test",
            "case_04_add_text",
            "case_05_add_button",
            "case_06_add_picture",
        ):
            with self.subTest(case=case_name):
                info = inspect_tft_checksum(CASE_ROOT / case_name / "lcd_test.tft")
                self.assertTrue(info["valid"])


if __name__ == "__main__":
    unittest.main()
