from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
from typing import Any


class TftToolchainError(RuntimeError):
    """Raised when TFT inspection or helper loading fails."""


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TFTTOOL_DIR = WORKSPACE_ROOT / "external" / "TFTTool"
TFTTOOL_PY = TFTTOOL_DIR / "TFTTool.py"


def inspect_tft(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path).resolve()
    module = _load_tfttool_module()
    raw = path.read_bytes()
    decode_error: str | None = None
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            tft = module.TFTFile(raw, hexVals=True, decode_usercode=True)
        except Exception as exc:
            # Some newer TJC editor versions are not in TFTTool's instruction table yet.
            # Header/section inspection is still useful for upload risk checks.
            decode_error = str(exc)
            tft = module.TFTFile(raw, hexVals=True, decode_usercode=False)
    if decode_error is None:
        readable = tft.getReadable(includeUnknowns=True, includeBins=False)
        try:
            parsed = ast.literal_eval(readable)
        except (ValueError, SyntaxError) as exc:
            raise TftToolchainError("Unable to parse TFTTool output") from exc
    else:
        parsed = _headers_to_parsed(tft)
    return {
        "path": str(path),
        "parsed": parsed,
        "editor_version": tft.getEditorVersionStr(),
        "model": tft.model,
        "usercode_decode_error": decode_error,
        "embedded_font_runs": scan_embedded_tft_fonts(raw),
    }


def list_supported_tft_models() -> list[str]:
    module = _load_tfttool_module()
    return sorted(module.TFTFile._modelXORs.keys())


def _headers_to_parsed(tft: Any) -> dict[str, Any]:
    return {
        "GeneralInfo": {
            "Target Model": tft.model,
            "Usercode Decode": "skipped",
        },
        "Header1": dict(tft.header1.content),
        "Header2": {key: hex(value) if isinstance(value, int) else value for key, value in tft.header2.content.items()},
        "Bootloader": "[binary data]",
        "Pictures": "[binary data]",
        "Fonts": "[binary data]",
        "Usercode": {},
    }


def scan_embedded_tft_fonts(raw: bytes) -> list[dict[str, Any]]:
    magic = b"\x04\xff\x00\x0a"
    positions: list[int] = []
    start = 0
    while True:
        idx = raw.find(magic, start)
        if idx < 0:
            break
        positions.append(idx)
        start = idx + 1

    runs: list[dict[str, Any]] = []
    index = 0
    while index < len(positions):
        run = [positions[index]]
        cursor = index + 1
        while cursor < len(positions) and positions[cursor] - run[-1] == 0x2C:
            run.append(positions[cursor])
            cursor += 1

        if len(run) >= 2:
            base = run[0]
            entries = [_parse_embedded_font_entry(raw, base, offset) for offset in run]
            runs.append(
                {
                    "base_offset": base,
                    "base_offset_hex": f"0x{base:X}",
                    "count": len(entries),
                    "entries": entries,
                }
            )
            index = cursor
            continue

        index += 1

    return runs


def _load_tfttool_module():
    if not TFTTOOL_PY.exists():
        raise TftToolchainError(f"TFTTool.py not found at {TFTTOOL_PY}")

    if str(TFTTOOL_DIR) not in sys.path:
        sys.path.insert(0, str(TFTTOOL_DIR))

    spec = importlib.util.spec_from_file_location("_local_tfttool", TFTTOOL_PY)
    if spec is None or spec.loader is None:
        raise TftToolchainError("Unable to create import spec for TFTTool.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_embedded_font_entry(raw: bytes, base: int, offset: int) -> dict[str, Any]:
    header = raw[offset : offset + 0x2C]
    codepage = header[4]
    char_w = header[6]
    char_h = header[7]
    char_count = int.from_bytes(header[0x0C:0x10], "little")
    version = header[0x10]
    descriptor_len = header[0x11]
    variable_data_len = int.from_bytes(header[0x14:0x18], "little")
    data_start = int.from_bytes(header[0x18:0x1C], "little")
    file_name_len = header[0x20]
    align8 = header[0x21]
    total_chars = int.from_bytes(header[0x24:0x28], "little")

    name_offset = base + data_start
    name_bytes = raw[name_offset : name_offset + descriptor_len]
    font_name = name_bytes[:file_name_len].decode("ascii", errors="replace")
    encoding_name = name_bytes[file_name_len:descriptor_len].decode("ascii", errors="replace")

    return {
        "offset": offset,
        "offset_hex": f"0x{offset:X}",
        "codepage": codepage,
        "char_width": char_w,
        "char_height": char_h,
        "char_count": char_count,
        "version": version,
        "descriptor_len": descriptor_len,
        "variable_data_len": variable_data_len,
        "data_start": data_start,
        "data_start_hex": f"0x{data_start:X}",
        "file_name_len": file_name_len,
        "align8": align8,
        "total_chars": total_chars,
        "font_name": font_name,
        "encoding_name": encoding_name,
    }
