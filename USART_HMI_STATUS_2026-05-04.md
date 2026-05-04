# USART HMI Status 2026-05-04

## Scope

This note records the current state of the local `usarthmi` toolchain, verified artifacts, and the exact gap that still blocks a true `scene -> TFT -> flash` workflow for the `TJC8048X543_011C` screen on `COM36`.

## Verified Working Pieces

### Serial runtime control

- `COM36 @ 9600` is the active screen link.
- Runtime drawing works on the real screen.
- The following have been visually verified on hardware:
  - page background color changes
  - temporary runtime button previews
  - scene-driven runtime preview push

### Scene authoring and preview

- Scene validation works for both JSON and YAML.
- Scene layout resolution works for:
  - `absolute`
  - `row`
  - `column`
  - `grid`
  - `stack`
  - `anchor`
- Local PNG preview rendering works.
- Current preview entrypoint:

```powershell
python -m usarthmi scene preview examples\menu_demo\scene.json --out .\preview_menu_demo.png
```

### HMI page rewriting

- The seed HMI container can be parsed safely.
- `0.pa` round-trips exactly for the current seed page.
- Rebuilt `.HMI` files preserve the original seed container addressing style.
- Scene build emits:
  - `output.hmi`
  - `preview.png`
  - `scene.normalized.json`
  - `manifest.json`

### Font toolchain

- The local `ZiLib` library is built successfully against `.NET Framework 4.8`.
- The local helper [ZiCli.exe](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/tools/ZiCli/bin/Release/ZiCli.exe>) is built and runnable.
- Existing seed font [0.zi](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/hmi_extract_v1/0.zi>) can be inspected.
- New `.zi` subset fonts can be generated from:
  - explicit text files
  - scene text
- `0.zi` replacement inside `.HMI` works.
- Multiple `.zi` files can now be packed into a TFT-style embedded font run.

## Important Artifacts

### Scene / HMI

- Seed HMI: [lcd_test.HMI](</D:/MySTM32/H723ZGT6/Program/ISP_Test/lcd_test.HMI>)
- Example scene preview: [preview_menu_demo.png](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/preview_menu_demo.png>)
- Current built scene HMI: [output.hmi](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/build_menu_demo_v3/output.hmi>)
- Current built scene HMI with replaced font: [output_font.hmi](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/build_menu_demo_v3/output_font.hmi>)
- Build manifest: [manifest.json](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/build_menu_demo_v3/manifest.json>)

### Fonts

- Extracted seed font: [0.zi](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/hmi_extract_v1/0.zi>)
- Demo generated subset font: [build_font_demo.zi](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/build_font_demo.zi>)
- Scene-derived subset font: [build_font_scene.zi](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/build_font_scene.zi>)
- Packed TFT-style font run: [build_tft_font_run.bin](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/build_tft_font_run.bin>)
- Demo text source for font generation: [zi_chars_demo.txt](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/tools/zi_chars_demo.txt>)

### Local tooling

- Font helper executable: [ZiCli.exe](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/tools/ZiCli/bin/Release/ZiCli.exe>)
- Font helper source: [Program.cs](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/tools/ZiCli/Program.cs>)
- Python font integration: [font_toolchain.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/usarthmi/font_toolchain.py>)
- Python TFT uploader: [tft_download.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/usarthmi/tft_download.py>)
- Python TFT inspector: [tft_toolchain.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/usarthmi/tft_toolchain.py>)
- Python TFT font packer: [tft_font_pack.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/usarthmi/tft_font_pack.py>)
- Reference parsed TFT sample: [tft_reference_nextion43_18may.json](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/tft_reference_nextion43_18may.json>)
- Experimental forced-conversion TFT, not flashed: [build_experimental_hsv_to_tjc8048x543.tft](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/build_experimental_hsv_to_tjc8048x543.tft>)
- Official compiled target TFT, flashed and verified: [official_lcd_test_TJC8048X543_011_20260504.tft](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/official_lcd_test_TJC8048X543_011_20260504.tft>)
- Official target TFT inspection: [official_lcd_test_TJC8048X543_011_20260504.inspect.json](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/official_lcd_test_TJC8048X543_011_20260504.inspect.json>)
- Extracted `USART HMI.exe` embedded PE files: [embedded_pe](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/embedded_pe>)
- XOR-decoded `ACTR.dll` container: [ACTR_xor09.bin](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/ACTR_xor09.bin>)
- Extracted `ACTR.dll` entries: [actr_entries](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/actr_entries>)

