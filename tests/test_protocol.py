from __future__ import annotations

import unittest

from usarthmi.protocol import (
    ProtocolError,
    build_click,
    build_dim,
    build_get,
    build_page,
    build_ref,
    build_set,
    build_tsw,
    build_vis,
    parse_response,
)
from usarthmi.transport import SerialTransport


class ProtocolTests(unittest.TestCase):
    def test_command_encoding_appends_terminator(self) -> None:
        payload = SerialTransport.encode_command("get dim")
        self.assertEqual(payload, b"get dim\xff\xff\xff")

    def test_builders_follow_expected_wire_format(self) -> None:
        self.assertEqual(build_get("page0.bco"), "get page0.bco")
        self.assertEqual(build_set("page0.bco", "65535"), "page0.bco=65535")
        self.assertEqual(build_page("0"), "page 0")
        self.assertEqual(build_ref("0"), "ref 0")
        self.assertEqual(build_vis("x0", "1"), "vis x0,1")
        self.assertEqual(build_tsw("x0", "0"), "tsw x0,0")
        self.assertEqual(build_dim("30"), "dim=30")
        self.assertEqual(build_click("x0", "down"), "click x0,1")
        self.assertEqual(build_click("x0", "up"), "click x0,0")
        with self.assertRaises(ProtocolError):
            build_click("x0", "hold")

    def test_parse_connect_ascii(self) -> None:
        raw = (
            b"comok 2,1089-0,TJC8048X543_011C,277,10501,"
            b"FC8B3401B1A6086E,128974848-0\xff\xff\xff"
        )
        parsed = parse_response(raw)
        self.assertEqual(parsed.kind, "connect")
        self.assertEqual(parsed.details["model"], "TJC8048X543_011C")
        self.assertEqual(parsed.details["firmware"], "277")

    def test_parse_page_id(self) -> None:
        parsed = parse_response(bytes.fromhex("66 00 FF FF FF"))
        self.assertEqual(parsed.kind, "page_id")
        self.assertEqual(parsed.value, 0)

    def test_parse_number(self) -> None:
        parsed = parse_response(bytes.fromhex("71 64 00 00 00 FF FF FF"))
        self.assertEqual(parsed.kind, "number")
        self.assertEqual(parsed.value, 100)

    def test_parse_invalid_reference(self) -> None:
        parsed = parse_response(bytes.fromhex("1A FF FF FF"))
        self.assertEqual(parsed.kind, "invalid_reference")
        self.assertEqual(parsed.code, 0x1A)


if __name__ == "__main__":
    unittest.main()

