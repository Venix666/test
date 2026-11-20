"""Small RGB (0-255) helpers."""

from __future__ import annotations

RGB = list


def clamp(rgb) -> RGB:
    return [max(0, min(255, round(c))) for c in rgb]


def tint(rgb, mul) -> RGB:
    return clamp(c * m for c, m in zip(rgb, mul))


def mix(a, b, t: float) -> RGB:
    return clamp(x + (y - x) * t for x, y in zip(a, b))


def saturate(rgb, amount: float) -> RGB:
    """Scale saturation around Rec.709 luma; 1.0 leaves the color unchanged."""
    luma = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return clamp(luma + (c - luma) * amount for c in rgb)


def hex_to_rgb(value: str) -> RGB:
    h = value.lstrip("#")
    if len(h) == 8:  # ARGB
        h = h[2:]
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)]
