# USART HMI Scene Builder

## Quick Start

Build the bundled example scene against the current seed project:

```powershell
python -m usarthmi scene build examples\menu_demo\scene.json `
  --seed "D:\MySTM32\H723ZGT6\Program\ISP_Test\lcd_test.HMI" `
  --out .\build_menu_demo_v2
```

Validate a scene file:

```powershell
python -m usarthmi scene validate examples\menu_demo\scene.yaml
```

Normalize a single image asset:

```powershell
python -m usarthmi hmi import-image .\examples\menu_demo\assets\play.png --out .\tmp_assets
```

## Scene Notes

- `canvas.width/height` are fixed to `800x480` for the current workflow.
- `assets` can define `normal`, `pressed`, and optional `disabled` image variants.
- `button` widgets map those image states to `pic`, `picc`, and `pic2/picc2`.
- Layout authoring supports `absolute`, `row`, `column`, `grid`, `stack`, and `anchor`.
- Output files are:
  - `output.hmi`
  - `scene.normalized.json`
  - `manifest.json`
  - normalized image files under `assets\`

## Current Limits

- The `.HMI` page writer now preserves the seed container offsets and rewrites `0.pa`.
- Image files are normalized and assigned resource IDs in `manifest.json`.
- True static image resource packing into `.HMI/.TFT` is still experimental, so `output_tft` is not emitted yet.
