from __future__ import annotations

from pathlib import Path
from typing import Any


class TftFontPackError(RuntimeError):
    """Raised when a .zi file or TFT font run cannot be parsed or packed."""


ZI_HEADER_SIZE = 0x2C
ZI_MAGIC = b"\x04\xff\x00\x0a"


def pack_tft_font_run(font_paths: list[str | Path], out_path: str | Path | None = None) -> dict[str, Any]:
    if not font_paths:
        raise TftFontPackError("No .zi font files were provided")

    fonts = [parse_zi_file(path) for path in font_paths]
    table_size = len(fonts) * ZI_HEADER_SIZE
    cursor = table_size
    headers = bytearray()
    payloads = bytearray()
    entries: list[dict[str, Any]] = []

    for font in fonts:
        header = bytearray(font["header"])
        header[0x18:0x1C] = int(cursor).to_bytes(4, "little")
        headers.extend(header)
        payloads.extend(font["payload"])
        entries.append(
            {
                "source": font["path"],
                "font_name": font["font_name"],
                "encoding_name": font["encoding_name"],
                "char_height": font["char_height"],
                "char_count": font["char_count"],
                "data_start": cursor,
                "data_start_hex": f"0x{cursor:X}",
                "payload_size": len(font["payload"]),
            }
        )
        cursor += len(font["payload"])

    packed = bytes(headers + payloads)
    result = {
        "font_count": len(fonts),
        "table_size": table_size,
        "table_size_hex": f"0x{table_size:X}",
        "packed_size": len(packed),
        "packed_size_hex": f"0x{len(packed):X}",
        "entries": entries,
    }

    if out_path is not None:
        target = Path(out_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(packed)
        result["output"] = str(target)

    return result


def inspect_tft_font_run(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path).resolve()
    raw = path.read_bytes()
    return inspect_tft_font_run_bytes(raw, source_path=str(path))


def inspect_tft_font_run_bytes(raw: bytes, source_path: str = "") -> dict[str, Any]:
    offsets = _scan_header_offsets(raw)
    if not offsets:
        raise TftFontPackError("No TFT-style font headers found")

    entries: list[dict[str, Any]] = []
    for index, offset in enumerate(offsets):
        entry = _parse_font_entry(raw, offsets, index, offset)
        entries.append(entry)

    return {
        "source_path": source_path,
        "font_count": len(entries),
        "entries": entries,
    }


def parse_zi_file(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path).resolve()
    raw = path.read_bytes()
    if len(raw) < ZI_HEADER_SIZE or not raw.startswith(ZI_MAGIC):
        raise TftFontPackError(f"File is not a recognized .zi v5/v6 font: {path}")

    header = raw[:ZI_HEADER_SIZE]
    payload = raw[ZI_HEADER_SIZE:]
    descriptor_len = header[0x11]
    file_name_len = header[0x20]
    name_bytes = payload[:descriptor_len]
    font_name = name_bytes[:file_name_len].decode("ascii", errors="replace")
    encoding_name = name_bytes[file_name_len:descriptor_len].decode("ascii", errors="replace")

    return {
        "path": str(path),
        "header": bytes(header),
        "payload": bytes(payload),
        "font_name": font_name,
        "encoding_name": encoding_name,
        "char_height": header[0x07],
        "char_width": header[0x06],
        "char_count": int.from_bytes(header[0x0C:0x10], "little"),
        "version": header[0x10],
    }


def _scan_header_offsets(raw: bytes) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    first_data_start: int | None = None
    while cursor + ZI_HEADER_SIZE <= len(raw):
        chunk = raw[cursor : cursor + ZI_HEADER_SIZE]
        if not chunk.startswith(ZI_MAGIC):
            break
        data_start = int.from_bytes(chunk[0x18:0x1C], "little")
        if data_start < ZI_HEADER_SIZE:
            break
        offsets.append(cursor)
        if first_data_start is None:
            first_data_start = data_start
        cursor += ZI_HEADER_SIZE
        if first_data_start is not None and cursor >= first_data_start:
            break
    return offsets


def _parse_font_entry(raw: bytes, offsets: list[int], index: int, offset: int) -> dict[str, Any]:
    header = raw[offset : offset + ZI_HEADER_SIZE]
    descriptor_len = header[0x11]
    file_name_len = header[0x20]
    data_start = int.from_bytes(header[0x18:0x1C], "little")
    payload_start = data_start
    if index + 1 < len(offsets):
        payload_end = int.from_bytes(raw[offsets[index + 1] + 0x18 : offsets[index + 1] + 0x1C], "little")
    else:
        payload_end = len(raw)
    payload = raw[payload_start:payload_end]
    name_bytes = payload[:descriptor_len]

    return {
        "offset": offset,
        "offset_hex": f"0x{offset:X}",
        "data_start": data_start,
        "data_start_hex": f"0x{data_start:X}",
        "payload_size": len(payload),
        "codepage": header[0x04],
        "char_width": header[0x06],
        "char_height": header[0x07],
        "char_count": int.from_bytes(header[0x0C:0x10], "little"),
        "version": header[0x10],
        "font_name": name_bytes[:file_name_len].decode("ascii", errors="replace"),
        "encoding_name": name_bytes[file_name_len:descriptor_len].decode("ascii", errors="replace"),
    }
