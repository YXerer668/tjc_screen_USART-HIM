from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

ENTRY_NAME_SIZE = 16
ENTRY_SIZE = 28
MIN_ASCII_RUN = 2
OBJECT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\d+$")
PAGE_NAME_RE = re.compile(r"^page\d+$")

KNOWN_PA_PROPERTIES = {
    "aph",
    "bco",
    "borderc",
    "borderw",
    "codesdown-0",
    "codesload-0",
    "codesloadend-0",
    "codesunload-0",
    "codesup-0",
    "drag",
    "down",
    "effect",
    "endx",
    "endy",
    "first",
    "font",
    "groupid0",
    "groupid1",
    "id",
    "isbr",
    "key",
    "left",
    "lockobj",
    "movex",
    "movey",
    "objname",
    "pco",
    "pic",
    "picc",
    "right",
    "sendkey",
    "spax",
    "spay",
    "sta",
    "style",
    "time",
    "type",
    "val",
    "vscope",
    "vvs0",
    "vvs1",
    "w",
    "x",
    "xcen",
    "y",
    "ycen",
}


class HMIParseError(ValueError):
    """Raised when an HMI container cannot be parsed safely."""


@dataclass(slots=True)
class HMIEntry:
    index: int
    dir_offset: int
    name: str
    name_hex: str
    data_offset: int
    length: int
    field3: int
    in_file: bool

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["dir_offset_hex"] = f"0x{self.dir_offset:X}"
        data["data_offset_hex"] = f"0x{self.data_offset:08X}"
        data["field3_hex"] = f"0x{self.field3:08X}"
        return data


@dataclass(slots=True)
class PAString:
    offset: int
    text: str

    def to_dict(self) -> dict[str, object]:
        return {"offset": self.offset, "offset_hex": f"0x{self.offset:X}", "text": self.text}


@dataclass(slots=True)
class HMIInspection:
    path: Path
    entry_count: int
    entries: list[HMIEntry]
    program_text: str | None
    pa_strings: list[PAString]
    page_names: list[str]
    object_names: list[str]
    property_names: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "entry_count": self.entry_count,
            "entries": [entry.to_dict() for entry in self.entries],
            "program_text": self.program_text,
            "pa_strings": [item.to_dict() for item in self.pa_strings],
            "page_names": self.page_names,
            "object_names": self.object_names,
            "property_names": self.property_names,
        }


def inspect_hmi(path: str | Path) -> HMIInspection:
    file_path = Path(path).resolve()
    raw = file_path.read_bytes()
    if len(raw) < 4:
        raise HMIParseError("File is too small to be a USART HMI container")

    entry_count = int.from_bytes(raw[0:4], "little")
    directory_end = 4 + (entry_count * ENTRY_SIZE)
    if entry_count <= 0 or directory_end > len(raw):
        raise HMIParseError("Unsupported or corrupt HMI directory layout")

    entries = _parse_entries(raw, entry_count)
    resources = {
        entry.name: raw[entry.data_offset : entry.data_offset + entry.length]
        for entry in entries
        if entry.in_file
    }

    program_text = None
    if "Program.s" in resources:
        program_text = _decode_text(resources["Program.s"])

    pa_strings: list[PAString] = []
    page_names: list[str] = []
    object_names: list[str] = []
    property_names: list[str] = []
    if "0.pa" in resources:
        pa_strings = _extract_ascii_runs(resources["0.pa"])
        page_names = sorted({item.text for item in pa_strings if PAGE_NAME_RE.match(item.text)})
        property_names = sorted({item.text for item in pa_strings if item.text in KNOWN_PA_PROPERTIES})
        object_names = sorted(
            {
                item.text
                for item in pa_strings
                if OBJECT_NAME_RE.match(item.text)
                and item.text not in KNOWN_PA_PROPERTIES
                and not PAGE_NAME_RE.match(item.text)
            }
        )

    return HMIInspection(
        path=file_path,
        entry_count=entry_count,
        entries=entries,
        program_text=program_text,
        pa_strings=pa_strings,
        page_names=page_names,
        object_names=object_names,
        property_names=property_names,
    )


def extract_hmi(path: str | Path, out_dir: str | Path) -> list[Path]:
    file_path = Path(path).resolve()
    output_dir = Path(out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = file_path.read_bytes()
    inspection = inspect_hmi(file_path)
    written: list[Path] = []
    seen_names: set[str] = set()

    for entry in inspection.entries:
        if not entry.in_file or entry.length == 0:
            continue
        name = _safe_file_name(entry.name or f"entry_{entry.index}.bin")
        if name in seen_names:
            stem, dot, suffix = name.partition(".")
            name = f"{stem}_{entry.index}"
            if dot:
                name = f"{name}.{suffix}"
        seen_names.add(name)

        target = output_dir / name
        target.write_bytes(raw[entry.data_offset : entry.data_offset + entry.length])
        written.append(target)

        if entry.name == "Program.s":
            utf8_target = output_dir / "Program_utf8.txt"
            utf8_target.write_text(_decode_text(target.read_bytes()), encoding="utf-8")
            written.append(utf8_target)

    return written


def _parse_entries(raw: bytes, entry_count: int) -> list[HMIEntry]:
    entries: list[HMIEntry] = []
    for index in range(entry_count):
        base = 4 + index * ENTRY_SIZE
        name_bytes = raw[base : base + ENTRY_NAME_SIZE]
        data_offset = int.from_bytes(raw[base + 16 : base + 20], "little")
        length = int.from_bytes(raw[base + 20 : base + 24], "little")
        field3 = int.from_bytes(raw[base + 24 : base + 28], "little")
        in_file = data_offset + length <= len(raw)
        entries.append(
            HMIEntry(
                index=index,
                dir_offset=base,
                name=_decode_name(name_bytes),
                name_hex=name_bytes.hex(" "),
                data_offset=data_offset,
                length=length,
                field3=field3,
                in_file=in_file,
            )
        )
    return entries


def _decode_name(name_bytes: bytes) -> str:
    chars = []
    for value in name_bytes:
        if value == 0:
            break
        chars.append(chr(value) if 32 <= value <= 126 else "_")
    return "".join(chars).strip("_")


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _extract_ascii_runs(data: bytes, min_length: int = MIN_ASCII_RUN) -> list[PAString]:
    runs: list[PAString] = []
    start = -1
    for index, value in enumerate(data):
        printable = 32 <= value <= 126 or value == 9
        if printable and start < 0:
            start = index
        if not printable and start >= 0:
            if index - start >= min_length:
                text = data[start:index].decode("ascii", errors="ignore")
                runs.append(PAString(offset=start, text=text))
            start = -1
    if start >= 0 and len(data) - start >= min_length:
        runs.append(PAString(offset=start, text=data[start:].decode("ascii", errors="ignore")))
    return runs


def _safe_file_name(name: str) -> str:
    safe_chars = []
    for char in name:
        if char.isalnum() or char in {".", "-", "_"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    safe = "".join(safe_chars).strip("_")
    return safe or "entry.bin"
