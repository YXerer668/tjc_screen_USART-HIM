from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

from . import __version__
from .editor import EditorError, build_scene, import_asset
from .font_toolchain import (
    FontToolchainError,
    collect_scene_text,
    ensure_zicli_built,
    generate_zi,
    generate_zi_from_scene,
    replace_hmi_font,
)
from .hmi_inspect import HMIParseError, extract_hmi, inspect_hmi
from .preview import render_scene_preview
from .protocol import (
    ProtocolError,
    build_click,
    build_dim,
    build_get,
    build_page,
    build_raw,
    build_ref,
    build_set,
    build_tsw,
    build_vis,
    parse_response,
)
from .runtime_preview import build_scene_runtime_commands, push_scene_runtime_preview
from .scene import SceneError, WidgetSpec, load_scene, save_scene_json
from .tft_download import plan_upload, upload_tft
from .tft_case_diff import compare_case_folder
from .tft_checksum import inspect_tft_checksum
from .tft_font_pack import TftFontPackError, inspect_tft_font_run, pack_tft_font_run
from .tft_patch import patch_added_object_tft, patch_basic_tft
from .tft_reverse import reverse_tft_tail
from .tft_toolchain import TftToolchainError, inspect_tft, list_supported_tft_models
from .transport import SerialConfig, SerialTransport, SerialTransportError


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 1

    try:
        if args.command in {
            "raw",
            "connect",
            "sendme",
            "get",
            "set",
            "page",
            "ref",
            "vis",
            "tsw",
            "click",
            "dim",
        }:
            result = _handle_serial_command(args)
        elif args.command == "inspect-hmi":
            result = _handle_inspect_hmi(args)
        elif args.command == "extract-hmi":
            result = _handle_extract_hmi(args)
        elif args.command == "scene":
            result = _handle_scene_command(args)
        elif args.command == "font":
            result = _handle_font_command(args)
        elif args.command == "hmi":
            result = _handle_hmi_command(args)
        elif args.command == "tft":
            result = _handle_tft_command(args)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except (
        ProtocolError,
        SerialTransportError,
        HMIParseError,
        FileNotFoundError,
        SceneError,
        EditorError,
        FontToolchainError,
        TftToolchainError,
        TftFontPackError,
    ) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}")
        return 2

    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human_result(args.command, result)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="usarthmi", description="USART HMI CLI")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose transport logs")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    serial_parent = argparse.ArgumentParser(add_help=False)
    serial_parent.add_argument("--port", required=True, help="Serial port, for example COM36")
    serial_parent.add_argument("--baud", type=int, default=9600, help="Serial baud rate")
    serial_parent.add_argument(
        "--timeout-ms", type=int, default=800, help="Read timeout in milliseconds"
    )

    raw_parser = subparsers.add_parser("raw", parents=[serial_parent], help="Send a raw command")
    raw_parser.add_argument("raw_command", help='Raw command text, for example "get dim"')

    subparsers.add_parser("connect", parents=[serial_parent], help="Send connect")
    subparsers.add_parser("sendme", parents=[serial_parent], help="Send sendme")

    get_parser = subparsers.add_parser("get", parents=[serial_parent], help="Read an attribute")
    get_parser.add_argument("target", help="Attribute path, for example page0.bco")

    set_parser = subparsers.add_parser("set", parents=[serial_parent], help="Write an attribute")
    set_parser.add_argument("target", help="Attribute path, for example page0.bco")
    set_parser.add_argument("value", help="Value to assign")

    page_parser = subparsers.add_parser("page", parents=[serial_parent], help="Switch page")
    page_parser.add_argument("page_id", help="Page id or page name")

    ref_parser = subparsers.add_parser("ref", parents=[serial_parent], help="Refresh object")
    ref_parser.add_argument("object_name", help="Object id/name")

    vis_parser = subparsers.add_parser("vis", parents=[serial_parent], help="Show/hide object")
    vis_parser.add_argument("object_name", help="Object id/name")
    vis_parser.add_argument("state", help="0 or 1")

    tsw_parser = subparsers.add_parser("tsw", parents=[serial_parent], help="Enable/disable touch")
    tsw_parser.add_argument("object_name", help="Object id/name")
    tsw_parser.add_argument("state", help="0 or 1")

    click_parser = subparsers.add_parser("click", parents=[serial_parent], help="Trigger click event")
    click_parser.add_argument("object_name", help="Object id/name")
    click_parser.add_argument("event", help="down/up or 1/0")

    dim_parser = subparsers.add_parser("dim", parents=[serial_parent], help="Set backlight")
    dim_parser.add_argument("value", help="Backlight value")

    inspect_parser = subparsers.add_parser("inspect-hmi", help="Inspect an HMI container")
    inspect_parser.add_argument("path", help="Path to .HMI file")

    extract_parser = subparsers.add_parser("extract-hmi", help="Extract HMI resources")
    extract_parser.add_argument("path", help="Path to .HMI file")
    extract_parser.add_argument("--out", required=True, help="Extraction directory")

    scene_parser = subparsers.add_parser("scene", help="Scene file operations")
    scene_sub = scene_parser.add_subparsers(dest="scene_command")
    scene_validate = scene_sub.add_parser("validate", help="Validate a scene JSON/YAML")
    scene_validate.add_argument("scene_path", help="Scene file path")
    scene_preview = scene_sub.add_parser("preview", help="Render a scene to a PNG preview")
    scene_preview.add_argument("scene_path", help="Scene JSON/YAML file")
    scene_preview.add_argument("--out", required=True, help="Preview PNG path")
    scene_preview.add_argument("--page", default="page0", help="Page id")
    scene_push = scene_sub.add_parser("push-preview", help="Push a runtime preview of a scene to the serial screen")
    scene_push.add_argument("scene_path", help="Scene JSON/YAML file")
    scene_push.add_argument("--port", required=True, help="Serial port, for example COM36")
    scene_push.add_argument("--baud", type=int, default=9600, help="Serial baud rate")
    scene_push.add_argument("--page", default="page0", help="Page id")
    scene_push.add_argument("--timeout-ms", type=int, default=800, help="Serial timeout in milliseconds")
    scene_push.add_argument("--delay-ms", type=int, default=70, help="Delay between drawing commands in milliseconds")
    scene_build = scene_sub.add_parser("build", help="Build a scene against a seed HMI")
    scene_build.add_argument("scene_path", help="Scene JSON/YAML file")
    scene_build.add_argument("--seed", required=True, help="Seed HMI file")
    scene_build.add_argument("--out", required=True, help="Output directory")

    hmi_parser = subparsers.add_parser("hmi", help="Scene authoring helpers")
    hmi_sub = hmi_parser.add_subparsers(dest="hmi_command")
    hmi_import = hmi_sub.add_parser("import-image", help="Normalize a PNG/JPG into build assets")
    hmi_import.add_argument("source", help="PNG/JPG file")
    hmi_import.add_argument("--out", required=True, help="Asset output directory")

    for name in ("add-text", "add-image", "add-button", "add-number"):
        patch_parser = hmi_sub.add_parser(name, help=f"Append a {name[4:]} widget to a scene file")
        patch_parser.add_argument("--scene", required=True, help="Scene JSON file to modify")
        patch_parser.add_argument("--page", default="page0", help="Target page id")
        patch_parser.add_argument("--id", required=True, help="Widget id")
        patch_parser.add_argument("--x", type=int, required=True, help="Widget x")
        patch_parser.add_argument("--y", type=int, required=True, help="Widget y")
        patch_parser.add_argument("--w", type=int, required=True, help="Widget width")
        patch_parser.add_argument("--h", type=int, required=True, help="Widget height")
        patch_parser.add_argument("--text", help="Widget text")
        patch_parser.add_argument("--value", type=int, help="Widget numeric value")
        patch_parser.add_argument("--asset", help="Asset key for image/button widgets")

    hmi_set_page = hmi_sub.add_parser("set-page", help="Update canvas metadata in a scene file")
    hmi_set_page.add_argument("--scene", required=True, help="Scene JSON/YAML file")
    hmi_set_page.add_argument("--background-color", type=int, help="Canvas background color")
    hmi_set_page.add_argument("--width", type=int, help="Canvas width")
    hmi_set_page.add_argument("--height", type=int, help="Canvas height")

    hmi_build = hmi_sub.add_parser("build", help="Build a scene file into an HMI artifact")
    hmi_build.add_argument("--scene", required=True, help="Scene JSON/YAML file")
    hmi_build.add_argument("--seed", required=True, help="Seed HMI")
    hmi_build.add_argument("--out", required=True, help="Output directory")

    font_parser = subparsers.add_parser("font", help="Font generation and HMI font replacement")
    font_sub = font_parser.add_subparsers(dest="font_command")
    font_build = font_sub.add_parser("build-zicli", help="Build the local ZiCli helper")
    font_gen = font_sub.add_parser("generate-zi", help="Generate a .zi font from text input")
    _add_font_generation_args(font_gen)
    font_scene = font_sub.add_parser("from-scene", help="Generate a .zi subset font from scene text")
    _add_font_generation_args(font_scene, include_scene=True)
    font_replace = font_sub.add_parser("replace-hmi", help="Replace an HMI font entry such as 0.zi")
    font_replace.add_argument("--hmi", required=True, help="Input HMI file")
    font_replace.add_argument("--zi", required=True, help="Replacement .zi file")
    font_replace.add_argument("--out", required=True, help="Output HMI file")
    font_replace.add_argument("--entry", default="0.zi", help="Entry name to replace")

    tft_parser = subparsers.add_parser("tft", help="TFT build operations")
    tft_sub = tft_parser.add_subparsers(dest="tft_command")
    tft_build = tft_sub.add_parser("build", help="Build scene artifacts including experimental TFT metadata")
    tft_build.add_argument("--scene", required=True, help="Scene JSON/YAML file")
    tft_build.add_argument("--seed", required=True, help="Seed HMI")
    tft_build.add_argument("--out", required=True, help="Output directory")
    tft_inspect = tft_sub.add_parser("inspect", help="Inspect an existing TFT file using the local TFTTool")
    tft_inspect.add_argument("--file", required=True, help="TFT file path")
    tft_reverse = tft_sub.add_parser("reverse-tail", help="Probe compiled TFT object data against a parsed HMI .pa page")
    tft_reverse.add_argument("--file", required=True, help="TFT file path")
    tft_reverse.add_argument("--hmi-pa", help="Extracted HMI page file such as 0.pa")
    tft_reverse.add_argument("--install-dir", help="USART HMI installation directory for static resource matching")
    tft_reverse.add_argument("--context-bytes", type=int, default=48, help="Hex context around every match")
    tft_models = tft_sub.add_parser("list-models", help="List TFT models known by the local TFTTool")
    tft_pack_fonts = tft_sub.add_parser("pack-fonts", help="Pack one or more .zi files into a TFT-style embedded font run")
    tft_pack_fonts.add_argument("--font", action="append", required=True, help="Input .zi file, repeatable")
    tft_pack_fonts.add_argument("--out", required=True, help="Output packed font-run binary")
    tft_inspect_font_run = tft_sub.add_parser("inspect-font-run", help="Inspect a packed TFT-style font run binary")
    tft_inspect_font_run.add_argument("--file", required=True, help="Packed font-run file path")
    tft_upload = tft_sub.add_parser("upload", help="Upload a .tft file to a screen over serial")
    tft_upload.add_argument("--file", required=True, help="TFT file path")
    tft_upload.add_argument("--port", required=True, help="Serial port")
    tft_upload.add_argument("--baud", type=int, default=9600, help="Current device baud")
    tft_upload.add_argument("--download-baud", type=int, default=115200, help="Forced download baud")
    tft_upload.add_argument("--chunk-size", type=int, default=4096, help="Chunk size in bytes")
    tft_upload.add_argument("--timeout-ms", type=int, default=3000, help="Ack timeout in milliseconds")
    tft_upload.add_argument("--address", type=int, default=0, help="Optional HMI address prefix, 0 disables")
    tft_upload.add_argument(
        "--prepare-delay-ms",
        type=int,
        default=2500,
        help="Send delay=<ms> before whmi-wri like the official downloader; 0 disables",
    )
    tft_upload.add_argument(
        "--prepare-wait-ms",
        type=int,
        default=1500,
        help="Wait after delay=<ms> before whmi-wri",
    )
    tft_upload.add_argument("--progress", action="store_true", help="Print upload progress to stderr")
    tft_plan = tft_sub.add_parser("plan-upload", help="Analyze TFT chunks before upload")
    tft_plan.add_argument("--file", required=True, help="TFT file path")
    tft_plan.add_argument("--baseline", help="Known-current TFT file for chunk comparison")
    tft_plan.add_argument("--chunk-size", type=int, default=4096, help="Chunk size in bytes")
    tft_plan.add_argument("--download-baud", type=int, default=921600, help="Baud used for timing estimate")
    tft_cases = tft_sub.add_parser("compare-cases", help="Compare official one-variable HMI/TFT reverse-engineering cases")
    tft_cases.add_argument("--case-root", required=True, help="Folder containing case_* subdirectories")
    tft_cases.add_argument("--out", required=True, help="Output directory for extracts and JSON reports")
    tft_cases.add_argument("--baseline-case", default="case_00_baseline", help="Baseline case directory name")
    tft_cases.add_argument("--install-dir", help="USART HMI installation directory for static resource matching")
    tft_cases.add_argument("--context-bytes", type=int, default=16, help="Hex context around reverse matches")
    tft_cases.add_argument("--diff-run-limit", type=int, default=64, help="Maximum diff runs stored per case")
    tft_patch = tft_sub.add_parser("patch-basic", help="Experimentally patch same-layout text/coordinate fields in a baseline TFT")
    tft_patch.add_argument("--baseline-tft", required=True, help="Official baseline TFT used as binary template")
    tft_patch.add_argument("--baseline-pa", required=True, help="Extracted baseline 0.pa")
    tft_patch.add_argument("--target-pa", required=True, help="Target extracted 0.pa with same object layout")
    tft_patch.add_argument("--out", required=True, help="Output experimental TFT")
    tft_patch.add_argument(
        "--checksum-mode",
        choices=("recompute", "keep", "zero"),
        default="recompute",
        help="How to handle the final 4-byte TFT checksum",
    )
    tft_patch_add = tft_sub.add_parser("patch-add-object", help="Experimentally rebuild a TFT tail after adding one object")
    tft_patch_add.add_argument("--baseline-tft", required=True, help="Official baseline TFT used as binary seed")
    tft_patch_add.add_argument("--baseline-pa", required=True, help="Extracted baseline 0.pa")
    tft_patch_add.add_argument("--target-pa", required=True, help="Target extracted 0.pa with exactly one added t/b/p object")
    tft_patch_add.add_argument("--out", required=True, help="Output experimental TFT")
    tft_checksum = tft_sub.add_parser("checksum", help="Verify the final 4-byte TFT checksum")
    tft_checksum.add_argument("--file", required=True, help="TFT file path")

    return parser


