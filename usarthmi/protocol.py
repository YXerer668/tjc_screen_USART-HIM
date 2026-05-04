from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .transport import TERMINATOR

CONNECT_RE = re.compile(r"^comok\b", re.IGNORECASE)
PRINTABLE_ASCII_RE = re.compile(r"^[\x20-\x7e\t\r\n]+$")


class ProtocolError(ValueError):
    """Raised when a high-level command cannot be constructed."""


@dataclass(slots=True)
class ParsedResponse:
    kind: str
    raw: bytes
    hex: str
    ascii_preview: str | None = None
    value: Any | None = None
    code: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "kind": self.kind,
            "hex": self.hex,
            "ascii_preview": self.ascii_preview,
            "value": self.value,
            "code": self.code,
            "details": self.details,
        }
        return {key: value for key, value in payload.items() if value not in ({}, None)}


def build_raw(command: str) -> str:
    return command.strip()


def build_get(target: str) -> str:
    return f"get {target}"


def build_set(target: str, value: str) -> str:
    return f"{target}={value}"


def build_page(page_id: str) -> str:
    return f"page {page_id}"


def build_ref(obj: str) -> str:
    return f"ref {obj}"


def build_vis(obj: str, state: str) -> str:
    return f"vis {obj},{state}"


def build_tsw(obj: str, state: str) -> str:
    return f"tsw {obj},{state}"


def build_click(obj: str, event: str) -> str:
    normalized = event.strip().lower()
    if normalized in {"down", "press", "1"}:
        event_value = "1"
    elif normalized in {"up", "release", "0"}:
        event_value = "0"
    else:
        raise ProtocolError(f"Unsupported click event: {event}")
    return f"click {obj},{event_value}"


def build_dim(value: str) -> str:
    return build_set("dim", value)


def parse_response(data: bytes) -> ParsedResponse:
    hex_value = data.hex(" ")
    if not data:
        return ParsedResponse(kind="none", raw=data, hex=hex_value)

    stripped = data[:-3] if data.endswith(TERMINATOR) else data
    ascii_preview = _decode_ascii_preview(stripped)

    if stripped and CONNECT_RE.match(ascii_preview or ""):
        return ParsedResponse(
            kind="connect",
            raw=data,
            hex=hex_value,
            ascii_preview=ascii_preview,
            value=ascii_preview,
            details=parse_connect_payload(ascii_preview),
        )

    code = data[0]
    if code == 0x70 and len(data) >= 4:
        text = stripped[1:].decode("ascii", errors="replace")
        return ParsedResponse(
            kind="string",
            raw=data,
            hex=hex_value,
            ascii_preview=text,
            value=text,
            code=code,
        )

    if code == 0x71 and len(data) >= 8:
        value = int.from_bytes(data[1:5], "little", signed=False)
        return ParsedResponse(
            kind="number",
            raw=data,
            hex=hex_value,
            value=value,
            code=code,
        )

    if code == 0x66 and len(data) >= 5:
        page_id = data[1]
        return ParsedResponse(
            kind="page_id",
            raw=data,
            hex=hex_value,
            value=page_id,
            code=code,
        )

    if code == 0x1A:
        return ParsedResponse(
            kind="invalid_reference",
            raw=data,
            hex=hex_value,
            code=code,
            details={"message": "Invalid variable, object, or attribute"},
        )

    if ascii_preview and PRINTABLE_ASCII_RE.match(ascii_preview):
        return ParsedResponse(
            kind="ascii",
            raw=data,
            hex=hex_value,
            ascii_preview=ascii_preview,
            value=ascii_preview,
            code=code,
        )

    return ParsedResponse(
        kind="unknown",
        raw=data,
        hex=hex_value,
        ascii_preview=ascii_preview,
        code=code,
    )


def parse_connect_payload(text: str) -> dict[str, Any]:
    details: dict[str, Any] = {"text": text}
    if not CONNECT_RE.match(text):
        return details

    _, _, tail = text.partition(" ")
    fields = [part.strip() for part in tail.split(",") if part.strip()]
    details["status"] = "comok"
    details["fields"] = fields

    if len(fields) >= 1:
        details["mode"] = fields[0]
    if len(fields) >= 2:
        details["flash_descriptor"] = fields[1]
    if len(fields) >= 3:
        details["model"] = fields[2]
    if len(fields) >= 4:
        details["firmware"] = fields[3]
    if len(fields) >= 5:
        details["mcu_code"] = fields[4]
    if len(fields) >= 6:
        details["serial"] = fields[5]
    if len(fields) >= 7:
        details["feature_descriptor"] = fields[6]

    return details


def _decode_ascii_preview(data: bytes) -> str | None:
    if not data:
        return None
    try:
        preview = data.decode("ascii", errors="replace")
    except Exception:
        return None
    return preview
