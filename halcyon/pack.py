"""Assemble a preset into a pack folder and a .mcpack archive."""

from __future__ import annotations

import io
import json
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .gen import generate
from .limits import validate
from .style import VIBRANT, Look
from .vanilla import Vanilla

NAMESPACE = uuid.UUID("6f1d3c52-8a4e-4f0b-9d2a-1c7e5b9a4d10")
MIN_ENGINE = [1, 21, 120]  # Vibrant Visuals pack customization requires >= 1.21.120


def version_tuple(version: str = __version__) -> list[int]:
    return [int(x) for x in version.split(".")]


@dataclass(frozen=True)
class PackInfo:
    name: str
    title: str
    description: str


PBR_INFO = PackInfo(
    "pbr", "PBR",
    "Procedural heightmaps for every block and glowing ores. Stack above a Halcyon preset.",
)


def manifest(look: Look | PackInfo, version: str = __version__) -> dict:
    """Stable UUIDs per pack so updates replace the installed pack."""
    v = version_tuple(version)
    return {
        "format_version": 2,
        "header": {
            "name": f"Halcyon Visuals: {look.title}",
            "description": f"{look.description} Requires Vibrant Visuals. v{version}",
            "uuid": str(uuid.uuid5(NAMESPACE, f"halcyon/{look.name}/header")),
            "version": v,
            "min_engine_version": MIN_ENGINE,
        },
        "modules": [{
            "type": "resources",
            "uuid": str(uuid.uuid5(NAMESPACE, f"halcyon/{look.name}/resources")),
            "version": v,
        }],
        "capabilities": ["pbr"],
        "metadata": {"authors": ["Halcyon Visuals contributors"], "generated_with": {"halcyon": [version]}},
    }


def pack_icon(look: Look, t: float = 0.245) -> bytes:
    """A 256x256 sun-over-water icon drawn from the preset's own sky colors (t = time of day)."""
    from PIL import Image, ImageDraw, ImageFilter

    from .timeline import sample

    size = 256
    img = Image.new("RGB", (size, size))
    px = img.load()
    zen, hor = sample(look.zenith, t), sample(look.horizon, t)
    horizon_y = 160
    for y in range(horizon_y):
        f = (y / horizon_y) ** 1.6
        c = tuple(int(z + (h - z) * f) for z, h in zip(zen, hor))
        for x in range(size):
            px[x, y] = c
    glow = Image.new("L", (size, size), 0)
    ImageDraw.Draw(glow).ellipse((88, 96, 168, 176), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    sun = sample(look.sun_color, t)
    img = Image.composite(Image.new("RGB", (size, size), tuple(int(c) for c in sun)), img, glow)
    draw = ImageDraw.Draw(img)
    draw.ellipse((108, 116, 148, 156), fill=(255, 236, 200))
    water_top, water_bottom = (40, 60, 110), (12, 18, 48)
    for y in range(horizon_y, size):
        f = (y - horizon_y) / (size - horizon_y)
        c = tuple(int(a + (b - a) * f) for a, b in zip(water_top, water_bottom))
        draw.line([(0, y), (size, y)], fill=c)
    for i, y in enumerate(range(horizon_y + 4, size, 9)):  # sun glints on the water
        w = max(6, 46 - i * 4)
        draw.line([(128 - w, y), (128 + w, y)], fill=tuple(int(c) for c in sun), width=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def build_pack(look: Look, vanilla: Vanilla, out_dir: Path, version: str = __version__) -> Path:
    """Write the pack folder and its .mcpack; return the .mcpack path."""
    docs = generate(look, vanilla)
    for path, doc in docs.items():
        try:
            validate(doc)
        except ValueError as e:
            raise ValueError(f"{look.name}/{path}: {e}") from e

    files = {p: _dump(d) for p, d in docs.items()}
    return _write(look, files, pack_icon(look), Path(out_dir), version)


def build_pbr_pack(vanilla: Vanilla, out_dir: Path, version: str = __version__,
                   glowing_ores: bool = True) -> Path:
    from .pbr import generate as generate_pbr

    files = generate_pbr(vanilla, glowing_ores=glowing_ores)
    return _write(PBR_INFO, files, pack_icon(VIBRANT, t=0.12), Path(out_dir), version)


def _write(info: Look | PackInfo, files: dict[str, bytes], icon: bytes, out_dir: Path, version: str) -> Path:
    folder = out_dir / f"Halcyon-{info.title}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    files = {"manifest.json": _dump(manifest(info, version)), "pack_icon.png": icon, **files}
    for rel, data in sorted(files.items()):
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    archive = out_dir / f"Halcyon-{info.title}-v{version}.mcpack"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, data in sorted(files.items()):
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))  # reproducible archives
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return archive


def _dump(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2) + "\n").encode("utf-8")
