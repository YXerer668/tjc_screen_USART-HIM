# Font Import And Upload

## Current Working Pieces

Build the local `.zi` helper:

```powershell
python -m usarthmi font build-zicli
```

Generate a `.zi` font subset directly from a scene:

```powershell
python -m usarthmi font from-scene `
  --scene examples\menu_demo\scene.json `
  --out .\build_font_scene.zi `
  --font-file C:\Windows\Fonts\simsun.ttc `
  --name SimSun32scene `
  --height 32 `
  --font-size 32
```

Generate a `.zi` font from explicit text files:

```powershell
python -m usarthmi font generate-zi `
  --out .\build_font_demo.zi `
  --font-file C:\Windows\Fonts\simsun.ttc `
  --name SimSun32subset `
  --height 32 `
  --font-size 32 `
  --codepage utf-8 `
  --text-file .\tools\zi_chars_demo.txt
```

Replace the `0.zi` entry inside an `.HMI` source file:

```powershell
python -m usarthmi font replace-hmi `
  --hmi .\build_menu_demo_v3\output.hmi `
  --zi .\build_font_scene.zi `
  --out .\build_menu_demo_v3\output_font.hmi
```

Upload a `.tft` file over serial:

```powershell
python -m usarthmi tft upload `
  --file your_file.tft `
  --port COM36 `
  --baud 9600 `
  --download-baud 115200
```

## Current Limit

- `.zi` generation works.
- `.HMI` font replacement works.
- `.tft` serial upload command is implemented from the official download protocol.
- A real `.tft` compiler for this project is still missing, so there is not yet an end-to-end `scene -> tft -> flash` chain fully inside `usarthmi`.
