from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .page_format import PageBlock, load_page_file
from .tft_checksum import _crc32_like, update_tft_checksum
from .tft_reverse import reverse_tft_tail
from .tft_toolchain import TftToolchainError, _load_tfttool_module, inspect_tft


COORD_FIELDS = ("x", "y", "w", "h", "endx", "endy")
TYPE_RECORD_LENGTHS = {"y": 0x40, "t": 0x54, "b": 0x54, "p": 0x3C}
TYPE_USER_SLOT_COUNTS = {"y": 33, "t": 41, "b": 42, "p": 28}
KNOWN_OBJECT_NAME_HASHES = {
    # Recovered from official one-object-add fixtures for the current seed.
    "t1": 0xB64689A1,
    "b1": 0xB8756F4E,
    "p1": 0x207A7E7A,
}
HEADER1_FILE_SIZE_OFFSET = 0x3C
HEADER1_CRC_OFFSET = 0xC4
HEADER2_START = 0xC8
HEADER2_CRC_OFFSET = HEADER2_START + 0xC4
HEADER2_FIELD_OFFSETS = {
    "static_usercode_address": 0x00,
    "app_attributes_data_address": 0x04,
    "usercode_address": 0x0C,
    "pictures_address": 0x18,
    "gmovs_address": 0x1C,
    # TFTTool labels this as audios_count, but these local TJC 1.67.6
    # fixtures use it as the page object count.
    "compiled_object_count": 0x3A,
}


@dataclass(slots=True)
class BasicPatchResult:
    baseline_tft: str
    baseline_pa: str
    target_pa: str
    out_tft: str
    file_size: int
    checksum_mode: str
    patched_coordinates: int
    patched_text_slots: int
    final_word_note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "experimental_basic_tft_patch",
            "baseline_tft": self.baseline_tft,
            "baseline_pa": self.baseline_pa,
            "target_pa": self.target_pa,
            "out_tft": self.out_tft,
            "file_size": self.file_size,
            "checksum_mode": self.checksum_mode,
            "patched_coordinates": self.patched_coordinates,
            "patched_text_slots": self.patched_text_slots,
            "final_word_note": self.final_word_note,
            "warnings": [
                "V0 only supports unchanged object count/type/order.",
                "V0 patches coordinate sequences and fixed-size text slots in an official baseline TFT.",
                "The final 4-byte TFT checksum is recomputed, but the object-tail generator is still limited to same-layout patches.",
            ],
        }


@dataclass(slots=True)
class AddedObjectPatchResult:
    baseline_tft: str
    baseline_pa: str
    target_pa: str
    out_tft: str
    file_size: int
    object_count: int
    added_object: str
    added_type: str
    section_offsets: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "experimental_added_object_tft_patch",
            "baseline_tft": self.baseline_tft,
            "baseline_pa": self.baseline_pa,
            "target_pa": self.target_pa,
            "out_tft": self.out_tft,
            "file_size": self.file_size,
            "object_count": self.object_count,
            "added_object": self.added_object,
            "added_type": self.added_type,
            "section_offsets": {
                key: {"value": value, "hex": f"0x{value:X}"}
                for key, value in self.section_offsets.items()
            },
            "warnings": [
                "Experimental V1 supports adding exactly one t/b/p object to the current seed layout.",
                "Object-name hashes are currently known only for page0/t0/b0/p0 plus t1/b1/p1 fixtures.",
                "Header CRCs, encrypted Header2 fields, and the final TFT checksum are recomputed.",
            ],
        }


@dataclass(slots=True)
class _UserRecordTemplate:
    slot_index: int
    word1_mode: str
    word1_delta: int
    word2: int
    word3: int
    word5: int


@dataclass(slots=True)
class _TailSeed:
    baseline_tft: Path
    baseline_pa: Path
    raw: bytes
    object_start: int
    model: str
    model_series: int
    prefix_head: bytes
    page_event: bytes
    object_event: bytes
    user_header: bytes
    primary_templates: dict[str, bytes]
    user_templates: dict[str, list[_UserRecordTemplate]]
    mirror_templates: dict[str, list[int | None]]
    hash_by_name: dict[str, int]


