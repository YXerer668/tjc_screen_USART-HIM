from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

FIELD_MARKER_DEFAULT = 0x11
HEADER_SIZE = 0x38
EVENT_PREFIXES = (
    "codesdown-",
    "codesup-",
    "codesload-",
    "codesloadend-",
    "codesunload-",
)
KNOWN_FIELDS = {
    "type",
    "id",
    "objname",
    "vscope",
    "drag",
    "disup",
    "sendkey",
    "aph",
    "movex",
    "movey",
    "x",
    "y",
    "w",
    "h",
    "endx",
    "endy",
    "effect",
    "first",
    "time",
    "lockobj",
    "sta",
    "style",
    "borderc",
    "borderw",
    "font",
    "pic",
    "picc",
    "bco",
    "pic2",
    "picc2",
    "bco2",
    "pco",
    "pco2",
    "xcen",
    "ycen",
    "val",
    "txt",
    "txt_maxl",
    "isbr",
    "spax",
    "spay",
    "newtxt",
    "pw",
    "key",
    "up",
    "down",
    "left",
    "right",
    "groupid0",
    "groupid1",
    "vvs0",
    "vvs1",
}
FIELD_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


@dataclass(slots=True)
class BlockField:
    name: str
    value: bytes
    marker: int | None

    def clone(self) -> "BlockField":
        return BlockField(self.name, bytes(self.value), self.marker)


@dataclass(slots=True)
class PageBlock:
    attr_name: str
    attr_marker: int
    fields: list[BlockField]
    event_tokens: list[str]

    def clone(self) -> "PageBlock":
        return PageBlock(
            attr_name=self.attr_name,
            attr_marker=self.attr_marker,
            fields=[field.clone() for field in self.fields],
            event_tokens=list(self.event_tokens),
        )

    @property
    def type_code(self) -> str | None:
        field = self.get_field("type")
        if field is None or not field.value:
            return None
        return field.value.decode("ascii", errors="ignore")

    @property
    def objname(self) -> str | None:
        field = self.get_field("objname")
        if field is None:
            return None
        return field.value.decode("ascii", errors="ignore")

    def get_field(self, name: str) -> BlockField | None:
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def set_string(self, name: str, value: str, encoding: str = "ascii") -> None:
        encoded = value.encode(encoding, errors="ignore")
        field = self.get_field(name)
        if field is None:
            self._append_field(name, encoded, FIELD_MARKER_DEFAULT)
            return
        field.value = encoded

    def set_int(self, name: str, value: int, width: int | None = None, marker: int = 0x12) -> None:
        field = self.get_field(name)
        if field is None:
            size = width or 2
            self._append_field(name, int(value).to_bytes(size, "little", signed=False), marker)
            return
        size = width or max(1, len(field.value))
        field.value = int(value).to_bytes(size, "little", signed=False)
        if field.marker is None:
            field.marker = None

    def set_event(self, name_prefix: str, lines: list[str]) -> None:
        events = _parse_event_specs(self.event_tokens)
        replaced = False
        for index, (event_name, _) in enumerate(events):
            if event_name.startswith(name_prefix):
                events[index] = (f"{name_prefix}{len(lines)}", list(lines))
                replaced = True
                break
        if not replaced:
            events.append((f"{name_prefix}{len(lines)}", list(lines)))
        self.event_tokens = _build_event_tokens(events)

    def serialize(self) -> bytes:
        parts = [
            len(self.attr_name).to_bytes(4, "little"),
            self.attr_name.encode("ascii"),
            self.attr_marker.to_bytes(4, "little"),
        ]
        for field in self.fields:
            name_bytes = field.name.encode("ascii")
            if len(name_bytes) > 16:
                raise ValueError(f"Field name too long: {field.name}")
            parts.append(name_bytes.ljust(16, b"\x00"))
            parts.append(field.value)
            if field.marker is not None:
                parts.append(field.marker.to_bytes(4, "little"))

        for token in self.event_tokens:
            encoded = token.encode("ascii", errors="ignore")
            parts.append(len(encoded).to_bytes(4, "little"))
            parts.append(encoded)
        parts.append((0).to_bytes(4, "little"))
        return b"".join(parts)

    def _append_field(self, name: str, value: bytes, marker: int) -> None:
        if self.fields:
            last = self.fields[-1]
            if last.marker is None:
                last.marker = FIELD_MARKER_DEFAULT
        self.fields.append(BlockField(name=name, value=value, marker=None))


@dataclass(slots=True)
class PageFile:
    magic: int
    total_length: int
    object_count: int
    header_bytes: bytes
    page_name: str
    blocks: list[PageBlock]

    def serialize(self) -> bytes:
        block_bytes = [block.serialize() for block in self.blocks]
        table_size = len(block_bytes) * 12
        rel_offsets = []
        cursor = table_size
        for payload in block_bytes:
            rel_offsets.append((cursor, len(payload), 0))
            cursor += len(payload)

        header = bytearray(self.header_bytes[:HEADER_SIZE])
        header[0x04:0x08] = (HEADER_SIZE + table_size + sum(len(item) for item in block_bytes)).to_bytes(4, "little")
        header[0x0C:0x10] = len(block_bytes).to_bytes(4, "little")
        header[0x18:0x28] = self.page_name.encode("ascii")[:16].ljust(16, b"\x00")

        table = bytearray()
        for rel_offset, block_length, unknown in rel_offsets:
            table.extend(rel_offset.to_bytes(4, "little"))
            table.extend(block_length.to_bytes(4, "little"))
            table.extend(unknown.to_bytes(4, "little"))
        return bytes(header + table + b"".join(block_bytes))