## Commands That Work Now

### Build local font helper

```powershell
python -m usarthmi font build-zicli
```

### Generate `.zi` from scene text

```powershell
python -m usarthmi font from-scene `
  --scene examples\menu_demo\scene.json `
  --out .\build_font_scene.zi `
  --font-file C:\Windows\Fonts\simsun.ttc `
  --name SimSun32scene `
  --height 32 `
  --font-size 32
```

### Replace `0.zi` in an HMI file

```powershell
python -m usarthmi font replace-hmi `
  --hmi .\build_menu_demo_v3\output.hmi `
  --zi .\build_font_scene.zi `
  --out .\build_menu_demo_v3\output_font.hmi
```

### Push a runtime scene preview to the real screen

```powershell
python -m usarthmi scene push-preview examples\menu_demo\scene.json --port COM36 --baud 9600 --page page0
```

### Inspect an existing TFT file

```powershell
python -m usarthmi --json tft inspect --file .\github_refs\Gaggiuino_35\Nextion_43\Nextion_43_18MAY2024_0_Deg.tft
```

### Upload the official compiled target TFT

```powershell
python -m usarthmi --json tft upload `
  --file .\official_lcd_test_TJC8048X543_011_20260504.tft `
  --port COM36 `
  --baud 9600 `
  --download-baud 921600 `
  --timeout-ms 8000
```

The uploader now mirrors the official open-source `TFTFileDownload` preparation sequence by default:

- sends `delay=2500`
- waits `1500ms`
- sends an empty command
- sends `whmi-wri filesize,baud,0`
- streams 4096-byte chunks and waits for `0x05` after each chunk

Use `--progress` to print progress to stderr. Use `--prepare-delay-ms 0` to disable the `delay=2500` preparation step.

### Analyze TFT upload chunks

```powershell
python -m usarthmi --json tft plan-upload `
  --file .\official_lcd_test_TJC8048X543_011_20260504.tft `
  --baseline .\official_lcd_test_TJC8048X543_011_20260504.tft `
  --download-baud 921600
```

For the known-good official TFT:

- file size: `11408156`
- upload chunks: `2786`
- theoretical serial-only minimum at `921600 8N1`: about `123.786s`
- all-`FF` chunks: `31`
- all-zero chunks: `16`
- comparing the file against itself reports `2786/2786` identical chunks

### Pack `.zi` files into a TFT-style font run

```powershell
python -m usarthmi --json tft pack-fonts `
  --font .\build_font_demo.zi `
  --font .\build_font_scene.zi `
  --out .\build_tft_font_run.bin
```

## What Is Not Finished Yet

- There is still no real `.tft` compiler in `usarthmi`.
- The serial upload command has now been exercised successfully with a known-good official `.tft` for this exact screen.
- The generated `.HMI` files are not yet equivalent to a fully official `USART HMI` build product.
- Static image resource packing into final `.HMI/.TFT` is still incomplete.
- The official `.tft` generated by `USART HMI` has been flashed and should persist after power cycle; what is still missing is a self-generated `.tft` from the `usarthmi` toolchain.
- The local `TFTTool` model database contains `TJC8048X543_011`, but the real screen handshake reports `TJC8048X543_011C`, so the suffix difference still needs to be explained or normalized before a fully confident generator/patcher path exists.
- Current `TFT` progress is strongest on the font segment; page/object/picture/resource sections are still not emitted by our own builder.
- A forced-converted same-resolution sample TFT was generated from `HSV Test.tft` to target `TJC8048X543_011`, but it was not flashed because the source content still reports `model_series=0` (T0), while `TJC8048X543` is X5 (`model_series=3`). It is useful as a header/checksum experiment, not as a safe screen payload.

## New Reverse Engineering Notes

