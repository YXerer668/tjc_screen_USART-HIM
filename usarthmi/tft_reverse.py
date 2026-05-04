from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .page_format import PageBlock, load_page_file
from .tft_toolchain import TftToolchainError, inspect_tft


ASCII_RE = re.compile(rb"[ -~]{3,}")
COORD_FIELDS = ("x", "y", "w", "h", "endx", "endy")
PAGE_SIZE_FIELDS = ("w", "h", "endx", "endy")
STRING_FIELDS = ("objname", "txt", "type")


def reverse_tft_tail(
    file_path: str | Path,
    *,
    hmi_pa_path: str | Path | None = None,
    install_dir: str | Path | None = None,
    context_bytes: int = 48,
) -> dict[str, Any]:
    """Probe the compiled TFT object tail by aligning it with a parsed .pa page.

    This is intentionally an evidence-gathering helper, not a complete decoder.
    It answers: "where did this HMI page/object data land in the TFT?"
    """

    path = Path(file_path).resolve()
    raw = path.read_bytes()
    inspection = inspect_tft(path)
    header2 = _get_header2(inspection)
    object_start = _header_int(header2, "unknown_objects_address")
    picture_start = _header_int(header2, "pictures_address")
    if object_start is None or picture_start is None:
        raise TftToolchainError("TFT header does not expose object/picture section addresses")
    if not (0 <= object_start <= picture_start <= len(raw)):
        raise TftToolchainError(
            f"Invalid TFT object region: objects=0x{object_start:X}, pictures=0x{picture_start:X}, size=0x{len(raw):X}"
        )

    object_region = raw[object_start:picture_start]
    tail_region = raw[object_start:]
    result: dict[str, Any] = {
        "mode": "reverse_probe",
        "notes": [
            "This output is a byte-level alignment probe, not a complete TFT decoder.",
            "Offsets are stable evidence for implementing the independent TFT writer.",
        ],
        "file_path": str(path),
        "file_size": len(raw),
        "editor_version": inspection.get("editor_version"),
        "model": inspection.get("model"),
        "usercode_decode_error": inspection.get("usercode_decode_error"),
        "object_region": {
            "start": object_start,
            "start_hex": f"0x{object_start:X}",
            "end": picture_start,
            "end_hex": f"0x{picture_start:X}",
            "size": len(object_region),
            "size_hex": f"0x{len(object_region):X}",
        },
        "compiled_tail_region": {
            "start": object_start,
            "start_hex": f"0x{object_start:X}",
            "tfttool_pictures_address": picture_start,
            "tfttool_pictures_address_hex": f"0x{picture_start:X}",
            "end": len(raw),
            "end_hex": f"0x{len(raw):X}",
            "size": len(tail_region),
            "size_hex": f"0x{len(tail_region):X}",
            "notes": [
                "The TFTTool pictures_address is not the end of compiled object data for TJC 1.67.6.",
                "Coordinate mirrors and the final 4-byte checksum/hash live after that address.",
            ],
        },
        "ascii_strings": _ascii_strings(tail_region, base=object_start),
    }
    resource_matches: list[dict[str, Any]] = []

    if hmi_pa_path is not None:
        page_path = Path(hmi_pa_path).resolve()
        page = load_page_file(page_path)
        blocks = [
            _probe_block(block, index, tail_region, object_start, context_bytes)
            for index, block in enumerate(page.blocks)
        ]
        _attach_record_layout(blocks, tail_region, object_start)
        text_pointer_bias = _attach_text_pointer_layout(blocks, tail_region)
        value_offsets = [
            item["compiled_record_candidate"]["value_blob_offset"]
            for item in blocks
            if item.get("compiled_record_candidate")
        ]
        result["hmi_pa_path"] = str(page_path)
        result["hmi_page"] = {
            "page_name": page.page_name,
            "object_count": page.object_count,
            "magic_hex": f"0x{page.magic:X}",
            "compiled_text_pointer_bias": text_pointer_bias,
            "compiled_value_offset_table": _probe_value_offset_table(
                tail_region,
                object_start,
                value_offsets,
                context_bytes,
            ),
            "blocks": blocks,
        }
        hmi_matches = _probe_hmi_resource_matches(raw, page_path.parent)
        result["hmi_resource_matches"] = hmi_matches
        resource_matches.extend(hmi_matches)

    if install_dir is not None:
        install_matches = _probe_install_resource_matches(raw, Path(install_dir))
        result["install_resource_matches"] = install_matches
        resource_matches.extend(install_matches)

    result["resource_directory_probe"] = _probe_resource_directory(raw, header2, resource_matches)

    return result


