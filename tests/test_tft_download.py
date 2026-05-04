from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from usarthmi.transport import TERMINATOR
from usarthmi.tft_download import _write_command, plan_upload


class FakeSerial:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, payload: bytes | str) -> None:
        if isinstance(payload, str):
            payload = payload.encode("ascii")
        self.data.extend(payload)


class TftDownloadTests(unittest.TestCase):
    def test_write_command_adds_optional_address_and_terminator(self) -> None:
        ser = FakeSerial()
        _write_command(ser, "connect", address=0x1234)  # type: ignore[arg-type]
        self.assertEqual(bytes(ser.data), b"\x34\x12connect" + TERMINATOR)

    def test_plan_upload_compares_4096_byte_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "baseline.tft"
            candidate = root / "candidate.tft"
            baseline.write_bytes(b"A" * 4096 + b"B" * 4096 + b"\xFF" * 4096)
            candidate.write_bytes(b"A" * 4096 + b"C" * 4096 + b"\xFF" * 4096)

            plan = plan_upload(candidate, baseline_path=baseline, chunk_size=4096, download_baud=40960)
            data = plan.to_dict()

            self.assertEqual(data["total_chunks"], 3)
            self.assertEqual(data["identical_chunks"], 2)
            self.assertEqual(data["different_chunks"], 1)
            self.assertEqual(data["identical_bytes"], 8192)
            self.assertEqual(data["identical_prefix_bytes"], 4096)
            self.assertEqual(data["all_ff_chunks"], 1)
            self.assertTrue(data["public_whmi_wri_requires_full_stream"])
            self.assertEqual(data["estimated_serial_min_s"], 3.0)


if __name__ == "__main__":
    unittest.main()
