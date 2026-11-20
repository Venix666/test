# Halcyon Visuals

A Vibrant Visuals resource pack for **Minecraft Bedrock 26.60+** aiming for the mood of Java's
best shader packs: saturated skies, long golden hours, readable blue nights, god rays,
colored block light, underwater light shafts, living water and per-block PBR. Pure official Vibrant Visuals data, so it runs on
every platform that has Vibrant Visuals.

![Vibrant preset day cycle](docs/previews/vibrant.png)

## Presets
| Pack | Look |
|---|---|
| **Vibrant** | Saturated skies, golden hours, blue moonlit nights, god rays |
| **Cinematic** | ACES filmic contrast, deeper shadows, denser light shafts, darker nights |
| **PBR** (add-on) | Surface depth for every block, glowing ores and emissive upgrades; stack above a preset |
| **Pixel Shadows** (add-on) | Blocky shadows snapped to the 16px texel grid; stack above a preset |

Both presets include colored block light for 106 light sources (torches warm, soul fire cyan,
redstone red, amethyst violet, sculk teal, ...) — see `docs/previews/lights.png`.

## Install
1. Build (below) or download `Halcyon-*.mcpack` from the latest CI run's artifacts.
2. Open the `.mcpack` files (Minecraft imports them), then activate one preset under
   **Settings → Global Resources**, optionally with **Halcyon PBR** and/or **Pixel Shadows** above it.
3. Turn on **Settings → Video → Graphics Mode → Vibrant Visuals**.

## Build
```bash
pip install pillow pytest
HALCYON_WITH_TEXTURES=1 ./tools/fetch_vanilla.sh   # pinned Mojang/bedrock-samples (nothing Mojang is committed)
python -m pytest -q
python -m halcyon build           # → dist/Halcyon-{Vibrant,Cinematic,PBR,PixelShadows}-v<version>.mcpack
python -m halcyon preview         # → docs/previews/*.png (day cycle, light palette, PBR sheet)
```

## How it works
`halcyon/style.py` holds the whole look (sun curves, sky colors, grading, fog, water, biome
families). The generator redefines every vanilla Vibrant Visuals identifier with that look,
validates every value against Mojang's documented ranges, and packages one `.mcpack` per
preset. `halcyon/pbr.py` derives a heightmap for each block from its color texture and adds
a faint glow to ore specks, keeping Mojang's own MERS maps. Details: [`docs/design.md`](docs/design.md). Plan: [`ROADMAP.md`](ROADMAP.md).