- `ACTR.dll` is not a normal PE file. XORing the whole file with `0x09` reveals a 64-byte-record container.
- The decoded container includes these core entries:
  - `HMIFORM.dll`
  - `TFTEDIT.dll`
  - `TFTRUN.dll`
  - `Tcode.dll`
  - `hmitype.dll`
- The bundled `AppDllPass.dll` was extracted from `USART HMI.exe` and exports:
  - `AppDllPass_Decode`
  - `AppDllPass_Encode`
- Applying `AppDllPass_Decode` directly to the extracted entries does not yet produce normal PE headers, so there is at least one more loader/decode step.
- The real panel reports `mcu_code=10501` in `connect`.
- Official install file `3.cc` starts with little-endian code `10501`, and its payload size field matches `len(file)-8`. This strongly indicates `3.cc` is the matching static MCU/code block for the current panel family.
- The official wiki now provides `TFTFileDownload` binaries and C# source. Downloaded copies are kept locally:
  - [TFTFileDownload_0.zip](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/external/TFTFileDownload_0.zip>)
  - [TFTFileDownload_1.zip](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/external/TFTFileDownload_1.zip>)
  - [MainFrame.cs](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/external/TFTFileDownload_source/TFTFileDownLoad/TFTFileDownload/MainFrame.cs>)
- The open-source `TFTFileDownload` implementation does not contain a sparse/incremental protocol. It uses the same public protocol:
  - optional scan/connect
  - `delay=2500`
  - empty command
  - `whmi-wri filesize,baud,0`
  - 4096-byte chunks
  - wait for single-byte `0x05` after command and each chunk
- The public wiki page [HMI download protocol](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/hmi_download_protocol.html>) also documents only full-stream `whmi-wri`.
- Therefore the official editor's "same part not downloaded/written" behavior is not exposed by the public TFT downloader source. It is likely either:
  - inside the closed `USART HMI` editor download path, or
  - inside the screen bootloader/flash layer as "receive full stream but skip flash erase/write for unchanged blocks".

## Flash Verification 2026-05-04

- Official output path supplied by user:
  - `C:\Users\SinYu\AppData\Roaming\USART HMI\work\a-20265415630280\output\lcd_test.tft`
- The official TFT inspected as:
  - `model=TJC8048X543_011`
  - `model_series=3`
  - `lcd_resolution_x=800`
  - `lcd_resolution_y=480`
  - `editor_version=tjc-1.67.6`
  - `file_size=11408156`
- The file was uploaded successfully over `COM36`:
  - initial baud: `9600`
  - download baud: `921600`
  - chunks sent: `2786`
- Post-flash serial verification passed:
  - `connect` returned `TJC8048X543_011C`
  - `sendme` returned page `0`
  - `get dim` returned `100`
  - `get t0.txt` returned `nihao`
  - `get b0.txt` returned `ceshi`
  - `get p0.pic` returned `0`

## TFT Object Tail Reverse Probe 2026-05-04

- Added a repeatable CLI probe:
  - `python -m usarthmi --json tft reverse-tail --file official_lcd_test_TJC8048X543_011_20260504.tft --hmi-pa hmi_extract_current\0.pa --context-bytes 32`
- The current evidence JSON is saved at:
  - [official_lcd_test_tft_tail_reverse.json](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/official_lcd_test_tft_tail_reverse.json>)
- The official TFT object region is:
  - start `0xAE0000`
  - end `0xAE10DE`
  - size `0x10DE`
- The parsed `.HMI` `0.pa` objects align uniquely with the compiled TFT object records:
  - `page0`: header `0xAE01EB`, body `0xAE0207`, coords `0xAE0213`, value offset `0x20`, record length `0x40`
  - `t0`: header `0xAE022B`, body `0xAE0247`, coords `0xAE0253`, value offset `0x60`, record length `0x54`, text `nihao` at `0xAE0313`
  - `b0`: header `0xAE027F`, body `0xAE029B`, coords `0xAE02A7`, value offset `0xB4`, record length `0x54`, text `ceshi` at `0xAE031F`
  - `p0`: header `0xAE02D3`, body `0xAE02EF`, coords `0xAE02FB`, value offset `0x108`, record length `0x40`