def parse_page_data(data: bytes) -> PageFile:
    if len(data) < HEADER_SIZE:
        raise ValueError("Page data is too short")
    total_length = int.from_bytes(data[0x04:0x08], "little")
    object_count = int.from_bytes(data[0x0C:0x10], "little")
    page_name = data[0x18:0x28].split(b"\x00", 1)[0].decode("ascii", errors="ignore")
    blocks = []
    table_start = HEADER_SIZE
    for index in range(object_count):
        base = table_start + index * 12
        rel_offset = int.from_bytes(data[base : base + 4], "little")
        block_length = int.from_bytes(data[base + 4 : base + 8], "little")
        block_start = HEADER_SIZE + rel_offset
        block_end = block_start + block_length
        blocks.append(parse_block_bytes(data[block_start:block_end]))
    return PageFile(
        magic=int.from_bytes(data[0x00:0x04], "little"),
        total_length=total_length,
        object_count=object_count,
        header_bytes=data[:HEADER_SIZE],
        page_name=page_name,
        blocks=blocks,
    )


def parse_block_bytes(block: bytes) -> PageBlock:
    attr_len = int.from_bytes(block[:4], "little")
    attr_name = block[4 : 4 + attr_len].decode("ascii", errors="ignore")
    cursor = 4 + attr_len
    attr_marker = int.from_bytes(block[cursor : cursor + 4], "little")
    cursor += 4

    fields: list[BlockField] = []
    event_tokens: list[str] = []
    while cursor < len(block):
        field_name = _decode_field_name_chunk(block[cursor : cursor + 16])
        if field_name is None:
            raise ValueError(f"Unable to parse field name in block {attr_name!r} at offset {cursor}")

        value_start = cursor + 16
        candidate = _find_field_end(block, value_start)
        if candidate is None:
            raise ValueError(f"Unable to locate field boundary for {field_name!r} in block {attr_name!r}")

        end_kind, value_end, marker, events = candidate
        fields.append(BlockField(name=field_name, value=block[value_start:value_end], marker=marker))
        if end_kind == "event":
            event_tokens = events or []
            break
        cursor = value_end + 4

    return PageBlock(
        attr_name=attr_name,
        attr_marker=attr_marker,
        fields=fields,
        event_tokens=event_tokens,
    )


def load_page_file(path: str | Path) -> PageFile:
    return parse_page_data(Path(path).read_bytes())


def find_first_block(page: PageFile, type_code: str) -> PageBlock:
    for block in page.blocks:
        if block.type_code == type_code:
            return block
    raise KeyError(f"No block of type '{type_code}' found")


def find_block_by_objname(page: PageFile, objname: str) -> PageBlock:
    for block in page.blocks:
        if block.objname == objname:
            return block
    raise KeyError(f"No block named '{objname}' found")


def _decode_field_name_chunk(chunk: bytes) -> str | None:
    if len(chunk) < 16 or chunk[0] == 0:
        return None
    end = 16
    for index, value in enumerate(chunk):
        if value == 0:
            end = index
            if any(item != 0 for item in chunk[index:]):
                return None
            break
    try:
        text = chunk[:end].decode("ascii")
    except UnicodeDecodeError:
        return None
    if text in KNOWN_FIELDS or text.startswith(EVENT_PREFIXES):
        return text
    if FIELD_NAME_RE.match(text):
        return text
    return None


def _find_field_end(
    block: bytes,
    value_start: int,
) -> tuple[str, int, int | None, list[str] | None] | None:
    for value_end in range(value_start, len(block) + 1):
        events = _parse_event_section(block[value_end:])
        if events is not None:
            return ("event", value_end, None, events)

        if value_end + 4 <= len(block):
            marker = int.from_bytes(block[value_end : value_end + 4], "little")
            if marker <= 0x40:
                next_name = _decode_field_name_chunk(block[value_end + 4 : value_end + 20])
                if next_name is not None:
                    return ("marker", value_end, marker, None)
    return None


def _parse_event_section(data: bytes) -> list[str] | None:
    cursor = 0
    tokens: list[str] = []
    while cursor + 4 <= len(data):
        length = int.from_bytes(data[cursor : cursor + 4], "little")
        cursor += 4
        if length == 0:
            return tokens if cursor == len(data) else None
        if cursor + length > len(data):
            return None
        payload = data[cursor : cursor + length]
        if not _is_ascii_text(payload):
            return None
        tokens.append(payload.decode("ascii"))
        cursor += length
    return None


def _is_ascii_text(data: bytes) -> bool:
    return all((32 <= value <= 126) or value in {9, 10, 13} for value in data)


def _parse_event_specs(tokens: list[str]) -> list[tuple[str, list[str]]]:
    specs: list[tuple[str, list[str]]] = []
    cursor = 0
    while cursor < len(tokens):
        name = tokens[cursor]
        cursor += 1
        if not name.startswith(EVENT_PREFIXES):
            continue
        try:
            line_count = int(name.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            line_count = 0
        lines = tokens[cursor : cursor + line_count]
        cursor += line_count
        specs.append((name, lines))
    return specs


def _build_event_tokens(specs: list[tuple[str, list[str]]]) -> list[str]:
    tokens: list[str] = []
    for name, lines in specs:
        tokens.append(name)
        tokens.extend(lines)
    return tokens