def patch_basic_tft(
    baseline_tft: str | Path,
    *,
    baseline_pa: str | Path,
    target_pa: str | Path,
    out_tft: str | Path,
    checksum_mode: str = "recompute",
) -> BasicPatchResult:
    """Patch a same-layout TFT using target .pa coordinates and text.

    This is a deliberately narrow V0 writer. It proves and automates the fields
    we have already reversed, without pretending the full compiler is complete.
    """

    if checksum_mode not in {"recompute", "keep", "zero"}:
        raise TftToolchainError("checksum_mode must be 'recompute', 'keep', or 'zero'")

    baseline_tft_path = Path(baseline_tft).resolve()
    baseline_pa_path = Path(baseline_pa).resolve()
    target_pa_path = Path(target_pa).resolve()
    out_path = Path(out_tft).resolve()

    baseline_page = load_page_file(baseline_pa_path)
    target_page = load_page_file(target_pa_path)
    _validate_same_layout(baseline_page.blocks, target_page.blocks)

    payload = bytearray(baseline_tft_path.read_bytes())
    inspection = inspect_tft(baseline_tft_path)
    header1 = _header(inspection, "Header1")
    header2 = _header(inspection, "Header2")
    model_series = _header_int(header1, "model_series")
    object_start = _header_int(header2, "unknown_objects_address")
    if object_start is None:
        raise TftToolchainError("Unable to locate unknown_objects_address in baseline TFT")
    if model_series is None:
        raise TftToolchainError("Unable to locate model_series in baseline TFT")
    tail = memoryview(payload)[object_start:]

    patched_coordinates = 0
    for base_block, target_block in zip(baseline_page.blocks, target_page.blocks):
        old_coords = _coord_payload(base_block)
        new_coords = _coord_payload(target_block)
        if old_coords == new_coords:
            continue
        patched_coordinates += _replace_all(tail, old_coords, new_coords)

    reverse = reverse_tft_tail(baseline_tft_path, hmi_pa_path=baseline_pa_path)
    block_reverse = {
        item.get("objname"): item
        for item in (reverse.get("hmi_page", {}).get("blocks", []))
    }

    patched_text_slots = 0
    target_by_name = {block.objname: block for block in target_page.blocks}
    for base_block in baseline_page.blocks:
        objname = base_block.objname
        if objname is None:
            continue
        base_text = _field_text(base_block, "txt")
        target_text = _field_text(target_by_name[objname], "txt")
        if base_text is None or target_text is None or base_text == target_text:
            continue
        text_offset = _compiled_text_offset(block_reverse.get(objname))
        if text_offset is None:
            raise TftToolchainError(f"Unable to locate compiled text slot for {objname}")
        slot_len = _text_slot_len(base_block)
        encoded = target_text.encode("ascii")
        if len(encoded) > slot_len:
            raise TftToolchainError(
                f"Target text for {objname} is {len(encoded)} bytes, exceeds slot length {slot_len}"
            )
        absolute = object_start + text_offset
        payload[absolute : absolute + slot_len] = b"\x00" * slot_len
        payload[absolute : absolute + len(encoded)] = encoded
        patched_text_slots += 1

    if checksum_mode == "recompute":
        payload = bytearray(update_tft_checksum(bytes(payload), series=model_series))
    elif checksum_mode == "zero":
        payload[-4:] = b"\x00\x00\x00\x00"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)

    return BasicPatchResult(
        baseline_tft=str(baseline_tft_path),
        baseline_pa=str(baseline_pa_path),
        target_pa=str(target_pa_path),
        out_tft=str(out_path),
        file_size=len(payload),
        checksum_mode=checksum_mode,
        patched_coordinates=patched_coordinates,
        patched_text_slots=patched_text_slots,
        final_word_note="Final 4-byte TFT checksum is recomputed when checksum_mode=recompute.",
    )