- In each object record:
  - `coord_offset - 0x0C` is the body start.
  - `body_start - 0x1C` is the object header.
  - header byte 0 matches the HMI object type (`y/t/b/p`).
  - header byte 1 matches the HMI object id.
  - body dword 0 matches the compiled object value offset.
- A u32 value-offset table matching all four body dword-0 values exists at `0xAE01DB`:
  - `0x20, 0x60, 0xB4, 0x108`
- Text objects currently share a compiled text-pointer bias:
  - bias `0x1CB`
  - `t0` body `+0x2C` stores pointer `0x148`; `0x148 + 0x1CB = 0x313`, which is `nihao`
  - `b0` body `+0x30` stores pointer `0x154`; `0x154 + 0x1CB = 0x31F`, which is `ceshi`
- Resource matching from the extracted `.HMI` directory shows:
  - `0.i` is embedded byte-for-byte in the official TFT at `0x80F14`
  - `0.zi` is embedded byte-for-byte in the official TFT at `0x81BD6`
  - `Program.s`, `0.pa`, and `0.is` are not embedded as raw files
- Static resource matching from the installed `USART HMI` directory shows:
  - `input.bin` is embedded byte-for-byte at `0x20090`
  - `3.cc` is embedded byte-for-byte at `0x24532`
  - `cdx.dll` is embedded byte-for-byte at `0x7F4DA`
- These sections are contiguous:
  - `0x20000..0x20090`: 0x90-byte resource directory/header
  - `0x20090..0x24532`: `input.bin`
  - `0x24532..0x7F4DA`: `3.cc`
  - `0x7F4DA..0x80F14`: `cdx.dll`
  - `0x80F14..0x81BD6`: HMI `0.i`
  - `0x81BD6..0xACF82A`: HMI `0.zi`
  - `0xACF82A..0xAE0000`: zero padding/alignment before the object tail
- The 0x90-byte resource directory stores relative offsets from `0x20000`:
  - word 0/1: `input.bin` offset `0x90`, size `0x44A2`
  - word 3/4: `3.cc` offset `0x4532`, size `0x5AFA8`
  - word 6/7: `cdx.dll` offset `0x5F4DA`, size `0x1A3A`
  - word 21/22: `0.i` offset `0x60F14`, size `0xCC2`
  - word 24/25: `0.zi` offset `0x61BD6`, size `0xA4DC54`
- This means first-pass picture and font transfer can likely reuse the HMI resource blobs directly, while page/object data must be compiled into the object tail format.
- This is now the strongest known path toward a TFT writer/patcher: generate or patch the object tail from `.pa` semantics, then handle picture/font/resource tables separately.

## Case Diff Reverse Probe 2026-05-04

- User-provided one-variable official compiler samples are stored under:
  - `C:\Users\SinYu\Desktop\case_for_codex`
- Added a repeatable comparison CLI:
  - `python -m usarthmi --json tft compare-cases --case-root "C:\Users\SinYu\Desktop\case_for_codex" --out reverse_usarthmi\case_compare --install-dir "C:\Program Files (x86)\USART HMI"`
- The summary is saved at:
  - [summary.json](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/case_compare/summary.json>)
- `case_01_t0_text_hello`:
  - same file size as baseline
  - changes only `0xAE0313..` string pool text plus the final 4-byte word
- `case_02_t0_x_plus10`:
  - same file size as baseline
  - changes `t0` primary coordinates at relative `0x253`
  - also changes mirrored/render coordinates at relative `0x11A0`
  - changes the final 4-byte word
- `case_03_b0_text_test`:
  - same file size as baseline
  - changes `b0` string pool text plus the final 4-byte word
- The compiled tail must be considered `unknown_objects_address..EOF`, not only `unknown_objects_address..pictures_address` from TFTTool:
  - baseline tail size `0x131C`, while TFTTool `pictures_address` cuts at `0x10DE`
  - the post-`pictures_address` section contains mirrored coordinates/render metadata and the final 4-byte word
