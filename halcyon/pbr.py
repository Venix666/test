"""Integrated PBR: procedural heightmaps and glowing ores for every vanilla block.

Vanilla Vibrant Visuals already authors metalness, roughness, subsurface and
light-source emissive (MERS) for each block, but ships normal maps for only a
handful. This module derives a heightmap from each block's color texture
(Complementary-style "integrated PBR") and adds a faint glow to ore specks.

Texture sets may only reference images in their own pack, so the build copies
each block's vanilla color and MERS images next to the generated heightmap.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .vanilla import Vanilla, load_json

TEXTURE_SET_FORMAT = "1.21.30"
MERS_KEYS = ("metalness_emissive_roughness_subsurface", "metalness_emissive_roughness")
EXTENSIONS = (".tga", ".png", ".jpg", ".jpeg")  # engine priority order


@dataclass(frozen=True)
class Rule:
    pattern: str
    amplitude: float  # 0 = flat, 1 = full 0..255 height range
    source: str = "luma"  # luma | inv_luma | saturation | ore (luma with specks raised)


# First match on the texture's path (relative to textures/blocks, no extension) wins.
RULES: list[Rule] = [
    Rule(r"(^|/)brick$|mud_bricks", 0.7, "saturation"),  # light mortar sits lower than the bricks
    Rule(r"_ore$|ancient_debris", 0.8, "ore"),
    Rule(r"glass|ice$|ice_|^ice|concrete(?!_powder)|wool|carpet|snow|slime|honey|portal|beacon|"
         r"shulker|smooth|water|lava|frosted", 0.12),
    Rule(r"glazed_terracotta", 0.25),
    Rule(r"leaves|grass|fern|flower|vine|sapling|tulip|rose|dandelion|azalea|moss_carpet|"
         r"crop|wheat|carrot|potato|beetroot|sugar_cane|bush|petal|lily", 0.35),
    Rule(r"cobble|brick|ore|deepslate|blackstone|netherrack|basalt|tuff|gravel|log|stripped|bark|"
         r"stem|hyphae|end_stone|prismarine|purpur|mossy|dripstone|calcite|bone_block|"
         r"sandstone|crying_obsidian|obsidian|ancient_debris|magma|nylium|soul|mud|packed|root", 0.8),
    Rule(r".*", 0.5),
]

GLOW_ORES = re.compile(r"(diamond|emerald|lapis|redstone|gold|copper|iron|quartz)_ore")
ORE_EMISSIVE = 24  # vanilla glowstone sits at 21-41, so ores stay a faint sparkle


def rule_for(name: str) -> Rule:
    for rule in RULES:
        if re.search(rule.pattern, name):
            return rule
    return RULES[-1]


def heightmap(rgba: np.ndarray, rule: Rule) -> np.ndarray:
    """uint8 single-channel heightmap from an RGBA uint8 image."""
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    alpha = rgba[..., 3] > 0
    if rule.source == "saturation":
        mx, mn = rgb.max(axis=-1), rgb.min(axis=-1)
        signal = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    else:
        signal = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        if rule.source == "inv_luma":
            signal = 1.0 - signal
        elif rule.source == "ore":  # specks protrude even when darker than the host stone
            signal = 0.5 * signal + 0.5 * ore_mask(rgba)
    visible = signal[alpha] if alpha.any() else signal.ravel()
    mean, std = float(visible.mean()), float(visible.std())
    z = np.clip((signal - mean) / (std + 1e-3), -2.0, 2.0) / 4.0  # → [-0.5, 0.5]
    height = 0.5 + z * rule.amplitude
    height[~alpha] = 0.5
    return np.clip(np.round(height * 255.0), 0, 255).astype(np.uint8)


def ore_mask(rgba: np.ndarray) -> np.ndarray:
    """0..1 mask of pixels that stand out from the host stone (the ore specks)."""
    rgb = rgba[..., :3].astype(np.float32)
    host = np.median(rgb.reshape(-1, 3), axis=0)
    dist = np.linalg.norm(rgb - host, axis=-1) / 255.0
    luma = (rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)) / 255.0
    mask = np.clip((dist - 0.18) / 0.2, 0.0, 1.0) * (luma > 0.08)
    return mask * (rgba[..., 3] > 0)


def find_image(folder: Path, name: str) -> Path | None:
    for ext in EXTENSIONS:
        p = folder / f"{name}{ext}"
        if p.is_file():
            return p
    return None


def _png(arr: np.ndarray, mode: str) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr, mode).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _glow(mers_path: Path, color_rgba: np.ndarray) -> bytes:
    img = Image.open(mers_path)
    mode = "RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB"
    mers = np.array(img.convert(mode))
    if mers.shape[:2] != color_rgba.shape[:2]:
        return mers_path.read_bytes()
    glow = np.round(ore_mask(color_rgba) * ORE_EMISSIVE).astype(np.uint8)
    mers[..., 1] = np.maximum(mers[..., 1], glow)
    buf = io.BytesIO()
    Image.fromarray(mers, mode).save(buf, "TGA" if mers_path.suffix == ".tga" else "PNG")
    return buf.getvalue()


def textures_root(vanilla: Vanilla) -> Path:
    return vanilla.pack / "textures" / "blocks"


def generate(vanilla: Vanilla, glowing_ores: bool = True) -> dict[str, bytes]:
    """Return {pack-relative path: file bytes} for the PBR add-on pack."""
    root = textures_root(vanilla)
    if not root.is_dir():
        raise FileNotFoundError(f"{root} missing: run HALCYON_WITH_TEXTURES=1 tools/fetch_vanilla.sh")
    out: dict[str, bytes] = {}
    for ts_path in sorted(root.rglob("*.texture_set.json")):
        ts = load_json(ts_path)["minecraft:texture_set"]
        if "normal" in ts or "heightmap" in ts:
            continue  # vanilla already has surface detail
        color_ref = ts.get("color")
        mers_key = next((k for k in MERS_KEYS if k in ts), None)
        if not isinstance(color_ref, str):
            continue  # uniform color: nothing to derive height from
        folder = ts_path.parent
        color_path = find_image(folder, color_ref)
        if color_path is None:
            continue
        rel_dir = folder.relative_to(vanilla.pack).as_posix()
        name = ts_path.name.removesuffix(".texture_set.json")
        key = f"{folder.relative_to(root).as_posix()}/{name}".lstrip("./")
        rgba = np.array(Image.open(color_path).convert("RGBA"))

        new_ts = {"color": color_ref}
        out[f"{rel_dir}/{color_path.name}"] = color_path.read_bytes()
        if mers_key:
            mers_ref = ts[mers_key]
            new_ts[mers_key] = mers_ref
            if isinstance(mers_ref, str):
                mers_path = find_image(folder, mers_ref)
                if mers_path is None:
                    continue
                data = (_glow(mers_path, rgba) if glowing_ores and GLOW_ORES.search(key)
                        else mers_path.read_bytes())
                out[f"{rel_dir}/{mers_path.name}"] = data
        height_name = f"{name}_heightmap"
        new_ts["heightmap"] = height_name
        out[f"{rel_dir}/{height_name}.png"] = _png(heightmap(rgba, rule_for(key)), "L")
        out[f"{rel_dir}/{ts_path.name}"] = (json.dumps(
            {"format_version": TEXTURE_SET_FORMAT, "minecraft:texture_set": new_ts}, indent=2) + "\n").encode()
    return out