def _handle_serial_command(args: argparse.Namespace) -> dict[str, Any]:
    command_text = _build_command_text(args)
    config = SerialConfig(
        port=args.port,
        baud=args.baud,
        timeout_ms=args.timeout_ms,
        verbose=args.verbose,
    )
    payload, response = SerialTransport(config).transact(command_text)
    parsed = parse_response(response)
    return {
        "port": args.port,
        "baud": args.baud,
        "command": command_text,
        "sent_hex": payload.hex(" "),
        "response": parsed.to_dict(),
    }


def _handle_inspect_hmi(args: argparse.Namespace) -> dict[str, Any]:
    inspection = inspect_hmi(args.path)
    return inspection.to_dict()


def _handle_extract_hmi(args: argparse.Namespace) -> dict[str, Any]:
    written = extract_hmi(args.path, args.out)
    return {
        "path": str(Path(args.path).resolve()),
        "output_dir": str(Path(args.out).resolve()),
        "files": [str(item) for item in written],
    }


def _handle_scene_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.scene_command == "validate":
        scene = load_scene(args.scene_path)
        return {"scene_path": str(Path(args.scene_path).resolve()), "normalized": scene.to_dict()}
    if args.scene_command == "preview":
        scene = load_scene(args.scene_path)
        target = render_scene_preview(scene, args.out, page_id=args.page)
        return {
            "scene_path": str(Path(args.scene_path).resolve()),
            "page_id": args.page,
            "preview_png": str(target),
        }
    if args.scene_command == "push-preview":
        scene = load_scene(args.scene_path)
        result = push_scene_runtime_preview(
            scene,
            port=args.port,
            baud=args.baud,
            page_id=args.page,
            timeout_ms=args.timeout_ms,
            delay_ms=args.delay_ms,
        )
        return {
            "scene_path": str(Path(args.scene_path).resolve()),
            **result.to_dict(),
        }
    if args.scene_command == "build":
        scene = load_scene(args.scene_path)
        return build_scene(scene, args.seed, args.out)
    raise SceneError("Unsupported scene subcommand")