def patch_added_object_tft(
    baseline_tft: str | Path,
    *,
    baseline_pa: str | Path,
    target_pa: str | Path,
    out_tft: str | Path,
) -> AddedObjectPatchResult:
    """Recompile the current seed's TFT object tail after adding one object.

    This is still intentionally narrow, but it generates the object primary
    records, 24-byte user/attribute records, mirror records, encrypted Header2
    fields, header CRCs, and final TFT checksum instead of copying a full
    official target TFT.
    """

    baseline_tft_path = Path(baseline_tft).resolve()
    baseline_pa_path = Path(baseline_pa).resolve()
    target_pa_path = Path(target_pa).resolve()
    out_path = Path(out_tft).resolve()

    baseline_page = load_page_file(baseline_pa_path)
    target_page = load_page_file(target_pa_path)
    _validate_single_added_object(baseline_page.blocks, target_page.blocks)

    seed = _load_tail_seed(baseline_tft_path, baseline_pa_path, baseline_page)
    tail, sections = _build_added_object_tail(seed, target_page.blocks)
    payload = bytearray(seed.raw[: seed.object_start] + tail)

    _refresh_tft_headers(
        payload,
        model=seed.model,
        model_series=seed.model_series,
        object_start=seed.object_start,
        object_count=len(target_page.blocks),
        attr_relative=sections["attr"],
        user_relative=sections["user"],
        picture_relative=sections["pic"],
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)

    added = target_page.blocks[-1]
    return AddedObjectPatchResult(
        baseline_tft=str(baseline_tft_path),
        baseline_pa=str(baseline_pa_path),
        target_pa=str(target_pa_path),
        out_tft=str(out_path),
        file_size=len(payload),
        object_count=len(target_page.blocks),
        added_object=added.objname or "",
        added_type=added.type_code or "",
        section_offsets=sections,
    )


def _validate_same_layout(base_blocks: list[PageBlock], target_blocks: list[PageBlock]) -> None:
    if len(base_blocks) != len(target_blocks):
        raise TftToolchainError(
            f"Basic patch requires same object count: baseline={len(base_blocks)}, target={len(target_blocks)}"
        )
    for index, (base, target) in enumerate(zip(base_blocks, target_blocks)):
        if base.type_code != target.type_code or base.objname != target.objname:
            raise TftToolchainError(
                f"Basic patch requires same object order at index {index}: "
                f"{base.type_code}:{base.objname} != {target.type_code}:{target.objname}"
            )


def _validate_single_added_object(base_blocks: list[PageBlock], target_blocks: list[PageBlock]) -> None:
    if len(target_blocks) != len(base_blocks) + 1:
        raise TftToolchainError(
            "Added-object patch requires exactly one new object: "
            f"baseline={len(base_blocks)}, target={len(target_blocks)}"
        )
    for index, (base, target) in enumerate(zip(base_blocks, target_blocks)):
        if base.type_code != target.type_code or base.objname != target.objname:
            raise TftToolchainError(
                f"Added-object patch requires unchanged existing object order at index {index}: "
                f"{base.type_code}:{base.objname} != {target.type_code}:{target.objname}"
            )
    added_type = target_blocks[-1].type_code
    if added_type not in {"t", "b", "p"}:
        raise TftToolchainError(f"Added-object patch currently supports only t/b/p, got {added_type!r}")
    for block in target_blocks:
        if block.type_code not in TYPE_RECORD_LENGTHS:
            raise TftToolchainError(f"Unsupported object type in TFT tail generator: {block.type_code!r}")


