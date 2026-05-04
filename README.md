# usarthmi

Experimental Python tooling for TJC / USART HMI serial screens.

This repository started from a live reverse-engineering session around a
`TJC8048X543_011C` 800x480 screen and the `USART HMI` editor. The practical
goal is to control the screen from the command line and progressively replace
the GUI-only workflow with scriptable HMI/TFT tooling.

## Current Capabilities

- Serial command CLI for `connect`, `sendme`, `get`, `set`, `page`, `ref`,
  `vis`, `tsw`, `click`, and `dim`.
- Lightweight `.HMI` inspection and extraction helpers.
- Scene JSON/YAML authoring helpers and PNG preview rendering.
- Runtime serial preview for simple scene layouts.
- Font subset generation helpers around the local ZiCli tool.
- TFT inspection/checksum helpers using a small vendored copy of TFTTool.
- Experimental same-layout TFT patching for text/coordinate changes.
- Experimental one-object-add TFT tail generation for the current seed layout:
  adding exactly one `t`, `b`, or `p` object can be compiled into a flashable
  TFT tail.

## What Is Not Included

Large or potentially proprietary artifacts are intentionally not committed:

- official `.HMI` / `.TFT` / `.zi` payloads
- extracted USART HMI editor binaries
- generated build directories
- local screenshots and serial upload logs
- third-party example HMI/TFT repositories used as research references

Some local tests are skipped automatically when those optional fixtures are not
present.

## Install

```powershell
python -m pip install -e .
```

Dependencies are declared in `pyproject.toml`.

## Serial Examples

```powershell
python -m usarthmi --json connect --port COM36 --baud 9600
python -m usarthmi --json sendme --port COM36 --baud 9600
python -m usarthmi --json get t0.txt --port COM36 --baud 9600
python -m usarthmi --json set t0.txt '"hello"' --port COM36 --baud 9600
python -m usarthmi --json dim 30 --port COM36 --baud 9600
```

## HMI / Scene Examples

```powershell
python -m usarthmi --json inspect-hmi path\to\lcd_test.HMI
python -m usarthmi --json extract-hmi path\to\lcd_test.HMI --out hmi_extract
python -m usarthmi --json scene validate examples\menu_demo\scene.json
python -m usarthmi --json scene preview examples\menu_demo\scene.json --out preview.png
```

## TFT Patch Examples

Same-layout patch:

```powershell
python -m usarthmi --json tft patch-basic `
  --baseline-tft path\to\baseline.tft `
  --baseline-pa path\to\baseline\0.pa `
  --target-pa path\to\target\0.pa `
  --out patched.tft
```

One added object, current seed layout only:

```powershell
python -m usarthmi --json tft patch-add-object `
  --baseline-tft path\to\baseline.tft `
  --baseline-pa path\to\baseline\0.pa `
  --target-pa path\to\target_with_one_added_object\0.pa `
  --out added_object.tft
```

Upload:

```powershell
python -m usarthmi --json tft upload `
  --file added_object.tft `
  --port COM36 `
  --baud 9600 `
  --download-baud 921600 `
  --progress
```

## Verification Status

The local development session verified:

- same-layout text patch `nihao -> buhao` was flashed and read back from a real
  `TJC8048X543_011C` panel.
- one added text object `t1` was flashed and queried successfully with
  `get t1.txt` and `get t1.x`.
- local test suite passed with the available fixtures.

See `USART_HMI_STATUS_2026-05-04.md` for the detailed working log.

## Limitations

The TFT writer is not a complete replacement for the official editor yet. The
current independent generation path is deliberately narrow and optimized for
the known 800x480 seed project. Arbitrary object names still need the recovered
object-name hash algorithm or additional recovered mappings.
