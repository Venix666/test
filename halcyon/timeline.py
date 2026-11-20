"""Time-of-day keyframes.

Vibrant Visuals keyframes use a 0..1 day fraction: 0.0 noon, 0.25 sunset,
0.5 midnight, 0.75 sunrise. Vanilla hands the shadow-casting light from the
sun to the moon at 0.292 and back at 0.708.
"""

from __future__ import annotations

NOON, SUNSET, MIDNIGHT, SUNRISE = 0.0, 0.25, 0.5, 0.75
SUN_GONE, SUN_BACK = 0.292, 0.708


def mirror(half_day: dict[float, object]) -> dict[float, object]:
    """Author noon→midnight (keys in [0, 0.5]) and reflect it onto midnight→noon."""
    out = dict(half_day)
    for t, v in half_day.items():
        if not 0.0 <= t <= 0.5:
            raise ValueError(f"mirror() keys must be in [0, 0.5], got {t}")
        if t not in (0.0, 0.5):
            out[round(1.0 - t, 6)] = v
    return out


def keyframes(points: dict[float, object]) -> dict[str, object]:
    """Format keyframes for JSON: sorted 6-decimal keys, closing the loop at 1.0."""
    pts = dict(points)
    if 0.0 in pts and 1.0 not in pts:
        pts[1.0] = pts[0.0]
    for t in pts:
        if not 0.0 <= t <= 1.0:
            raise ValueError(f"keyframe time {t} outside [0, 1]")
    return {f"{t:.6f}": _clean(v) for t, v in sorted(pts.items())}


def sample(points: dict[float, object], t: float):
    """Linearly interpolate keyframes (numbers or RGB lists) at day fraction t."""
    pts = sorted(dict(points).items())
    if pts[0][0] > 0.0:
        pts.insert(0, (0.0, pts[-1][1]))
    if pts[-1][0] < 1.0:
        pts.append((1.0, pts[0][1]))
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            if isinstance(v0, (list, tuple)):
                return [a + (b - a) * f for a, b in zip(v0, v1)]
            return v0 + (v1 - v0) * f
    return pts[-1][1]


def remap(points: dict[float, object], fn) -> dict[float, object]:
    """Apply fn to every keyframe value."""
    return {t: fn(v) for t, v in points.items()}


def _clean(v):
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, float):
        r = round(v, 4)
        return int(r) if r.is_integer() and abs(r) >= 1 else r
    return v
