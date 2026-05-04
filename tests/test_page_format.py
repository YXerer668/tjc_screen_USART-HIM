from __future__ import annotations

from pathlib import Path
import unittest

from usarthmi.hmi_inspect import inspect_hmi
from usarthmi.page_format import (
    find_block_by_objname,
    find_first_block,
    load_page_file,
    parse_page_data,
)


class PageFormatTests(unittest.TestCase):
    def test_keyboard_page_prototypes_are_detected(self) -> None:
        page = load_page_file(r"C:\Program Files (x86)\USART HMI\keyboardch\800480\1.page")
        self.assertEqual(page.page_name, "keybdA")
        page_block = find_first_block(page, "y")
        button_block = find_block_by_objname(page, "b0")
        number_block = find_block_by_objname(page, "loadpageid")
        self.assertEqual(page_block.type_code, "y")
        self.assertEqual(button_block.type_code, "b")
        self.assertEqual(number_block.type_code, "4")
        self.assertEqual(button_block.get_field("txt").value.decode("ascii", errors="ignore"), "q")
        self.assertEqual(button_block.event_tokens[:2], ["codesdown-0", "codesup-6"])

    def test_seed_page_round_trip_is_exact(self) -> None:
        seed = r"D:\MySTM32\H723ZGT6\Program\ISP_Test\lcd_test.HMI"
        raw = Path(seed).read_bytes()
        inspection = inspect_hmi(seed)
        entry = next(item for item in inspection.entries if item.name == "0.pa")
        page_data = raw[entry.data_offset : entry.data_offset + entry.length]
        page = parse_page_data(page_data)
        self.assertEqual(page.serialize(), page_data)


if __name__ == "__main__":
    unittest.main()
