"""The look: one source of truth for every preset.

Times use the Vibrant Visuals day fraction (0 noon, .25 sunset, .5 midnight,
.75 sunrise). `mirror()` authors noon→midnight once and reflects it onto the
morning, so dusk and dawn match.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .timeline import SUN_GONE, mirror, remap


@dataclass(frozen=True)
class Family:
    """How a biome family bends the base look."""

    sun_tint: tuple = (1.0, 1.0, 1.0)
    sun_saturation: float = 1.0
    ambient_tint: tuple = (1.0, 1.0, 1.0)
    sky_mix: tuple | None = None  # ((r, g, b), amount) blended into the daytime sky
    sky_saturation: float = 1.0
    sky_intensity: float = 1.0  # multiplier on indirect sky light (lower = darker shade)
    mie: float = 1.0  # multiplier on sun glow (dusty or humid air glows more)
    temperature: float | None = None  # grading Kelvin; higher = cooler image
    saturation: float = 1.0  # multiplier on midtone saturation
    contrast: float = 1.0  # multiplier on midtone contrast


@dataclass(frozen=True)
class Fog:
    """Volumetric fog profile (air medium)."""

    density: float
    scattering: tuple
    absorption: tuple = (0.0, 0.0, 0.0)
    g: float = 0.75  # Henyey-Greenstein: >0 scatters forward = god rays toward the sun
    max_height: float = 63.0  # full density at/below this Y
    zero_height: float = 240.0  # fades to zero at this Y
    # Underwater medium: light shafts below the surface. Vibrant Visuals uses only the
    # luminance of absorption, so absorption sets murkiness, not tint.
    water_density: float = 0.22
    water_scattering: tuple = (0.016, 0.022, 0.030)
    water_absorption: tuple = (0.12, 0.08, 0.08)
    water_g: float = 0.85


@dataclass(frozen=True)
class Look:
    name: str
    title: str
    description: str
    # lighting
    sun_illuminance: dict
    sun_color: dict
    moon_illuminance: dict
    moon_color: dict
    ambient_color: dict
    ambient_illuminance: dict
    sky_intensity: dict
    orbital_offset: float
    emissive_desaturation: float
    flash_illuminance: float
    flash_color: tuple
    # atmosphere
    rayleigh: dict
    sun_mie: dict
    moon_mie: dict
    sun_glare: dict
    blend_start: dict
    blend_mie_start: dict
    blend_min: float
    blend_max: float
    zenith: dict
    horizon: dict
    # grading
    midtones: dict
    highlights: dict
    shadows: dict
    temperature: float
    tonemapper: str
    # water + fog
    water: dict
    fogs: dict
    families: dict = field(default_factory=dict)
    otherworld_saturation: float = 1.2  # Nether/End colors derived from vanilla
    nether_ambient: tuple = ((255, 178, 140), 0.35)
    end_ambient: tuple = ((205, 175, 255), 0.4)
    light_saturation: float = 1.0  # colored block light: 0 = vanilla-white, >1 = more vivid
    shadow_style: str = "soft"  # soft | blocky (pixel shadows snapped to 16px texels)


# Fog identifier (without namespace) → profile name. First match wins; None keeps vanilla.
FOG_RULES: list[tuple[str, str | None]] = [
    (r"pale_garden|sulfur|powder_snow", None),
    (r"hell|crimson|warped|soulsand|basalt", None),
    (r"the_end", "end"),
    (r"mangrove|swamp", "swamp"),
    (r"roofed", "dark_forest"),
    (r"jungle|bamboo|humid|lush", "humid"),
    (r"mushroom", "mushroom"),
    (r"desert|dry", "desert"),
    (r"mesa", "mesa"),
    (r"frozen|ice|cold|snow|grove|peaks|jagged", "cold"),
    (r"ocean|beach|river", "ocean"),
    (r".*", "temperate"),
]

# Vanilla identifiers that are not overworld skies; derived from vanilla data instead.
NETHER = {"nether", "hell", "basalt_deltas", "crimson_forest", "warped_forest", "soulsand_valley"}
END = {"end"}

FAMILIES = {
    "default": Family(),
    "coolish": Family(sun_tint=(0.98, 0.99, 1.03), temperature=7600),
    "cold": Family(sun_tint=(0.95, 0.98, 1.05), sky_mix=((200, 225, 255), 0.15), temperature=8800),
    "ice_plains_spikes": Family(sun_tint=(0.94, 0.98, 1.06), sky_mix=((190, 228, 255), 0.25),
                                temperature=9800, saturation=1.05),
    "warmish": Family(sun_tint=(1.0, 0.98, 0.94), temperature=5600, mie=1.1),
    "hot": Family(sun_tint=(1.0, 0.97, 0.9), temperature=5200, contrast=1.05, saturation=1.06, mie=1.2),
    "desert": Family(sun_tint=(1.0, 0.96, 0.88), sky_mix=((235, 205, 165), 0.22), temperature=5000, mie=1.3),
    "mesa": Family(sun_tint=(1.0, 0.94, 0.86), sky_mix=((240, 180, 140), 0.25), temperature=4800,
                   saturation=1.05, mie=1.3),
    "swampland": Family(sun_tint=(0.98, 1.0, 0.86), sky_mix=((165, 180, 150), 0.35), sky_intensity=0.9,
                        temperature=6000, saturation=0.92, mie=1.2),
    "mangrove_swamp": Family(sun_tint=(1.0, 0.98, 0.86), sky_mix=((175, 185, 150), 0.3), temperature=5600,
                             saturation=0.95, mie=1.2),
    "roofed_forest": Family(sun_tint=(1.0, 0.98, 0.92), sky_intensity=0.85, temperature=6200, contrast=1.06),
    "pale_garden": Family(sun_tint=(0.9, 0.92, 0.95), sun_saturation=0.5, sky_mix=((200, 200, 205), 0.5),
                          sky_saturation=0.6, sky_intensity=0.9, temperature=8200, saturation=0.72),
    "mushroom_island": Family(sky_mix=((235, 165, 235), 0.25), temperature=6400, saturation=1.12),
    "lush_caves": Family(temperature=5200, saturation=1.15),
}

_SUNSET_HALF = {
    0.0: [255, 244, 228],
    0.12: [255, 236, 205],
    0.19: [255, 208, 150],
    0.23: [255, 160, 85],
    0.26: [255, 118, 48],
    0.29: [255, 90, 60],
    0.5: [255, 90, 60],
}

VIBRANT = Look(
    name="vibrant",
    title="Vibrant",
    description="Saturated skies, long golden hours, blue moonlit nights and god rays.",
    sun_illuminance=mirror({0.0: 115.0, 0.10: 100.0, 0.18: 68.0, 0.23: 32.0, 0.26: 11.0, 0.28: 3.0,
                            0.29: 0.4, 0.2915: 0.01, SUN_GONE: 0.0, 0.5: 0.0}),
    sun_color=mirror(_SUNSET_HALF),
    moon_illuminance=mirror({0.0: 0.0, 0.2: 0.0, 0.24: 0.12, 0.30: 0.8, 0.5: 0.8}),
    moon_color={0.0: [135, 165, 255]},
    ambient_color=mirror({0.0: [205, 220, 255], 0.25: [255, 205, 180], 0.32: [130, 145, 255],
                          0.5: [110, 130, 255]}),
    ambient_illuminance=mirror({0.0: 0.05, 0.25: 0.04, 0.32: 0.03, 0.5: 0.03}),
    sky_intensity=mirror({0.0: 0.85, 0.25: 0.9, 0.5: 1.0}),
    orbital_offset=20.0,
    emissive_desaturation=0.0,
    flash_illuminance=12.0,
    flash_color=(205, 175, 255),
    rayleigh=mirror({0.0: 12.0, 0.14: 12.0, 0.25: 6.0, 0.33: 5.0, 0.5: 5.0}),
    sun_mie=mirror({0.0: 0.12, 0.18: 0.3, 0.25: 1.0, 0.29: 0.7, 0.34: 0.0, 0.5: 0.0}),
    moon_mie=mirror({0.0: 0.0, 0.3: 0.0, 0.36: 0.25, 0.5: 0.25}),
    sun_glare=mirror({0.0: 0.03, 0.18: 0.04, 0.25: 0.085, 0.3: 0.04, 0.4: 0.0, 0.5: 0.0}),
    blend_start=mirror({0.0: 0.8, 0.25: 0.5, 0.30: 0.25, 0.5: 0.25}),
    blend_mie_start=mirror({0.0: 0.5, 0.1: 0.5, 0.2: 1.0, 0.5: 1.0}),
    blend_min=0.0,
    blend_max=0.25,
    zenith=mirror({0.0: [60, 118, 232], 0.17: [68, 122, 228], 0.23: [78, 98, 180], 0.27: [62, 58, 128],
                   0.31: [24, 30, 72], 0.36: [14, 20, 52], 0.5: [12, 18, 48]}),
    horizon=mirror({0.0: [172, 204, 242], 0.16: [188, 206, 238], 0.21: [250, 200, 150],
                    0.245: [255, 150, 92], 0.27: [245, 112, 108], 0.295: [160, 92, 150],
                    0.33: [60, 66, 120], 0.5: [38, 48, 98]}),
    midtones={"contrast": 1.2, "gain": 1.0, "gamma": 2.2, "offset": 0.0, "saturation": 1.18},
    highlights={"enabled": True, "highlightsMin": 1.8, "gain": [1.03, 1.0, 0.95], "saturation": 1.04},
    shadows={"enabled": True, "shadowsMax": 0.45, "gain": [0.95, 0.98, 1.06], "saturation": 1.08},
    temperature=6200,
    tonemapper="generic",
    water={
        "particle_concentrations": {"chlorophyll": 0.35, "cdom": 0.25, "suspended_sediment": 0.15},
        "biome_water_color_contribution": 0.3,
        "caustics": {"enabled": True, "frame_length": 0.07, "scale": 0.65, "power": 3},
        "waves": {"enabled": True, "frequency": 0.9, "octaves": 20, "depth": 0.55, "speed": 1.4,
                  "shape": 2.2, "pull": 0.3, "mix": 0.35, "frequency_scaling": 1.18,
                  "speed_scaling": 1.03, "direction_increment": 37.0},
    },
    fogs={
        "temperate": Fog(0.045, (0.040, 0.046, 0.056), g=0.78),
        "ocean": Fog(0.035, (0.038, 0.046, 0.058), g=0.75, zero_height=200.0, water_density=0.18,
                     water_absorption=(0.08, 0.06, 0.06), water_g=0.88),
        "cold": Fog(0.025, (0.045, 0.050, 0.058), g=0.72, zero_height=260.0, water_scattering=(0.014, 0.022, 0.034)),
        "humid": Fog(0.07, (0.060, 0.064, 0.060), g=0.6, zero_height=200.0, water_density=0.3,
                     water_scattering=(0.020, 0.026, 0.024), water_absorption=(0.2, 0.16, 0.12)),
        "swamp": Fog(0.09, (0.060, 0.065, 0.055), (0.20, 0.12, 0.18), g=0.45, max_height=62.0, zero_height=140.0,
                     water_density=0.45, water_scattering=(0.030, 0.032, 0.022), water_absorption=(0.35, 0.30, 0.20),
                     water_g=0.6),
        "dark_forest": Fog(0.07, (0.050, 0.055, 0.050), g=0.82, zero_height=180.0),
        "desert": Fog(0.03, (0.060, 0.050, 0.036), (0.0, 0.01, 0.03), g=0.7, zero_height=220.0),
        "mesa": Fog(0.035, (0.065, 0.048, 0.032), (0.0, 0.015, 0.035), g=0.7, zero_height=220.0),
        "mushroom": Fog(0.05, (0.014, 0.010, 0.014), (0.042, 0.137, 0.012), g=0.45),
        "end": Fog(0.25, (0.022, 0.016, 0.030), g=0.8, max_height=320.0, zero_height=320.0),
    },
    families=FAMILIES,
)


def _cinematic() -> Look:
    v = VIBRANT
    fogs = {k: replace(f, density=min(1.0, f.density * 1.4), g=min(0.9, f.g + 0.05)) for k, f in v.fogs.items()}
    fogs["end"] = v.fogs["end"]
    return replace(
        v,
        name="cinematic",
        title="Cinematic",
        description="Filmic contrast, deeper shadows, denser light shafts and darker nights.",
        sun_illuminance=remap(v.sun_illuminance, lambda x: x * 1.1),
        moon_illuminance=remap(v.moon_illuminance, lambda x: x * 0.65),
        sky_intensity=mirror({0.0: 0.7, 0.25: 0.78, 0.5: 0.9}),
        ambient_illuminance=mirror({0.0: 0.035, 0.25: 0.03, 0.32: 0.02, 0.5: 0.02}),
        sun_mie=remap(v.sun_mie, lambda x: min(1.0, x * 1.15)),
        midtones={**v.midtones, "contrast": 1.3, "saturation": 1.06},
        light_saturation=0.9,
        highlights={**v.highlights, "gain": [1.05, 1.0, 0.93]},
        shadows={**v.shadows, "gain": [0.92, 0.97, 1.08], "saturation": 1.0},
        temperature=6000,
        tonemapper="aces",
        fogs=fogs,
    )


CINEMATIC = _cinematic()
PRESETS = {look.name: look for look in (VIBRANT, CINEMATIC)}
