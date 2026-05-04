from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from .tft_toolchain import TftToolchainError, inspect_tft


POLY = 0x04C11DB7 | (1 << 32)
CRC_TABLE = []
for _top in range(256):
    _reg = _top << 24
    for _ in range(8):
        _reg <<= 1
        if _reg >= (1 << 32):
            _reg ^= POLY
    CRC_TABLE.append(_reg & 0xFFFFFFFF)


def calculate_tft_checksum(file_data: bytes, *, series: int | None = None) -> int:
    """Calculate the final 4-byte TFT checksum.

    Series 2/3/100-style TFT files use a word based checksum. Older series use
    byte based input. The final value is XORed with three header bytes, matching
    the algorithm used by TFTTool and verified against local TJC 1.67.6 samples.
    """

    if len(file_data) < 4:
        raise TftToolchainError("TFT data is too short")
    raw = file_data[:-4]
    if series is None:
        series = _guess_series_from_raw(file_data)
    if series in (2, 3):
        if len(raw) % 4 != 0:
            raise TftToolchainError("Word-based TFT checksum requires body length divisible by 4")
        words = list(struct.unpack(f"<{len(raw) // 4}I", raw))
        checksum = _crc32_like(words)
    elif series in (0, 1, 100):
        checksum = _crc32_like(list(raw))
    else:
        raise TftToolchainError(f"Unsupported TFT model series for checksum: {series}")
    checksum ^= raw[0x03] ^ raw[0x2E] ^ raw[0x3C]
    return checksum & 0xFFFFFFFF


def update_tft_checksum(file_data: bytes, *, series: int | None = None) -> bytes:
    checksum = calculate_tft_checksum(file_data, series=series)
    return file_data[:-4] + checksum.to_bytes(4, "little")


def inspect_tft_checksum(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path).resolve()
    data = path.read_bytes()
    series = _series_from_inspection(path)
    stored = int.from_bytes(data[-4:], "little")
    calculated = calculate_tft_checksum(data, series=series)
    return {
        "path": str(path),
        "file_size": len(data),
        "model_series": series,
        "stored": stored,
        "stored_hex": f"0x{stored:08X}",
        "calculated": calculated,
        "calculated_hex": f"0x{calculated:08X}",
        "valid": stored == calculated,
        "algorithm": "word-based Nextion/TJC CRC variant for series 2/3, byte-based for series 0/1/100, final XOR with bytes 0x03/0x2E/0x3C",
    }


def _series_from_inspection(path: Path) -> int:
    info = inspect_tft(path)
    parsed = info.get("parsed")
    if not isinstance(parsed, dict):
        raise TftToolchainError("Unable to inspect TFT model series")
    header1 = parsed.get("Header1")
    if not isinstance(header1, dict):
        raise TftToolchainError("Unable to inspect TFT Header1")
    value = header1.get("model_series")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TftToolchainError("TFT Header1 does not contain model_series")


def _guess_series_from_raw(file_data: bytes) -> int:
    # The locally targeted TJC8048X543 files are X5 / series 3. Callers that
    # need other families should pass the inspected series explicitly.
    if len(file_data) >= 0xC8:
        return 3
    raise TftToolchainError("Unable to infer TFT model series from raw data")


def _crc32_like(values: list[int], salt: int = 0xFFFFFFFF) -> int:
    reg = 0
    stream = list(values) + [0]
    stream[0] ^= salt
    for word in stream:
        word &= 0xFFFFFFFF
        reg = _update_byte(reg, (word >> 24) & 0xFF)
        reg = _update_byte(reg, (word >> 16) & 0xFF)
        reg = _update_byte(reg, (word >> 8) & 0xFF)
        reg = _update_byte(reg, word & 0xFF)
    return reg & 0xFFFFFFFF


def _update_byte(reg: int, value: int) -> int:
    return ((((reg & 0x00FFFFFF) << 8) | value) ^ CRC_TABLE[(reg >> 24) & 0xFF]) & 0xFFFFFFFF