def _probe_block(
    block: PageBlock,
    index: int,
    object_region: bytes,
    object_start: int,
    context_bytes: int,
) -> dict[str, Any]:
    summary = _block_summary(block, index)
    coord_values = [_field_as_int(block, name) for name in COORD_FIELDS]
    coord_sequence: dict[str, Any] | None = None
    if all(value is not None for value in coord_values):
        payload = b"".join(int(value).to_bytes(2, "little") for value in coord_values if value is not None)
        matches = _match_windows(object_region, object_start, payload, context_bytes)
        coord_sequence = {
            "fields": list(COORD_FIELDS),
            "values": [int(value) for value in coord_values if value is not None],
            "hex": payload.hex(" "),
            "matches": matches,
        }

    page_size_sequence: dict[str, Any] | None = None
    page_values = [_field_as_int(block, name) for name in PAGE_SIZE_FIELDS]
    if all(value is not None for value in page_values):
        payload = b"".join(int(value).to_bytes(2, "little") for value in page_values if value is not None)
        matches = _match_windows(object_region, object_start, payload, context_bytes)
        page_size_sequence = {
            "fields": list(PAGE_SIZE_FIELDS),
            "values": [int(value) for value in page_values if value is not None],
            "hex": payload.hex(" "),
            "matches": matches,
        }

    strings: list[dict[str, Any]] = []
    for field_name in STRING_FIELDS:
        value = _field_as_text(block, field_name)
        if value:
            payload = value.encode("ascii", errors="ignore")
            strings.append(
                {
                    "field": field_name,
                    "value": value,
                    "hex": payload.hex(" "),
                    "matches": _match_windows(object_region, object_start, payload, context_bytes),
                }
            )

    summary["coordinate_sequence"] = coord_sequence
    summary["page_size_sequence"] = page_size_sequence
    summary["string_matches"] = strings
    summary["compiled_record_candidate"] = _record_candidate(
        block,
        object_region,
        object_start,
        coord_sequence,
    )
    return summary