def _load_tail_seed(
    baseline_tft: Path,
    baseline_pa: Path,
    baseline_page: Any,
) -> _TailSeed:
    raw = baseline_tft.read_bytes()
    inspection = inspect_tft(baseline_tft)
    header1 = _header(inspection, "Header1")
    header2 = _header(inspection, "Header2")
    object_start = _header_int(header2, "unknown_objects_address")
    picture_start = _header_int(header2, "pictures_address")
    attr_start = _header_int(header2, "static_usercode_address")
    user_start = _header_int(header2, "usercode_address")
    model = str(inspection.get("model") or "")
    model_series = _header_int(header1, "model_series")
    if None in {object_start, picture_start, attr_start, user_start, model_series}:
        raise TftToolchainError("Unable to inspect required TFT header fields")
    assert object_start is not None
    assert picture_start is not None
    assert attr_start is not None
    assert user_start is not None
    assert model_series is not None

    tail = raw[object_start:]
    if len(tail) < 0x187:
        raise TftToolchainError("Baseline TFT object tail is too short for current seed template extraction")

    prefix_head = tail[:0x145]
    page_event = tail[0x145:0x16D]
    object_event = tail[0x16D:0x187]
    baseline_hash_offset = 0x145 + len(page_event) + len(object_event) * (len(baseline_page.blocks) - 1)
    hash_size = int.from_bytes(tail[baseline_hash_offset : baseline_hash_offset + 4], "little")
    hash_data = tail[baseline_hash_offset + 4 : baseline_hash_offset + 4 + hash_size]
    if hash_size != len(baseline_page.blocks) * 6 or len(hash_data) != hash_size:
        raise TftToolchainError("Baseline TFT hash/index block does not match baseline .pa object count")

    by_id = {_field_int(block, "id"): block.objname for block in baseline_page.blocks}
    hash_by_name: dict[str, int] = {}
    for offset in range(0, len(hash_data), 6):
        object_hash = int.from_bytes(hash_data[offset : offset + 4], "little")
        object_id = int.from_bytes(hash_data[offset + 4 : offset + 6], "little")
        name = by_id.get(object_id)
        if name:
            hash_by_name[name] = object_hash

    primary_block_offset = baseline_hash_offset + 4 + hash_size
    primary_size = int.from_bytes(tail[primary_block_offset : primary_block_offset + 4], "little")
    primary_data_start = primary_block_offset + 4
    if primary_data_start + primary_size > len(tail):
        raise TftToolchainError("Baseline TFT primary object block is truncated")

    value_offsets = [
        int.from_bytes(tail[primary_data_start + index * 4 : primary_data_start + index * 4 + 4], "little")
        for index in range(len(baseline_page.blocks))
    ]
    record_start = primary_data_start + len(baseline_page.blocks) * 4
    primary_templates: dict[str, bytes] = {}
    cursor = record_start
    for block in baseline_page.blocks:
        type_code = block.type_code
        if type_code not in TYPE_RECORD_LENGTHS:
            raise TftToolchainError(f"Unsupported baseline object type: {type_code!r}")
        length = TYPE_RECORD_LENGTHS[type_code]
        primary_templates.setdefault(type_code, bytes(tail[cursor : cursor + length]))
        cursor += length

    user_header = tail[attr_start:user_start]
    if len(user_header) != 0x24:
        raise TftToolchainError("Baseline user/attribute header is not the expected 0x24 bytes")

    user_templates: dict[str, list[_UserRecordTemplate]] = {}
    slot_start = 0
    for block, value_base in zip(baseline_page.blocks, value_offsets):
        type_code = block.type_code
        slot_count = TYPE_USER_SLOT_COUNTS[type_code]
        entries: list[_UserRecordTemplate] = []
        for slot_index in range(slot_count):
            record = tail[user_start + (slot_start + slot_index) * 24 : user_start + (slot_start + slot_index + 1) * 24]
            if record == b"\x00" * 24:
                continue
            words = [int.from_bytes(record[index : index + 4], "little") for index in range(0, 24, 4)]
            word1_mode = "text_pointer" if words[5] == 0x0B3F else "value_delta"
            entries.append(
                _UserRecordTemplate(
                    slot_index=slot_index,
                    word1_mode=word1_mode,
                    word1_delta=words[1] - value_base,
                    word2=words[2],
                    word3=words[3],
                    word5=words[5],
                )
            )
        user_templates.setdefault(type_code, entries)
        slot_start += slot_count

    mirror_start = picture_start - object_start
    mirror_templates: dict[str, list[int | None]] = {}
    slot_start = 0
    for index, block in enumerate(baseline_page.blocks):
        type_code = block.type_code
        record = tail[mirror_start + 0x10 + index * 0x8A : mirror_start + 0x10 + (index + 1) * 0x8A]
        if len(record) != 0x8A:
            raise TftToolchainError("Baseline mirror object record is truncated")
        values: list[int | None] = []
        for offset in range(0x38, 0x8A, 2):
            value = int.from_bytes(record[offset : offset + 2], "little")
            values.append(None if value == 0xFFFF else value - slot_start)
        mirror_templates.setdefault(type_code, values)
        slot_start += TYPE_USER_SLOT_COUNTS[type_code]

    return _TailSeed(
        baseline_tft=baseline_tft,
        baseline_pa=baseline_pa,
        raw=raw,
        object_start=object_start,
        model=model,
        model_series=model_series,
        prefix_head=prefix_head,
        page_event=page_event,
        object_event=object_event,
        user_header=user_header,
        primary_templates=primary_templates,
        user_templates=user_templates,
        mirror_templates=mirror_templates,
        hash_by_name=hash_by_name,
    )


