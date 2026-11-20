"""Colored block light and shadow style.

`local_lighting/local_lighting.json` sets the light color of any block and
whether it is a *static* light (baked, cheap) or a *point* light (dynamic
shadows and specular highlights, expensive). Light reach and strength come
from the block's light emission level, which resource packs can't change.

Shared light families keep the number of unique colors low, which Mojang
recommends for performance.
"""

from __future__ import annotations

import logging

from .color import hex_to_rgb, mix, saturate

log = logging.getLogger(__name__)

# Light families (sRGB). Reused across blocks on purpose.
TORCH = "#FFAE5C"
FIRE = "#FF9A48"
CANDLE = "#FFB86B"
LAVA = "#FF6A1C"
SOUL = "#3FD7FF"
REDSTONE = "#FF2E18"
LAMP = "#FFB46A"
GLOWSTONE = "#FFD07A"
SHROOM = "#FF9A4D"
SEA = "#9FEFFF"
END_ROD = "#F2E9FF"
ENDER = "#6EFFD2"
VOID = "#7A5CFF"
PORTAL = "#B44DFF"
AMETHYST = "#C48CFF"
LICHEN = "#A8FFD0"
BERRY = "#FFB347"
SCULK = "#3FE6D9"
COPPER_FLAME = "#A6F57A"
COPPER_BULB = "#FFC380"

COPPER_STAGES = ["", "exposed_", "weathered_", "oxidized_"]
DYES = {
    "white": "#F9FFFE", "orange": "#F9801D", "magenta": "#C74EBD", "light_blue": "#3AB3DA",
    "yellow": "#FED83D", "lime": "#80C71F", "pink": "#F38BAA", "gray": "#474F52",
    "light_gray": "#9D9D97", "cyan": "#169C9C", "purple": "#8932B8", "blue": "#3C44AA",
    "brown": "#835432", "green": "#5E7C16", "red": "#B02E26", "black": "#1D1D21",
}

# Blocks the game always renders as point lights (Mojang docs); we only recolor them.
DEFAULT_POINT_LIGHTS = {"torch", "redstone_torch", "end_rod", "lantern", "soul_lantern", "soul_torch",
                        "sea_pickle", "copper_torch"}
# Extra point lights Halcyon adds: rare, small sources where dynamic shadows pay off.
EXTRA_POINT_LIGHTS = {"conduit"}


def _normalized(rgb) -> list[int]:
    """Scale so the brightest channel is 255: tinted lights keep their strength."""
    peak = max(rgb) or 1
    return [round(c * 255 / peak) for c in rgb]


def palette() -> dict[str, list[int]]:
    """Block name (no namespace) → light color."""
    c = {
        "torch": TORCH, "lantern": FIRE, "lit_pumpkin": FIRE, "campfire": FIRE, "fire": FIRE,
        "lit_furnace": FIRE, "lit_smoker": FIRE, "lit_blast_furnace": FIRE, "trial_spawner": FIRE,
        "vault": LAMP, "brewing_stand": GLOWSTONE,
        "lava": LAVA, "flowing_lava": LAVA, "lava_cauldron": LAVA, "magma": LAVA,
        "soul_torch": SOUL, "soul_lantern": SOUL, "soul_campfire": SOUL, "soul_fire": SOUL,
        "redstone_torch": REDSTONE, "lit_redstone_ore": REDSTONE, "lit_deepslate_redstone_ore": REDSTONE,
        "powered_repeater": REDSTONE, "powered_comparator": REDSTONE, "lit_redstone_lamp": LAMP,
        "glowstone": GLOWSTONE, "shroomlight": SHROOM, "ochre_froglight": "#FFD46A",
        "verdant_froglight": "#A6FF8C", "pearlescent_froglight": "#F4A6FF",
        "seaLantern": SEA, "sea_pickle": SEA, "conduit": SEA, "beacon": "#D6F7FF",
        "end_rod": END_ROD, "end_portal": VOID, "end_gateway": VOID, "dragon_egg": PORTAL,
        "end_portal_frame": ENDER, "ender_chest": ENDER, "enchanting_table": "#B49BFF",
        "portal": PORTAL, "crying_obsidian": PORTAL, "respawn_anchor": PORTAL,
        "amethyst_cluster": AMETHYST, "large_amethyst_bud": AMETHYST, "medium_amethyst_bud": AMETHYST,
        "small_amethyst_bud": AMETHYST,
        "glow_lichen": LICHEN, "cave_vines_body_with_berries": BERRY, "cave_vines_head_with_berries": BERRY,
        "firefly_bush": "#E6FF7A",
        "sculk_catalyst": SCULK, "sculk_sensor": SCULK, "calibrated_sculk_sensor": SCULK,
        "copper_torch": COPPER_FLAME,
    }
    colors = {name: hex_to_rgb(v) for name, v in c.items()}
    for stage in COPPER_STAGES:
        for wax in ("", "waxed_"):
            colors[f"{wax}{stage}copper_lantern"] = hex_to_rgb(COPPER_FLAME)
            colors[f"{wax}{stage}copper_bulb"] = hex_to_rgb(COPPER_BULB)
    base = hex_to_rgb(CANDLE)
    colors["candle"] = base
    colors["candle_cake"] = base
    for dye, hexcolor in DYES.items():  # dyed candles cast a hint of their color
        tinted = _normalized(mix(base, hex_to_rgb(hexcolor), 0.35))
        colors[f"{dye}_candle"] = tinted
        colors[f"{dye}_candle_cake"] = tinted
    return colors


def point_lights() -> set[str]:
    candles = {"candle", "candle_cake"} | {f"{d}_candle" for d in DYES} | {f"{d}_candle_cake" for d in DYES}
    copper = {f"{w}{s}copper_lantern" for s in COPPER_STAGES for w in ("", "waxed_")}
    return DEFAULT_POINT_LIGHTS | EXTRA_POINT_LIGHTS | candles | copper


def local_lighting(saturation: float = 1.0, known_blocks: set[str] | None = None) -> dict:
    points = point_lights()
    settings = {}
    for name, rgb in sorted(palette().items()):
        if known_blocks is not None and name not in known_blocks:
            log.warning("local lighting: minecraft:%s is not a vanilla block, skipped", name)
            continue
        settings[f"minecraft:{name}"] = {
            "light_color": "#{:02X}{:02X}{:02X}".format(*saturate(rgb, saturation)),
            "light_type": "point_light" if name in points else "static_light",
        }
    return {"minecraft:local_light_settings": settings}


def shadows(style: str) -> dict:
    """soft (default) or blocky shadows snapped to the 16px texel grid."""
    if style == "blocky":
        return {"minecraft:shadow_settings": {"shadow_style": "blocky_shadows", "texel_size": 16}}
    return {"minecraft:shadow_settings": {"shadow_style": "soft_shadows"}}