def _record_candidate(
    block: PageBlock,
    object_region: bytes,
    object_start: int,
    coord_sequence: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if coord_sequence is None or not coord_sequence.get("matches"):
        return None
    coord_relative = coord_sequence["matches"][0]["relative_offset"]
    body_relative = coord_relative - 0x0C
    header_relative = body_relative - 0x1C
    if header_relative < 0 or body_relative < 0 or body_relative + 0x18 > len(object_region):
        return None

    header = object_region[header_relative : header_relative + 4]
    body_prefix = object_region[body_relative : body_relative + 0x18]
    value_blob_offset = int.from_bytes(body_prefix[:4], "little")
    record_type = chr(header[0]) if 32 <= header[0] <= 126 else None
    hmi_id = _field_as_int(block, "id")
    return {
        "inference": "coord_offset - 0x0C = body start; body start - 0x1C = object header",
        "header_relative_offset": header_relative,
        "header_relative_offset_hex": f"0x{header_relative:X}",
        "header_absolute_offset": object_start + header_relative,
        "header_absolute_offset_hex": f"0x{object_start + header_relative:X}",
        "body_relative_offset": body_relative,
        "body_relative_offset_hex": f"0x{body_relative:X}",
        "body_absolute_offset": object_start + body_relative,
        "body_absolute_offset_hex": f"0x{object_start + body_relative:X}",
        "coord_relative_offset": coord_relative,
        "coord_relative_offset_hex": f"0x{coord_relative:X}",
        "coord_absolute_offset": object_start + coord_relative,
        "coord_absolute_offset_hex": f"0x{object_start + coord_relative:X}",
        "header_hex": header.hex(" "),
        "header_type": record_type,
        "header_id": header[1],
        "header_unknown_2": header[2],
        "header_unknown_3": header[3],
        "matches_hmi_type": record_type == block.type_code,
        "matches_hmi_id": hmi_id is not None and header[1] == hmi_id,
        "value_blob_offset": value_blob_offset,
        "value_blob_offset_hex": f"0x{value_blob_offset:X}",
        "body_prefix_hex": body_prefix.hex(" "),
        "body_prefix_fields": {
            "value_blob_offset": value_blob_offset,
            "unknown_04": body_prefix[4],
            "unknown_05": body_prefix[5],
            "aph_like_06": body_prefix[6],
            "unknown_07_to_0b_hex": body_prefix[7:12].hex(" "),
            "coords_start_at_body_plus": "0x0C",
        },
    }


def _attach_record_layout(blocks: list[dict[str, Any]], object_region: bytes, object_start: int) -> None:
    records: list[tuple[int, dict[str, Any]]] = []
    string_pool_start = _first_text_string_offset(blocks)
    for block in blocks:
        candidate = block.get("compiled_record_candidate")
        if not candidate:
            continue
        records.append((candidate["header_relative_offset"], candidate))
    records.sort(key=lambda item: item[0])

    for index, (header_relative, candidate) in enumerate(records):
        if index + 1 < len(records):
            end_relative = records[index + 1][0]
            end_reason = "next_object_header"
        elif string_pool_start is not None and string_pool_start > header_relative:
            end_relative = string_pool_start
            end_reason = "first_text_string"
        else:
            end_relative = min(len(object_region), candidate["body_relative_offset"] + 0x40)
            end_reason = "fallback_window"

        candidate["record_end_relative_offset"] = end_relative
        candidate["record_end_relative_offset_hex"] = f"0x{end_relative:X}"
        candidate["record_end_absolute_offset"] = object_start + end_relative
        candidate["record_end_absolute_offset_hex"] = f"0x{object_start + end_relative:X}"
        candidate["record_length"] = end_relative - header_relative
        candidate["record_length_hex"] = f"0x{end_relative - header_relative:X}"
        candidate["record_end_reason"] = end_reason
        candidate["record_hex"] = object_region[header_relative:end_relative].hex(" ")


def _first_text_string_offset(blocks: list[dict[str, Any]]) -> int | None:
    offsets: list[int] = []
    for block in blocks:
        for item in block.get("string_matches", []):
            if item.get("field") != "txt":
                continue
            for match in item.get("matches", []):
                offsets.append(match["relative_offset"])
    return min(offsets) if offsets else None


def _probe_value_offset_table(
    object_region: bytes,
    object_start: int,
    offsets: list[int],
    context_bytes: int,
) -> dict[str, Any] | None:
    if not offsets:
        return None
    payload = b"".join(int(value).to_bytes(4, "little") for value in offsets)
    matches = _match_windows(object_region, object_start, payload, context_bytes)
    return {
        "inference": "u32 list of compiled object value offsets, matching each object body's first dword",
        "values": offsets,
        "values_hex": [f"0x{value:X}" for value in offsets],
        "hex": payload.hex(" "),
        "matches": matches,
    }


def _attach_text_pointer_layout(blocks: list[dict[str, Any]], object_region: bytes) -> dict[str, Any] | None:
    text_blocks: list[tuple[dict[str, Any], list[int]]] = []
    for block in blocks:
        text_offsets = _string_match_offsets(block, "txt")
        if not text_offsets or not block.get("compiled_record_candidate"):
            continue
        text_blocks.append((block, text_offsets))
    if not text_blocks:
        return None

    candidate_groups: dict[int, list[dict[str, Any]]] = {}
    per_block: dict[int, list[dict[str, Any]]] = {}
    for block, text_offsets in text_blocks:
        record = block["compiled_record_candidate"]
        body_start = record["body_relative_offset"]
        body_end = record["record_end_relative_offset"]
        candidates: list[dict[str, Any]] = []
        for relative in range(body_start, max(body_start, body_end - 3), 4):
            value = int.from_bytes(object_region[relative : relative + 4], "little")
            if value == 0:
                continue
            for text_offset in text_offsets:
                if value >= text_offset:
                    continue
                bias = text_offset - value
                if bias > len(object_region):
                    continue
                item = {
                    "body_plus": relative - body_start,
                    "body_plus_hex": f"0x{relative - body_start:X}",
                    "relative_offset": relative,
                    "relative_offset_hex": f"0x{relative:X}",
                    "value": value,
                    "value_hex": f"0x{value:X}",
                    "text_relative_offset": text_offset,
                    "text_relative_offset_hex": f"0x{text_offset:X}",
                    "bias": bias,
                    "bias_hex": f"0x{bias:X}",
                }
                candidates.append(item)
                candidate_groups.setdefault(bias, []).append({"objname": block.get("objname"), **item})
        per_block[block["block_index"]] = candidates

    if not candidate_groups:
        return None

    best_bias, best_items = max(
        candidate_groups.items(),
        key=lambda item: (len({entry["objname"] for entry in item[1]}), len(item[1]), -item[0]),
    )
    if len({entry["objname"] for entry in best_items}) < 2 and len(text_blocks) > 1:
        return {
            "inference": "no shared text pointer bias found",
            "candidate_groups": _text_bias_groups(candidate_groups),
        }

    for block, _ in text_blocks:
        candidates = [
            item for item in per_block.get(block["block_index"], []) if item["bias"] == best_bias
        ]
        if candidates:
            block["compiled_record_candidate"]["text_pointer_candidate"] = candidates[0]

    return {
        "inference": "compiled text u32 pointer plus this bias equals the string offset in the object region",
        "bias": best_bias,
        "bias_hex": f"0x{best_bias:X}",
        "matched_objects": sorted({item["objname"] for item in best_items}),
        "candidate_groups": _text_bias_groups(candidate_groups),
    }


def _string_match_offsets(block: dict[str, Any], field_name: str) -> list[int]:
    offsets: list[int] = []
    for item in block.get("string_matches", []):
        if item.get("field") != field_name:
            continue
        for match in item.get("matches", []):
            offsets.append(match["relative_offset"])
    return sorted(set(offsets))


def _text_bias_groups(candidate_groups: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    result = []
    for bias, items in sorted(candidate_groups.items(), key=lambda item: (-len(item[1]), item[0])):
        result.append(
            {
                "bias": bias,
                "bias_hex": f"0x{bias:X}",
                "count": len(items),
                "objects": [item["objname"] for item in items],
                "items": items,
            }
        )
    return result


def _probe_hmi_resource_matches(tft_raw: bytes, hmi_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name in ("Program.s", "0.pa", "0.i", "0.is", "0.zi"):
        path = hmi_dir / name
        if not path.exists():
            continue
        data = path.read_bytes()
        exact_offset = tft_raw.find(data)
        item: dict[str, Any] = {
            "name": name,
            "path": str(path.resolve()),
            "size": len(data),
            "exact_match": _offset_item(exact_offset) if exact_offset >= 0 else None,
            "chunk_probes": _resource_chunk_probes(tft_raw, data),
        }
        results.append(item)
    return results


def _probe_install_resource_matches(tft_raw: bytes, install_dir: Path) -> list[dict[str, Any]]:
    names = (
        "2.cc",
        "3.cc",
        "4.cc",
        "5.cc",
        "cdx.dll",
        "syscom.bin",
        "ch0_com.bin",
        "ch0_va.bin",
        "ch1_com.bin",
        "ch1_va.bin",
        "model0.sa",
        "model1.sa",
        "other1.sa",
        "gsall.bin",
        "input.bin",
        "qr0.bin",
    )
    results: list[dict[str, Any]] = []
    for name in names:
        path = install_dir / name
        if not path.exists():
            continue
        data = path.read_bytes()
        exact_offset = tft_raw.find(data)
        results.append(
            {
                "name": name,
                "path": str(path.resolve()),
                "size": len(data),
                "exact_match": _offset_item(exact_offset) if exact_offset >= 0 else None,
                "chunk_probes": [] if exact_offset >= 0 else _resource_chunk_probes(tft_raw, data),
            }
        )
    return results


def _probe_resource_directory(
    tft_raw: bytes,
    header2: dict[str, Any],
    resource_matches: list[dict[str, Any]],
) -> dict[str, Any] | None:
    start = _header_int(header2, "unknown_pages_address")
    if start is None or start + 4 > len(tft_raw):
        return None
    directory_size = int.from_bytes(tft_raw[start : start + 4], "little")
    if directory_size <= 0 or directory_size > 0x1000 or start + directory_size > len(tft_raw):
        return None

    words = []
    for relative in range(0, directory_size, 4):
        value = int.from_bytes(tft_raw[start + relative : start + relative + 4], "little")
        words.append(
            {
                "index": relative // 4,
                "relative_offset": relative,
                "relative_offset_hex": f"0x{relative:X}",
                "value": value,
                "value_hex": f"0x{value:X}",
            }
        )

    matched_entries = []
    for item in resource_matches:
        exact = item.get("exact_match")
        if not exact:
            continue
        relative_offset = exact["offset"] - start
        if relative_offset < 0:
            continue
        size = item["size"]
        offset_word_indexes = [word["index"] for word in words if word["value"] == relative_offset]
        size_word_indexes = [word["index"] for word in words if word["value"] == size]
        if not offset_word_indexes and not size_word_indexes:
            continue
        matched_entries.append(
            {
                "name": item["name"],
                "relative_offset": relative_offset,
                "relative_offset_hex": f"0x{relative_offset:X}",
                "absolute_offset": exact["offset"],
                "absolute_offset_hex": exact["offset_hex"],
                "size": size,
                "size_hex": f"0x{size:X}",
                "offset_word_indexes": offset_word_indexes,
                "size_word_indexes": size_word_indexes,
            }
        )

    return {
        "inference": "directory at Header2 unknown_pages_address; values are relative to this directory start",
        "start": start,
        "start_hex": f"0x{start:X}",
        "size": directory_size,
        "size_hex": f"0x{directory_size:X}",
        "words": words,
        "matched_entries": matched_entries,
    }


def _resource_chunk_probes(tft_raw: bytes, data: bytes) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    for chunk_size in (4096, 1024, 512, 256, 128, 64, 32, 16, 8):
        if len(data) < chunk_size:
            continue
        offsets = [
            ("start", 0),
            ("middle", max(0, len(data) // 2 - chunk_size // 2)),
            ("end", len(data) - chunk_size),
        ]
        matches = []
        for label, resource_offset in offsets:
            chunk = data[resource_offset : resource_offset + chunk_size]
            tft_offset = tft_raw.find(chunk)
            if tft_offset >= 0:
                matches.append(
                    {
                        "label": label,
                        "resource_offset": resource_offset,
                        "resource_offset_hex": f"0x{resource_offset:X}",
                        "tft_offset": tft_offset,
                        "tft_offset_hex": f"0x{tft_offset:X}",
                    }
                )
        if matches:
            probes.append({"chunk_size": chunk_size, "matches": matches})
            break
    return probes


def _offset_item(offset: int) -> dict[str, Any]:
    return {
        "offset": offset,
        "offset_hex": f"0x{offset:X}",
    }


def _block_summary(block: PageBlock, index: int) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in block.fields:
        item: dict[str, Any] = {"hex": field.value.hex(" ")}
        text = _decode_ascii(field.value)
        if text is not None:
            item["ascii"] = text
        integer = _bytes_as_int(field.value)
        if integer is not None:
            item["int"] = integer
        fields[field.name] = item
    return {
        "block_index": index,
        "attr_name": block.attr_name,
        "attr_marker": block.attr_marker,
        "type": block.type_code,
        "objname": block.objname,
        "event_tokens": list(block.event_tokens),
        "fields": fields,
    }


def _get_header2(inspection: dict[str, Any]) -> dict[str, Any]:
    parsed = inspection.get("parsed")
    if not isinstance(parsed, dict):
        raise TftToolchainError("TFT inspection did not return parsed headers")
    header2 = parsed.get("Header2")
    if not isinstance(header2, dict):
        raise TftToolchainError("TFT inspection did not return Header2")
    return header2


def _header_int(header: dict[str, Any], key: str) -> int | None:
    value = header.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _ascii_strings(data: bytes, *, base: int, minimum: int = 3, limit: int = 200) -> list[dict[str, Any]]:
    strings: list[dict[str, Any]] = []
    for match in ASCII_RE.finditer(data):
        if len(match.group(0)) < minimum:
            continue
        start = match.start()
        strings.append(
            {
                "relative_offset": start,
                "relative_offset_hex": f"0x{start:X}",
                "absolute_offset": base + start,
                "absolute_offset_hex": f"0x{base + start:X}",
                "text": match.group(0).decode("ascii", errors="replace"),
            }
        )
        if len(strings) >= limit:
            break
    return strings


def _match_windows(data: bytes, base: int, needle: bytes, context_bytes: int) -> list[dict[str, Any]]:
    return [_window(data, base, offset, len(needle), context_bytes) for offset in _find_all(data, needle)]


def _window(data: bytes, base: int, offset: int, length: int, context_bytes: int) -> dict[str, Any]:
    context_start = max(0, offset - context_bytes)
    context_end = min(len(data), offset + length + context_bytes)
    return {
        "relative_offset": offset,
        "relative_offset_hex": f"0x{offset:X}",
        "absolute_offset": base + offset,
        "absolute_offset_hex": f"0x{base + offset:X}",
        "length": length,
        "context_relative_start": context_start,
        "context_relative_start_hex": f"0x{context_start:X}",
        "context_absolute_start": base + context_start,
        "context_absolute_start_hex": f"0x{base + context_start:X}",
        "context_hex": data[context_start:context_end].hex(" "),
    }


def _find_all(data: bytes, needle: bytes) -> list[int]:
    if not needle:
        return []
    offsets: list[int] = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return offsets
        offsets.append(offset)
        start = offset + 1


def _field_as_int(block: PageBlock, name: str) -> int | None:
    field = block.get_field(name)
    if field is None:
        return None
    return _bytes_as_int(field.value)


def _field_as_text(block: PageBlock, name: str) -> str | None:
    field = block.get_field(name)
    if field is None:
        return None
    return _decode_ascii(field.value)


def _bytes_as_int(value: bytes) -> int | None:
    if not value or len(value) > 4:
        return None
    return int.from_bytes(value, "little", signed=False)


def _decode_ascii(value: bytes) -> str | None:
    if not value:
        return None
    try:
        text = value.decode("ascii")
    except UnicodeDecodeError:
        return None
    if all((32 <= ord(ch) <= 126) or ch in "\t\r\n" for ch in text):
        return text
    return None