def _build_added_object_tail(
    seed: _TailSeed,
    target_blocks: list[PageBlock],
) -> tuple[bytes, dict[str, int]]:
    object_count = len(target_blocks)
    prefix = seed.prefix_head + seed.page_event + seed.object_event * (object_count - 1)
    hash_offset = len(prefix)
    hash_entries = []
    for block in target_blocks:
        name = block.objname
        if not name:
            raise TftToolchainError("Object without objname cannot be hashed")
        object_hash = seed.hash_by_name.get(name, KNOWN_OBJECT_NAME_HASHES.get(name))
        if object_hash is None:
            raise TftToolchainError(
                f"No recovered TFT object-name hash for {name!r}; known added names are "
                f"{', '.join(sorted(KNOWN_OBJECT_NAME_HASHES))}"
            )
        object_id = _required_field_int(block, "id")
        hash_entries.append((object_hash, object_id))
    hash_entries.sort(key=lambda item: item[0])
    hash_data = b"".join(
        object_hash.to_bytes(4, "little") + object_id.to_bytes(2, "little")
        for object_hash, object_id in hash_entries
    )

    out = bytearray(prefix)
    out.extend(_code_block(hash_data))
    primary_offset = len(out)
    primary_data, value_offsets, text_pointer_by_id, primary_pre_string_len = _build_primary_block(
        seed,
        target_blocks,
    )
    out.extend(_code_block(primary_data))
    out.extend(_code_block(b"\x09\x30\x08"))
    out.extend(_code_block(b""))

    attr_offset = len(out)
    user_offset = attr_offset + len(seed.user_header)
    out.extend(seed.user_header)
    out.extend(_build_user_records(seed, target_blocks, value_offsets, text_pointer_by_id))

    picture_offset = len(out)
    out.extend(
        _build_mirror_records(
            seed,
            target_blocks,
            value_offsets,
            hash_offset=hash_offset,
            user_offset=user_offset,
            primary_pre_string_len=primary_pre_string_len,
        )
    )
    out.extend(b"\x00\x00\x00\x00")
    return bytes(out), {
        "hash": hash_offset,
        "primary": primary_offset,
        "attr": attr_offset,
        "user": user_offset,
        "pic": picture_offset,
        "tail": len(out),
    }


def _build_primary_block(
    seed: _TailSeed,
    target_blocks: list[PageBlock],
) -> tuple[bytes, list[int], dict[int, int], int]:
    object_count = len(target_blocks)
    first_value = 0x10 + object_count * 4
    value_offsets: list[int] = []
    cursor = first_value
    for block in target_blocks:
        value_offsets.append(cursor)
        cursor += TYPE_RECORD_LENGTHS[block.type_code]

    primary_pre_string_len = object_count * 4 + sum(TYPE_RECORD_LENGTHS[block.type_code] for block in target_blocks)
    data = bytearray(b"".join(value.to_bytes(4, "little") for value in value_offsets))
    text_slots: list[tuple[str, int]] = []
    text_pointer_by_id: dict[int, int] = {}
    string_cursor = 0
    for block, value_base in zip(target_blocks, value_offsets):
        type_code = block.type_code
        record = bytearray(seed.primary_templates[type_code])
        object_id = _required_field_int(block, "id")
        record[0] = ord(type_code)
        record[1] = object_id
        record[2] = 0
        record[3] = 0x37
        record[0x1C:0x20] = value_base.to_bytes(4, "little")
        record[0x28:0x34] = _coord_payload(block)
        if type_code in {"t", "b"}:
            text = _field_text(block, "txt") or ""
            slot_len = _text_slot_len(block)
            pointer = primary_pre_string_len + 0x14 + string_cursor
            text_pointer_by_id[object_id] = pointer
            pointer_offset = 0x1C + (0x2C if type_code == "t" else 0x30)
            record[pointer_offset : pointer_offset + 4] = pointer.to_bytes(4, "little")
            text_slots.append((text, slot_len))
            string_cursor += slot_len
        elif type_code == "p":
            picture_id = _field_int(block, "pic") or 0
            record[0x38:0x3A] = picture_id.to_bytes(2, "little")
        data.extend(record)

    data.extend(b"\x00\x00\x00\x00")
    for text, slot_len in text_slots:
        encoded = text.encode("ascii")
        if len(encoded) > slot_len:
            raise TftToolchainError(f"Text {text!r} exceeds compiled text slot length {slot_len}")
        data.extend(encoded.ljust(slot_len, b"\x00"))
    data.extend(b"\x00\x00\x00\x00")
    return bytes(data), value_offsets, text_pointer_by_id, primary_pre_string_len