def _handle_hmi_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.hmi_command == "import-image":
        return import_asset(args.source, args.out)

    if args.hmi_command in {"add-text", "add-image", "add-button", "add-number"}:
        scene = load_scene(args.scene)
        page = next((item for item in scene.pages if item.id == args.page), None)
        if page is None:
            raise SceneError(f"Page '{args.page}' not found in scene")
        page.widgets.append(
            WidgetSpec(
                id=args.id,
                type=args.hmi_command.replace("add-", ""),
                x=args.x,
                y=args.y,
                w=args.w,
                h=args.h,
                text=args.text,
                value=args.value,
                resources={"asset": args.asset} if args.asset else {},
                style={},
                bindings={},
            )
        )
        save_scene_json(scene, args.scene)
        return {"scene_path": str(Path(args.scene).resolve()), "added_widget": {"id": args.id, "type": args.hmi_command.replace("add-", "")}}

    if args.hmi_command == "set-page":
        scene = load_scene(args.scene)
        if args.background_color is not None:
            scene.canvas["background_color"] = args.background_color
        if args.width is not None:
            scene.canvas["width"] = args.width
        if args.height is not None:
            scene.canvas["height"] = args.height
        save_scene_json(scene, args.scene)
        return {"scene_path": str(Path(args.scene).resolve()), "canvas": scene.canvas}

    if args.hmi_command == "build":
        scene = load_scene(args.scene)
        return build_scene(scene, args.seed, args.out)

    raise SceneError("Unsupported hmi subcommand")