- Coordinate matches are now two-per-object:
  - baseline `page0`: `0x213`, `0x1116`
  - baseline `t0`: `0x253`, `0x11A0`
  - baseline `b0`: `0x2A7`, `0x122A`
  - baseline `p0`: `0x2FB`, `0x12B4`
- Adding one object changes the value-offset table:
  - 4-object baseline: `0x20, 0x60, 0xB4, 0x108`
  - 5-object cases: `0x24, 0x64, 0xB8, 0x10C, 0x148`
- Adding duplicate text does not deduplicate the string pool:
  - `case_04_add_text` stores `nihao`, `ceshi`, `nihao`
  - `case_05_add_button` stores `nihao`, `ceshi`, `ceshi`
- Text pointer bias remains stable in 5-object cases:
  - bias `0x1EB`
  - `t0` pointer body `+0x2C`
  - `b0/b1` pointer body `+0x30`
- Final 4-byte checksum is now decoded:
  - implemented in [tft_checksum.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/usarthmi/tft_checksum.py>)
  - X5 / model series 3 uses the TFTTool word-based CRC variant
  - the checksum is then XORed with bytes `0x03`, `0x2E`, and `0x3C` from the TFT header/body
  - verified against all 7 user-provided official TFT samples

## Experimental TFT Writer V0 2026-05-04

- Added a conservative same-layout TFT patcher:
  - [tft_patch.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/usarthmi/tft_patch.py>)
  - CLI: `python -m usarthmi --json tft patch-basic --baseline-tft <official-baseline.tft> --baseline-pa <baseline-0.pa> --target-pa <target-0.pa> --out <candidate.tft>`
- Current V0 scope:
  - object count/type/order must be unchanged
  - patches all matching coordinate sequences in the compiled tail
  - patches fixed-size text slots using `txt_maxl + 2` bytes
  - recomputes the final 4-byte TFT checksum by default
- Validation against user-provided official cases:
  - `case_01_t0_text_hello`: generated TFT equals official target byte-for-byte
  - `case_02_t0_x_plus10`: generated TFT equals official target byte-for-byte
  - `case_03_b0_text_test`: generated TFT equals official target byte-for-byte
- Added regression test:
  - [test_tft_patch.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/tests/test_tft_patch.py>)
- This proves the currently reversed fields are sufficient to generate real same-layout TFT content. The next blocker is no longer checksum; it is generating new-object tails rather than only patching same-layout files.

## Live Flash Verification: nihao -> buhao 2026-05-04

- Built a same-layout patched target:
  - target `.pa`: [0_buhao.pa](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/live_buhao_patch/0_buhao.pa>)
  - generated `.tft`: [lcd_test_buhao.tft](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/live_buhao_patch/lcd_test_buhao.tft>)
- Patch summary:
  - file size `11408156`
  - changed `t0.txt` from `nihao` to `buhao`
  - checksum recomputed to `0x7F034D2F`
  - compared with baseline: only string bytes and final checksum differ
- Uploaded to the real screen:
  - port `COM36`
  - initial baud `9600`
  - download baud `921600`
  - bytes sent `11408156`
  - chunks sent `2786`
  - elapsed `207.359s`
- Post-flash serial verification:
  - `connect` returned `TJC8048X543_011C`
  - `sendme` returned page `0`
  - `get t0.txt` returned `buhao`
  - `get dim` returned `100`
- This is the first confirmed live-screen proof that a non-official `usarthmi` generated TFT patch can be flashed and run.

## Milestone: First Non-Official TFT Patch Accepted By Screen

- Status: achieved.
- Scope proven:
  - parse official baseline HMI/TFT
  - modify page text through a generated target `0.pa`
  - patch compiled TFT text slots
  - recompute final TFT checksum
  - upload through public `whmi-wri`
  - verify runtime state over serial
- Practical meaning:
  - `usarthmi` can now generate a valid same-layout TFT patch without calling the official GUI compiler.
  - Same-layout edits such as text and coordinates are no longer only theoretical reverse-engineering results; they have been accepted by the real `TJC8048X543_011C` panel.

## Next Target: Full New-Object Object Tail Generation

- New blocker:
  - Generate the complete compiled object tail for added widgets instead of only patching existing same-layout objects.
