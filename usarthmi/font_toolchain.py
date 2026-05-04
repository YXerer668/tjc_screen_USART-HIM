from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

from .hmi_inspect import HMIEntry, inspect_hmi
from .scene import SceneModel, WidgetSpec, load_scene


class FontToolchainError(RuntimeError):
    """Raised when local font generation or HMI font replacement fails."""


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MSBUILD_EXE = Path(r"C:\Program Files\Microsoft Visual Studio\18\Professional\MSBuild\Current\Bin\MSBuild.exe")
ZI_CLI_PROJECT = WORKSPACE_ROOT / "tools" / "ZiCli" / "ZiCli.csproj"
ZI_CLI_EXE = WORKSPACE_ROOT / "tools" / "ZiCli" / "bin" / "Release" / "ZiCli.exe"
ZI_LIB_PROJECT = WORKSPACE_ROOT / "external" / "nextion-font-editor" / "NextionFontEditor" / "ZiLib" / "ZiLib.csproj"


def ensure_zicli_built() -> Path:
    if ZI_CLI_EXE.exists() and not _needs_rebuild(ZI_CLI_EXE):
        return ZI_CLI_EXE
    if not MSBUILD_EXE.exists():
        raise FontToolchainError(f"MSBuild not found at {MSBUILD_EXE}")
    if not ZI_CLI_PROJECT.exists():
        raise FontToolchainError(f"ZiCli project not found at {ZI_CLI_PROJECT}")

    _run(
        [
            str(MSBUILD_EXE),
            str(ZI_LIB_PROJECT),
            "/p:Configuration=Release",
            "/nologo",
        ]
    )
    _run(
        [
            str(MSBUILD_EXE),
            str(ZI_CLI_PROJECT),
            "/p:Configuration=Release",
            "/nologo",
        ]
    )

    if not ZI_CLI_EXE.exists():
        raise FontToolchainError("ZiCli build completed without producing ZiCli.exe")
    return ZI_CLI_EXE


def generate_zi(
    *,
    out_path: str | Path,
    font_name: str | None = None,
    font_file: str | Path | None = None,
    name: str | None = None,
    codepage: str = "utf-8",
    height: int = 32,
    font_size: float | None = None,
    text: str | None = None,
    text_files: Iterable[str | Path] | None = None,
    include_ascii: bool = True,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> dict[str, object]:
    exe = ensure_zicli_built()
    output = Path(out_path).resolve()
    args = [
        str(exe),
        "generate",
        "--out",
        str(output),
        "--height",
        str(int(height)),
        "--font-size",
        str(float(font_size if font_size is not None else height)),
        "--codepage",
        codepage,
        "--offset-x",
        str(float(offset_x)),
        "--offset-y",
        str(float(offset_y)),
        "--include-ascii",
        "true" if include_ascii else "false",
    ]
    if font_name:
        args.extend(["--font-name", font_name])
    if font_file:
        args.extend(["--font-file", str(Path(font_file).resolve())])
    if name:
        args.extend(["--name", name])
    if text:
        args.extend(["--text", text])
    if text_files:
        for item in text_files:
            args.extend(["--text-file", str(Path(item).resolve())])

    stdout = _run(args)
    return {
        "tool": str(exe),
        "output": str(output),
        "stdout": stdout,
    }


def generate_zi_from_scene(
    scene_path: str | Path,
    *,
    out_path: str | Path,
    font_name: str | None = None,
    font_file: str | Path | None = None,
    name: str | None = None,
    codepage: str = "utf-8",
    height: int = 32,
    font_size: float | None = None,
    include_ascii: bool = True,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> dict[str, object]:
    scene = load_scene(scene_path)
    scene_text = collect_scene_text(scene)
    return generate_zi(
        out_path=out_path,
        font_name=font_name,
        font_file=font_file,
        name=name,
        codepage=codepage,
        height=height,
        font_size=font_size,
        text=scene_text,
        include_ascii=include_ascii,
        offset_x=offset_x,
        offset_y=offset_y,
    )


def collect_scene_text(scene: SceneModel) -> str:
    fragments: list[str] = []
    for page in scene.pages:
        for widget in page.widgets:
            _collect_widget_text(widget, fragments)
    return "".join(fragments)


def replace_hmi_font(
    seed_hmi: str | Path,
    zi_path: str | Path,
    out_hmi: str | Path,
    entry_name: str = "0.zi",
) -> dict[str, object]:
    seed = Path(seed_hmi).resolve()
    zi_file = Path(zi_path).resolve()
    output = Path(out_hmi).resolve()

    inspection = inspect_hmi(seed)
    entries = inspection.entries
    replacement = zi_file.read_bytes()
    rebuilt = _replace_hmi_entry(seed.read_bytes(), entries, entry_name, replacement)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rebuilt)
    return {
        "seed_hmi": str(seed),
        "zi_path": str(zi_file),
        "out_hmi": str(output),
        "entry_name": entry_name,
        "zi_size": len(replacement),
    }


def _collect_widget_text(widget: WidgetSpec, fragments: list[str]) -> None:
    if widget.text:
        fragments.append(widget.text)
    for child in widget.children:
        _collect_widget_text(child, fragments)


def _replace_hmi_entry(seed_bytes: bytes, entries: list[HMIEntry], target_name: str, replacement: bytes) -> bytes:
    target = next((entry for entry in entries if entry.name == target_name), None)
    if target is None:
        raise FontToolchainError(f"Entry '{target_name}' not found in HMI")

    result = bytearray(seed_bytes)
    target_end = target.data_offset + target.length
    last_end = max(entry.data_offset + entry.length for entry in entries)
    if target_end == last_end:
        result[target.data_offset:target_end] = replacement
        new_offset = target.data_offset
    else:
        new_offset = len(result)
        result.extend(replacement)

    base = target.dir_offset
    result[base + 16 : base + 20] = int(new_offset).to_bytes(4, "little")
    result[base + 20 : base + 24] = len(replacement).to_bytes(4, "little")
    return bytes(result)


def _run(args: list[str]) -> str:
    completed = subprocess.run(
        args,
        cwd=str(WORKSPACE_ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise FontToolchainError(
            json.dumps(
                {
                    "cmd": args,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return completed.stdout


def _needs_rebuild(exe_path: Path) -> bool:
    exe_mtime = exe_path.stat().st_mtime
    sources = [
        ZI_CLI_PROJECT,
        WORKSPACE_ROOT / "tools" / "ZiCli" / "Program.cs",
        ZI_LIB_PROJECT,
    ]
    sources.extend((WORKSPACE_ROOT / "external" / "nextion-font-editor" / "NextionFontEditor" / "ZiLib").rglob("*.cs"))
    return any(path.exists() and path.stat().st_mtime > exe_mtime for path in sources)
