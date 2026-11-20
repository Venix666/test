"""Render a preset's day cycle to PNG, for tuning without launching the game.

Rows: sky (zenith→horizon) across the day, direct light (sun/moon color ×
log illuminance), ambient light, then each biome family's noon and sunset sky.
The x axis runs from pre-dawn through noon, sunset and night.
"""

from __future__ import annotations

import math
from pathlib import Path

from .color import mix, saturate
from .gen import _day_weight
from .style import Look
from .timeline import sample

WIDTH = 1200
START = 0.70  # day fraction at the left edge


def _t(x: int) -> float:
    return (START + x / WIDTH) % 1.0


def _family_sky(look: Look, fam, t: float, which: str):
    c = sample(look.zenith if which == "zenith" else look.horizon, t)
    if fam.sky_mix:
        target, amount = fam.sky_mix
        c = mix(c, target, amount * _day_weight(t))
    return saturate(c, fam.sky_saturation)


def render(look: Look, path: Path) -> Path:
    from PIL import Image, ImageDraw

    sky_h, light_h, amb_h, label_h = 200, 46, 30, 22
    fam_names = list(look.families)
    swatch_h = 64
    height = sky_h + light_h + amb_h + label_h + 30 + swatch_h + 24
    img = Image.new("RGB", (WIDTH, height), (18, 18, 22))
    px = img.load()
    draw = ImageDraw.Draw(img)

    peak = math.log10(1 + max(look.sun_illuminance.values()))
    for x in range(WIDTH):
        t = _t(x)
        zen, hor = sample(look.zenith, t), sample(look.horizon, t)
        for y in range(sky_h):
            f = (y / sky_h) ** 1.5
            px[x, y] = tuple(int(z + (h - z) * f) for z, h in zip(zen, hor))
        sun = sample(look.sun_color, t)
        sun_k = math.log10(1 + sample(look.sun_illuminance, t)) / peak
        moon = sample(look.moon_color, t)
        moon_k = min(1.0, sample(look.moon_illuminance, t)) * 0.45
        direct = tuple(min(255, int(s * sun_k + m * moon_k)) for s, m in zip(sun, moon))
        draw.line([(x, sky_h), (x, sky_h + light_h - 1)], fill=direct)
        amb = sample(look.ambient_color, t)
        amb_k = min(1.0, sample(look.ambient_illuminance, t) / 0.06)
        draw.line([(x, sky_h + light_h), (x, sky_h + light_h + amb_h - 1)],
                  fill=tuple(int(c * amb_k) for c in amb))

    y0 = sky_h + light_h + amb_h
    for label, t in (("sunrise", 0.75), ("noon", 0.0), ("sunset", 0.25), ("midnight", 0.5)):
        x = int(((t - START) % 1.0) * WIDTH)
        draw.line([(x, 0), (x, y0 + 4)], fill=(255, 255, 255), width=1)
        draw.text((x + 4, y0 + 5), label, fill=(230, 230, 230))

    y1 = y0 + label_h + 30
    draw.text((6, y1 - 18), f"Halcyon {look.title}  |  rows: sky, direct light, ambient  |  "
              "swatches: biome family skies at noon and sunset", fill=(150, 150, 160))
    w = WIDTH // len(fam_names)
    for i, (name, fam) in enumerate(look.families.items()):
        for half, t in enumerate((0.0, 0.25)):
            x0 = i * w + half * (w // 2)
            for y in range(swatch_h):
                f = (y / swatch_h) ** 1.5
                zen = _family_sky(look, fam, t, "zenith")
                hor = _family_sky(look, fam, t, "horizon")
                c = tuple(int(z + (h - z) * f) for z, h in zip(zen, hor))
                draw.line([(x0, y1 + y), (x0 + w // 2 - 1, y1 + y)], fill=c)
        draw.text((i * w + 2, y1 + swatch_h + 4), name[:12], fill=(200, 200, 205))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


PBR_SAMPLES = ["stone", "cobblestone", "stonebrick", "brick", "planks_oak", "log_oak", "sandstone",
               "deepslate/cobbled_deepslate", "diamond_ore", "redstone_ore", "gold_ore", "leaves_oak", "glass"]


def render_pbr(vanilla, path: Path, scale: int = 8) -> Path:
    """Contact sheet per block: color | heightmap | flat-lit | lit with derived normals | ore glow."""
    import numpy as np
    from PIL import Image, ImageDraw

    from .pbr import GLOW_ORES, find_image, heightmap, ore_mask, rule_for, textures_root

    root = textures_root(vanilla)
    light = np.array([-0.55, -0.6, 0.58])
    light /= np.linalg.norm(light)
    rows = []
    for name in PBR_SAMPLES:
        folder, base = (root / name).parent, (root / name).name
        p = find_image(folder, base)
        if p is None:
            continue
        rgba = np.array(Image.open(p).convert("RGBA"))[:16]  # first frame of animated strips
        h = heightmap(rgba, rule_for(name)).astype(np.float32) / 255.0
        dx = np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)
        dy = np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)
        n = np.dstack([-dx * 3.0, -dy * 3.0, np.ones_like(h)])
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        rgb = rgba[..., :3].astype(np.float32)
        flat = rgb * (0.35 + 0.65 * max(0.0, light[2]))
        lit = rgb * (0.35 + 0.65 * np.clip(n @ light, 0.0, 1.0))[..., None]
        glow = rgb * 0.25 + (ore_mask(rgba)[..., None] * rgb * 1.2 if GLOW_ORES.search(name) else 0.0)
        tiles = [rgb, np.repeat(h[..., None] * 255.0, 3, axis=-1), flat, lit, glow]
        rows.append((name, [np.clip(t, 0, 255).astype(np.uint8) for t in tiles]))

    tile, pad, label_w = 16 * scale, 6, 190
    width = label_w + 5 * (tile + pad)
    img = Image.new("RGB", (width, 24 + len(rows) * (tile + pad)), (18, 18, 22))
    draw = ImageDraw.Draw(img)
    for i, head in enumerate(["color", "heightmap", "flat lit", "with normals", "night (ore glow)"]):
        draw.text((label_w + i * (tile + pad), 6), head, fill=(200, 200, 205))
    for r, (name, tiles) in enumerate(rows):
        y = 24 + r * (tile + pad)
        draw.text((6, y + tile // 2 - 6), name, fill=(220, 220, 225))
        for i, t in enumerate(tiles):
            img.paste(Image.fromarray(t, "RGB").resize((tile, tile), Image.NEAREST),
                      (label_w + i * (tile + pad), y))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