def _handle_font_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.font_command == "build-zicli":
        path = ensure_zicli_built()
        return {"zicli": str(path)}

    if args.font_command == "generate-zi":
        return generate_zi(
            out_path=args.out,
            font_name=args.font_name,
            font_file=args.font_file,
            name=args.name,
            codepage=args.codepage,
            height=args.height,
            font_size=args.font_size,
            text=args.text,
            text_files=args.text_file,
            include_ascii=args.include_ascii,
            offset_x=args.offset_x,
            offset_y=args.offset_y,
        )

    if args.font_command == "from-scene":
        result = generate_zi_from_scene(
            args.scene,
            out_path=args.out,
            font_name=args.font_name,
            font_file=args.font_file,
            name=args.name,
            codepage=args.codepage,
            height=args.height,
            font_size=args.font_size,
            include_ascii=args.include_ascii,
            offset_x=args.offset_x,
            offset_y=args.offset_y,
        )
        result["scene_path"] = str(Path(args.scene).resolve())
        return result

    if args.font_command == "replace-hmi":
        return replace_hmi_font(args.hmi, args.zi, args.out, entry_name=args.entry)

    raise FontToolchainError("Unsupported font subcommand")


def _handle_tft_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.tft_command == "build":
        scene = load_scene(args.scene)
        result = build_scene(scene, args.seed, args.out)
        result["mode"] = "experimental_tft_stub"
        return result
    if args.tft_command == "inspect":
        return inspect_tft(args.file)
    if args.tft_command == "reverse-tail":
        return reverse_tft_tail(
            args.file,
            hmi_pa_path=args.hmi_pa,
            install_dir=args.install_dir,
            context_bytes=args.context_bytes,
        )
    if args.tft_command == "list-models":
        return {"models": list_supported_tft_models()}
    if args.tft_command == "pack-fonts":
        return pack_tft_font_run(args.font, out_path=args.out)
    if args.tft_command == "inspect-font-run":
        return inspect_tft_font_run(args.file)
    if args.tft_command == "upload":
        progress = _make_upload_progress() if args.progress else None
        return upload_tft(
            args.file,
            port=args.port,
            baud=args.baud,
            download_baud=args.download_baud,
            chunk_size=args.chunk_size,
            timeout_ms=args.timeout_ms,
            address=args.address,
            prepare_delay_ms=args.prepare_delay_ms,
            prepare_wait_ms=args.prepare_wait_ms,
            progress=progress,
        ).to_dict()
    if args.tft_command == "plan-upload":
        return plan_upload(
            args.file,
            baseline_path=args.baseline,
            chunk_size=args.chunk_size,
            download_baud=args.download_baud,
        ).to_dict()
    if args.tft_command == "compare-cases":
        return compare_case_folder(
            args.case_root,
            out_dir=args.out,
            baseline_case=args.baseline_case,
            install_dir=args.install_dir,
            context_bytes=args.context_bytes,
            diff_run_limit=args.diff_run_limit,
        )
    if args.tft_command == "patch-basic":
        return patch_basic_tft(
            args.baseline_tft,
            baseline_pa=args.baseline_pa,
            target_pa=args.target_pa,
            out_tft=args.out,
            checksum_mode=args.checksum_mode,
        ).to_dict()
    if args.tft_command == "patch-add-object":
        return patch_added_object_tft(
            args.baseline_tft,
            baseline_pa=args.baseline_pa,
            target_pa=args.target_pa,
            out_tft=args.out,
        ).to_dict()
    if args.tft_command == "checksum":
        return inspect_tft_checksum(args.file)
    raise SceneError("Unsupported tft subcommand")


