from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from .hmi_inspect import extract_hmi
from .page_format import PageBlock, load_page_file
from .tft_reverse import reverse_tft_tail


def compare_case_folder(
    case_root: str | Path,
    *,
    out_dir: str | Path | None = None,
    baseline_case: str = "case_00_baseline",
    install_dir: str | Path | None = None,
    context_bytes: int = 16,
    diff_run_limit: int = 64,
) -> dict[str, Any]:
    root = Path(case_root).resolve()
    if not root.exists():
        raise FileNotFoundError(root)

    output = Path(out_dir).resolve() if out_dir is not None else None
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)

    case_dirs = sorted(item for item in root.iterdir() if item.is_dir())
    baseline_dir = root / baseline_case
    baseline_tft = _find_one(baseline_dir, "*.tft")
    baseline_payload = baseline_tft.read_bytes()

    cases = []
    for case_dir in case_dirs:
        hmi_path = _find_one(case_dir, "*.HMI")
        tft_path = _find_one(case_dir, "*.tft")
        case_out = output / case_dir.name if output is not None else None
        extract_dir = case_out / "extract" if case_out is not None else None
        if extract_dir is not None:
            extract_dir.mkdir(parents=True, exist_ok=True)
            extract_hmi(hmi_path, extract_dir)
            pa_path = extract_dir / "0.pa"
        else:
            raise ValueError("out_dir is required so HMI extraction has a stable location")

        page = load_page_file(pa_path)
        reverse = reverse_tft_tail(
            tft_path,
            hmi_pa_path=pa_path,
            install_dir=install_dir,
            context_bytes=context_bytes,
        )
        if case_out is not None:
            (case_out / "reverse_tail.json").write_text(
                json.dumps(reverse, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        tft_payload = tft_path.read_bytes()
        cases.append(
            {
                "case": case_dir.name,
                "hmi_path": str(hmi_path),
                "tft_path": str(tft_path),
                "hmi_pa_path": str(pa_path),
                "hmi_page": _summarize_page(page),
                "tft": {
                    "file_size": len(tft_payload),
                    "final_word_hex": f"0x{int.from_bytes(tft_payload[-4:], 'little'):08X}",
                    "object_region": reverse.get("object_region"),
                    "compiled_tail_region": reverse.get("compiled_tail_region"),
                    "block_matches": _summarize_reverse_blocks(reverse),
                    "resource_directory_probe": reverse.get("resource_directory_probe"),
                },
                "baseline_diff": _diff_payloads(
                    baseline_payload,
                    tft_payload,
                    limit=diff_run_limit,
                ),
            }
        )

    result = {
        "mode": "tft_case_compare",
        "case_root": str(root),
        "baseline_case": baseline_case,
        "baseline_tft": str(baseline_tft),
        "out_dir": str(output) if output is not None else None,
        "cases": cases,
    }
    if output is not None:
        (output / "summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return result


def _find_one(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No {pattern} found in {directory}")
    if len(matches) > 1:
        raise ValueError(f"Expected one {pattern} in {directory}, found {len(matches)}")
    return matches[0].resolve()


def _summarize_page(page: Any) -> dict[str, Any]:
    return {
        "page_name": page.page_name,
        "object_count": page.object_count,
        "pa_size": page.total_length,
        "blocks": [_summarize_block(block) for block in page.blocks],
    }


def _summarize_block(block: PageBlock) -> dict[str, Any]:
    return {
        "type": block.type_code,
        "objname": block.objname,
        "id": _field_int(block, "id"),
        "x": _field_int(block, "x"),
        "y": _field_int(block, "y"),
        "w": _field_int(block, "w"),
        "h": _field_int(block, "h"),
        "endx": _field_int(block, "endx"),
        "endy": _field_int(block, "endy"),
        "txt": _field_text(block, "txt"),
        "pic": _field_int(block, "pic"),
        "font": _field_int(block, "font"),
        "bco": _field_int(block, "bco"),
        "style": _field_int(block, "style"),
    }


def _summarize_reverse_blocks(reverse: dict[str, Any]) -> list[dict[str, Any]]:
    page = reverse.get("hmi_page")
    if not isinstance(page, dict):
        return []
    result = []
    for block in page.get("blocks", []):
        candidate = block.get("compiled_record_candidate") or {}
        coords = block.get("coordinate_sequence") or {}
        text_pointer = candidate.get("text_pointer_candidate")
        result.append(
            {
                "type": block.get("type"),
                "objname": block.get("objname"),
                "header": candidate.get("header_relative_offset_hex"),
                "body": candidate.get("body_relative_offset_hex"),
                "value_offset": candidate.get("value_blob_offset_hex"),
                "record_length": candidate.get("record_length_hex"),
                "coord_matches": [item.get("relative_offset_hex") for item in coords.get("matches", [])],
                "text_pointer": text_pointer,
            }
        )
    return result


def _diff_payloads(base: bytes, other: bytes, *, limit: int) -> dict[str, Any]:
    common = min(len(base), len(other))
    first = None
    runs = []
    index = 0
    while index < common:
        if base[index] == other[index]:
            index += 1
            continue
        start = index
        while index < common and base[index] != other[index]:
            index += 1
        if first is None:
            first = start
        if len(runs) < limit:
            runs.append(
                {
                    "offset": start,
                    "offset_hex": f"0x{start:X}",
                    "length": index - start,
                    "base_hex": base[start : min(index, start + 32)].hex(" "),
                    "case_hex": other[start : min(index, start + 32)].hex(" "),
                }
            )

    return {
        "file_size_delta": len(other) - len(base),
        "first_diff_offset": first,
        "first_diff_offset_hex": f"0x{first:X}" if first is not None else None,
        "diff_run_count": _count_diff_runs(base, other),
        "diff_runs_truncated_to": limit,
        "diff_runs": runs,
    }


def _count_diff_runs(base: bytes, other: bytes) -> int:
    common = min(len(base), len(other))
    count = 0
    index = 0
    while index < common:
        if base[index] == other[index]:
            index += 1
            continue
        count += 1
        while index < common and base[index] != other[index]:
            index += 1
    if len(base) != len(other):
        count += 1
    return count


def _field_int(block: PageBlock, name: str) -> int | None:
    field = block.get_field(name)
    if field is None or not (0 < len(field.value) <= 4):
        return None
    return int.from_bytes(field.value, "little")


def _field_text(block: PageBlock, name: str) -> str | None:
    field = block.get_field(name)
    if field is None or not field.value:
        return None
    try:
        return field.value.decode("ascii")
    except UnicodeDecodeError:
        return field.value.decode("ascii", errors="replace")