- Immediate fixtures:
  - `case_04_add_text`
  - `case_05_add_button`
  - `case_06_add_picture`
- Required object-tail pieces to synthesize:
  - event token area growth for the extra object
  - object count and offset table changes
  - primary object records for `t1/b1/p1`
  - string pool growth with duplicate text preserved
  - value-offset table update
  - mirrored/render metadata section after TFTTool `pictures_address`
  - final TFT checksum recomputation
- Target acceptance for the next phase:
  - Generate `case_04_add_text`, `case_05_add_button`, and `case_06_add_picture` from baseline plus target `.pa`.
  - Match the official TFT outputs byte-for-byte.
  - Then flash one added-object TFT to the real screen and verify over serial.

## Current Gap

The remaining blocker is not runtime serial drawing, not font generation, and not `0.zi` replacement.

The blocker is:

`scene/HMI/font state` can be created locally, but it still cannot be compiled into a final `TFT` payload that is known-good for `TJC8048X543_011C`, then flashed and verified on the real panel.

## Recommended Next Step

Continue reverse engineering toward one of these:

1. Build a real `TFT` emitter inside `usarthmi`.
2. Or derive a reusable bridge from a known-good official `.tft` layout and patch it safely.

Until that step is complete, all screen changes remain either:
- runtime-only, or
- local `.HMI` source artifacts not yet proven as flashable screen firmware.

## Milestone: One-Object Add TFT Tail Generation 2026-05-04

- Status: achieved for the current seed and one added `t/b/p` object.
- Implemented:
  - [tft_patch.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/usarthmi/tft_patch.py>)
  - [cli.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/usarthmi/cli.py>)
  - [test_tft_patch.py](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/tests/test_tft_patch.py>)
- New CLI:
  - `python -m usarthmi --json tft patch-add-object --baseline-tft <baseline.tft> --baseline-pa <baseline 0.pa> --target-pa <target 0.pa> --out <out.tft>`
- Proven byte-for-byte against official fixtures:
  - `case_04_add_text`
  - `case_05_add_button`
  - `case_06_add_picture`
- Reverse facts now encoded:
  - event token area grows by one extra down/up event block sequence
  - object hash/index list is regenerated and sorted by recovered object hash
  - primary object block is rebuilt with value-offset table, records, text pointers, and duplicate text slots
  - `attr/usercode` section is rebuilt as `0x24` header plus per-object 24-byte property records
  - mirror section is rebuilt as 16-byte header plus fixed `0x8A` per-object records
  - encrypted Header2 fields, Header1/Header2 CRCs, and final TFT checksum are recomputed
- Command-line verification:
  - generated [case_04_add_text.tft](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/patch_add_object/case_04_add_text.tft>)
  - SHA256 matched the official `case_04_add_text/lcd_test.tft`
  - checksum verified as valid: `0xEA1A9568`
- Current limitation:
  - This is still a current-seed V1 path.
  - It supports adding exactly one object whose type is `t`, `b`, or `p`.
  - Object-name hashes are known for `page0/t0/b0/p0` from the seed and `t1/b1/p1` from fixtures; arbitrary new names still need the hash algorithm or more recovered mappings.

## Live Flash Verification: Added `t1` Object 2026-05-04

- Flashed generated file:
  - [case_04_add_text.tft](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/patch_add_object/case_04_add_text.tft>)
- Upload result:
  - port `COM36`
  - initial baud `9600`
  - download baud `921600`
  - bytes sent `11409408`
  - chunks sent `2786`
  - elapsed `208.079s`
  - log: [case_04_upload_result.json](</C:/Users/SinYu/Documents/Codex/2026-05-03/files-mentioned-by-the-user-delay/reverse_usarthmi/patch_add_object/case_04_upload_result.json>)
- Post-flash serial verification:
  - `connect` returned `TJC8048X543_011C`
  - `sendme` returned page `0`
  - `get t1.txt` returned `nihao`
  - `get t1.x` returned `355`
- Meaning:
  - Added-object tail generation is accepted by the real screen.
  - The new object is not only visible in the binary; it is present in the runtime object table and queryable over serial.