def _make_upload_progress():
    last = {"t": 0.0}

    def progress(bytes_sent: int, total: int, chunks_sent: int) -> None:
        now = time.monotonic()
        if now - last["t"] < 1.0 and bytes_sent < total:
            return
        last["t"] = now
        ratio = (bytes_sent / total * 100.0) if total else 100.0
        print(
            f"upload {bytes_sent}/{total} bytes ({ratio:5.1f}%), chunks={chunks_sent}",
            file=sys.stderr,
            flush=True,
        )

    return progress


def _build_command_text(args: argparse.Namespace) -> str:
    if args.command == "raw":
        return build_raw(args.raw_command)
    if args.command == "connect":
        return "connect"
    if args.command == "sendme":
        return "sendme"
    if args.command == "get":
        return build_get(args.target)
    if args.command == "set":
        return build_set(args.target, args.value)
    if args.command == "page":
        return build_page(args.page_id)
    if args.command == "ref":
        return build_ref(args.object_name)
    if args.command == "vis":
        return build_vis(args.object_name, args.state)
    if args.command == "tsw":
        return build_tsw(args.object_name, args.state)
    if args.command == "click":
        return build_click(args.object_name, args.event)
    if args.command == "dim":
        return build_dim(args.value)
    raise ProtocolError(f"Unsupported command: {args.command}")