def _build_user_records(
    seed: _TailSeed,
    target_blocks: list[PageBlock],
    value_offsets: list[int],
    text_pointer_by_id: dict[int, int],
) -> bytes:
    out = bytearray()
    for block, value_base in zip(target_blocks, value_offsets):
        type_code = block.type_code
        object_id = _required_field_int(block, "id")
        slots = [b"\x00" * 24 for _ in range(TYPE_USER_SLOT_COUNTS[type_code])]
        for template in seed.user_templates[type_code]:
            if template.word1_mode == "text_pointer":
                word1 = text_pointer_by_id[object_id]
            else:
                word1 = value_base + template.word1_delta
            words = [
                value_base,
                word1,
                template.word2,
                template.word3,
                0x00FF0000 | (object_id << 8),
                template.word5,
            ]
            slots[template.slot_index] = b"".join(word.to_bytes(4, "little") for word in words)
        out.extend(b"".join(slots))
    return bytes(out)


def _build_mirror_records(
    seed: _TailSeed,
    target_blocks: list[PageBlock],
    value_offsets: list[int],
    *,
    hash_offset: int,
    user_offset: int,
    primary_pre_string_len: int,
) -> bytes:
    out = bytearray()
    out.extend((len(target_blocks) << 16).to_bytes(4, "little"))
    out.extend(hash_offset.to_bytes(4, "little"))
    out.extend(user_offset.to_bytes(4, "little"))
    out.extend(primary_pre_string_len.to_bytes(4, "little"))

    slot_start = 0
    for index, (block, value_base) in enumerate(zip(target_blocks, value_offsets)):
        type_code = block.type_code
        object_id = _required_field_int(block, "id")
        record = bytearray(bytes([ord(type_code), object_id, 0, 0x37]) + b"\xFF" * 24)
        record.extend(value_base.to_bytes(4, "little"))
        record.extend(b"\x00\x00\x7F\x00")
        record.extend(b"\x00\x00\x00\x00")
        record.extend(_coord_payload(block))
        event_offset = 0x145 if index == 0 else 0x16D + (index - 1) * 0x1A
        record.extend(event_offset.to_bytes(4, "little"))
        for item in seed.mirror_templates[type_code]:
            value = 0xFFFF if item is None else slot_start + item
            record.extend(value.to_bytes(2, "little"))
        if len(record) != 0x8A:
            raise TftToolchainError(f"Internal mirror record length mismatch for {block.objname}")
        out.extend(record)
        slot_start += TYPE_USER_SLOT_COUNTS[type_code]
    return bytes(out)


