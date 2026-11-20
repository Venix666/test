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