def _add_font_generation_args(parser: argparse.ArgumentParser, include_scene: bool = False) -> None:
    if include_scene:
        parser.add_argument("--scene", required=True, help="Scene JSON/YAML file")
    parser.add_argument("--out", required=True, help="Output .zi file")
    parser.add_argument("--font-name", help="Installed font family name")
    parser.add_argument("--font-file", help="Font file path such as simsun.ttc")
    parser.add_argument("--name", help="Stored .zi font name")
    parser.add_argument("--codepage", default="utf-8", help="ascii, gb2312, utf-8")
    parser.add_argument("--height", type=int, default=32, help="Glyph height in pixels")
    parser.add_argument("--font-size", type=float, help="Rendering font size in pixels")
    if not include_scene:
        parser.add_argument("--text", help="Inline text to include in the font subset")
        parser.add_argument("--text-file", action="append", help="Text file to include in the font subset")
    parser.add_argument("--include-ascii", dest="include_ascii", action="store_true", default=True, help="Include ASCII 32..126")
    parser.add_argument("--no-ascii", dest="include_ascii", action="store_false", help="Do not auto-include ASCII 32..126")
    parser.add_argument("--offset-x", type=float, default=0.0, help="Glyph x offset")
    parser.add_argument("--offset-y", type=float, default=0.0, help="Glyph y offset")


