from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from usarthmi.hmi_inspect import extract_hmi, inspect_hmi


def make_sample_hmi() -> bytes:
    resources = [
        ("Program.s", b"baud=9600\r\npage 0\r\n"),
        (
            "0.pa",
            b"\x00page0\x00objname\x00x0\x00bco\x00pco\x00font\x00pic\x00val\x00",
        ),
    ]

    header = bytearray((len(resources)).to_bytes(4, "little"))
    data = bytearray()
    current_offset = 4 + (28 * len(resources))

    for index, (name, payload) in enumerate(resources):
        name_bytes = name.encode("ascii").ljust(16, b"\x00")
        header.extend(name_bytes)
        header.extend(current_offset.to_bytes(4, "little"))
        header.extend(len(payload).to_bytes(4, "little"))
        header.extend((index + 1).to_bytes(4, "little"))
        data.extend(payload)
        current_offset += len(payload)

    return bytes(header + data)


class HMIInspectTests(unittest.TestCase):
    def test_inspect_and_extract_sample_hmi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            hmi_path = tmp_path / "sample.HMI"
            hmi_path.write_bytes(make_sample_hmi())

            inspection = inspect_hmi(hmi_path)
            self.assertEqual(inspection.entry_count, 2)
            self.assertEqual([entry.name for entry in inspection.entries], ["Program.s", "0.pa"])
            self.assertIn("baud=9600", inspection.program_text or "")
            self.assertEqual(inspection.page_names, ["page0"])
            self.assertEqual(inspection.object_names, ["x0"])
            self.assertTrue({"bco", "pco", "font", "pic", "val"}.issubset(inspection.property_names))

            output_dir = tmp_path / "extract"
            written = extract_hmi(hmi_path, output_dir)
            names = {path.name for path in written}
            self.assertIn("Program.s", names)
            self.assertIn("Program_utf8.txt", names)
            self.assertIn("0.pa", names)


if __name__ == "__main__":
    unittest.main()