def _refresh_tft_headers(
    payload: bytearray,
    *,
    model: str,
    model_series: int,
    object_start: int,
    object_count: int,
    attr_relative: int,
    user_relative: int,
    picture_relative: int,
) -> None:
    raw = bytearray(payload)
    if len(raw) < HEADER2_CRC_OFFSET + 4:
        raise TftToolchainError("TFT payload is too short for header refresh")

    raw[HEADER1_FILE_SIZE_OFFSET : HEADER1_FILE_SIZE_OFFSET + 4] = len(raw).to_bytes(4, "little")
    raw[HEADER1_CRC_OFFSET : HEADER1_CRC_OFFSET + 4] = _crc32_like(list(raw[:HEADER1_CRC_OFFSET])).to_bytes(4, "little")

    key = _header2_xor_key(model)
    _write_header2_field(raw, key, HEADER2_FIELD_OFFSETS["static_usercode_address"], attr_relative.to_bytes(4, "little"))
    _write_header2_field(raw, key, HEADER2_FIELD_OFFSETS["app_attributes_data_address"], attr_relative.to_bytes(4, "little"))
    _write_header2_field(raw, key, HEADER2_FIELD_OFFSETS["usercode_address"], user_relative.to_bytes(4, "little"))
    picture_absolute = object_start + picture_relative
    _write_header2_field(raw, key, HEADER2_FIELD_OFFSETS["pictures_address"], picture_absolute.to_bytes(4, "little"))
    _write_header2_field(raw, key, HEADER2_FIELD_OFFSETS["gmovs_address"], (picture_absolute + 0x10).to_bytes(4, "little"))
    _write_header2_field(raw, key, HEADER2_FIELD_OFFSETS["compiled_object_count"], object_count.to_bytes(2, "little"))
    raw[HEADER2_CRC_OFFSET : HEADER2_CRC_OFFSET + 4] = _crc32_like(list(raw[HEADER2_START:HEADER2_CRC_OFFSET])).to_bytes(4, "little")

    raw[:] = update_tft_checksum(bytes(raw), series=model_series)
    payload[:] = raw


def _header2_xor_key(model: str) -> bytes:
    module = _load_tfttool_module()
    key = int(module.TFTFile._modelXORs.get(model, 0))
    return key.to_bytes(4, "little") if key else b"\x00\x00\x00\x00"


def _write_header2_field(raw: bytearray, key: bytes, relative_offset: int, decoded: bytes) -> None:
    start = HEADER2_START + relative_offset
    for index, value in enumerate(decoded):
        raw[start + index] = value ^ key[(relative_offset + index) % 4]


def _code_block(data: bytes) -> bytes:
    return len(data).to_bytes(4, "little") + data


def _required_field_int(block: PageBlock, name: str) -> int:
    value = _field_int(block, name)
    if value is None:
        raise TftToolchainError(f"Missing integer field {name!r} in object {block.objname!r}")
    return value


def _coord_payload(block: PageBlock) -> bytes:
    values = []
    for name in COORD_FIELDS:
        value = _field_int(block, name)
        if value is None:
            raise TftToolchainError(f"Missing coordinate field {name} in {block.objname}")
        values.append(value)
    return b"".join(value.to_bytes(2, "little") for value in values)


def _replace_all(buf: memoryview, old: bytes, new: bytes) -> int:
    if len(old) != len(new):
        raise ValueError("replacement length must not change")
    data = buf.tobytes()
    count = 0
    start = 0
    while True:
        offset = data.find(old, start)
        if offset < 0:
            return count
        buf[offset : offset + len(old)] = new
        count += 1
        start = offset + len(old)


def _compiled_text_offset(block_reverse: dict[str, Any] | None) -> int | None:
    if not block_reverse:
        return None
    candidate = block_reverse.get("compiled_record_candidate")
    if not isinstance(candidate, dict):
        return None
    text_pointer = candidate.get("text_pointer_candidate")
    if not isinstance(text_pointer, dict):
        return None
    value = text_pointer.get("text_relative_offset")
    return int(value) if isinstance(value, int) else None


def _text_slot_len(block: PageBlock) -> int:
    txt_maxl = _field_int(block, "txt_maxl")
    if txt_maxl is not None:
        return txt_maxl + 2
    text = _field_text(block, "txt")
    return max(len(text.encode("ascii")) if text else 0, 1)


def _header(inspection: dict[str, Any], name: str) -> dict[str, Any]:
    parsed = inspection.get("parsed")
    if not isinstance(parsed, dict) or not isinstance(parsed.get(name), dict):
        raise TftToolchainError(f"Unable to inspect TFT {name}")
    return parsed[name]


def _header_int(header: dict[str, Any], key: str) -> int | None:
    value = header.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _field_int(block: PageBlock, name: str) -> int | None:
    field = block.get_field(name)
    if field is None or not (0 < len(field.value) <= 4):
        return None
    return int.from_bytes(field.value, "little")


def _field_text(block: PageBlock, name: str) -> str | None:
    field = block.get_field(name)
    if field is None:
        return None
    try:
        return field.value.decode("ascii")
    except UnicodeDecodeError:
        return field.value.decode("ascii", errors="replace")