def _print_human_result(command_name: str, result: dict[str, Any]) -> None:
    if command_name in {
        "raw",
        "connect",
        "sendme",
        "get",
        "set",
        "page",
        "ref",
        "vis",
        "tsw",
        "click",
        "dim",
    }:
        print(f"Command: {result['command']}")
        print(f"Port: {result['port']} @ {result['baud']}")
        print(f"Sent: {result['sent_hex']}")
        response = result["response"]
        if not response:
            print("Response: none")
            return
        print(f"Response kind: {response.get('kind', 'none')}")
        if "value" in response:
            print(f"Value: {response['value']}")
        if "ascii_preview" in response:
            print(f"ASCII: {response['ascii_preview']}")
        print(f"HEX: {response.get('hex', '')}")
        details = response.get("details")
        if isinstance(details, dict) and details:
            print("Details:")
            for key, value in details.items():
                print(f"  {key}: {value}")
        return

    if command_name == "inspect-hmi":
        print(f"HMI: {result['path']}")
        print(f"Entries: {result['entry_count']}")
        print("Top-level entries:")
        for entry in result["entries"]:
            print(
                f"  [{entry['index']}] {entry['name'] or '<unnamed>'} "
                f"off={entry['data_offset_hex']} len={entry['length']} in_file={entry['in_file']}"
            )
        if result.get("program_text"):
            print("\nProgram.s:")
            print(result["program_text"])
        print("\nPage names:", ", ".join(result["page_names"]) or "(none)")
        print("Object names:", ", ".join(result["object_names"]) or "(none)")
        print("Property names:", ", ".join(result["property_names"]) or "(none)")
        print("0.pa strings:")
        for item in result["pa_strings"]:
            print(f"  {item['offset_hex']}: {item['text']}")
        return

    if command_name == "extract-hmi":
        print(f"Extracted {len(result['files'])} file(s) to {result['output_dir']}")
        for path in result["files"]:
            print(f"  {path}")
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))
