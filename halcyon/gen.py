"""Generate Vibrant Visuals settings documents for a Look.

Every vanilla identifier is redefined with the same identifier and filename, so
the vanilla client_biome files route each biome to Halcyon's settings.
"""

from __future__ import annotations

import copy
import logging
import re

from . import lights
from .color import hex_to_rgb, mix, saturate, tint
from .style import END, FOG_RULES, NETHER, Family, Fog, Look
from .timeline import keyframes
from .vanilla import Vanilla

log = logging.getLogger(__name__)

FORMAT = {
    "lighting": "1.26.0",  # keyframed ambient + sky need 1.26.0
    "atmospherics": "1.21.40",
    "color_grading": "1.21.90",
    "water": "1.26.0",  # biome_water_color_contribution needs 1.26.0
    "fogs": "1.21.90",
    "local_lighting": "1.21.120",
    "shadows": "1.21.80",
}
SUFFIX = {"lighting": "_lighting", "atmospherics": "_atmospherics", "color_grading": "_color_grading"}


def family_name(identifier: str, folder: str) -> str:
    name = identifier.split(":", 1)[1]
    if name.startswith("default_"):
        return "default"
    return name.removesuffix(SUFFIX.get(folder, ""))


def family_for(look: Look, name: str, identifier: str) -> Family:
    fam = look.families.get(name)
    if fam is None:
        log.warning("unknown vanilla identifier %s: using the default family", identifier)
        fam = look.families["default"]
    return fam


def generate(look: Look, vanilla: Vanilla) -> dict[str, dict]:
    """Return {pack-relative path: JSON document}."""
    out: dict[str, dict] = {}
    for folder, build in (("lighting", _lighting), ("atmospherics", _atmospherics),
                          ("color_grading", _color_grading), ("water", _water)):
        for entry in vanilla.entries(folder):
            out[f"{folder}/{entry.filename}"] = build(look, entry)
    for entry in vanilla.entries("fogs"):
        doc = _fog(look, entry)
        if doc is not None:
            out[f"fogs/{entry.filename}"] = doc
    out["local_lighting/local_lighting.json"] = {
        "format_version": FORMAT["local_lighting"],
        **lights.local_lighting(look.light_saturation, vanilla.known_blocks()),
    }
    out["shadows/global.json"] = {"format_version": FORMAT["shadows"], **lights.shadows(look.shadow_style)}
    return out


# -- lighting ------------------------------------------------------------------

def _lighting(look: Look, entry) -> dict:
    name = family_name(entry.identifier, "lighting")
    if name in NETHER or name in END:
        settings = _derived_lighting(look, entry, "nether" if name in NETHER else "end")
    else:
        settings = _overworld_lighting(look, family_for(look, name, entry.identifier), entry.identifier)
    return {"format_version": FORMAT["lighting"], "minecraft:lighting_settings": settings}


def _overworld_lighting(look: Look, fam: Family, identifier: str) -> dict:
    sun_color = {t: saturate(tint(c, fam.sun_tint), fam.sun_saturation) for t, c in look.sun_color.items()}
    ambient = {t: tint(c, fam.ambient_tint) for t, c in look.ambient_color.items()}
    sky = {t: min(1.0, max(0.1, x * fam.sky_intensity)) for t, x in look.sky_intensity.items()}
    return {
        "description": {"identifier": identifier},
        "directional_lights": {
            "orbital": {
                "sun": {"illuminance": keyframes(look.sun_illuminance), "color": keyframes(sun_color)},
                "moon": {"illuminance": keyframes(look.moon_illuminance), "color": keyframes(look.moon_color)},
                "orbital_offset_degrees": look.orbital_offset,
            },
            "flash": {"illuminance": look.flash_illuminance, "color": list(look.flash_color)},
        },
        "emissive": {"desaturation": look.emissive_desaturation},
        "ambient": {"color": keyframes(ambient), "illuminance": keyframes(look.ambient_illuminance)},
        "sky": {"intensity": keyframes(sky)},
    }


def _derived_lighting(look: Look, entry, kind: str) -> dict:
    s = copy.deepcopy(entry.doc["minecraft:lighting_settings"])
    lights = s.setdefault("directional_lights", {})
    if "orbital" not in lights:  # 1.21.70 layout → 1.21.80 orbital layout
        lights["orbital"] = {k: lights.pop(k) for k in ("sun", "moon", "orbital_offset_degrees") if k in lights}
    # Orbital offset can't blend between biomes: every lighting file in a pack must share it.
    lights["orbital"]["orbital_offset_degrees"] = look.orbital_offset
    target, amount = look.nether_ambient if kind == "nether" else look.end_ambient
    ambient = s.setdefault("ambient", {"color": [255, 255, 255], "illuminance": 0.1})
    ambient["color"] = _map_colors(ambient.get("color", [255, 255, 255]), lambda c: mix(c, target, amount))
    s["emissive"] = {"desaturation": look.emissive_desaturation}
    return s


# -- atmospherics --------------------------------------------------------------

def _atmospherics(look: Look, entry) -> dict:
    name = family_name(entry.identifier, "atmospherics")
    if name in NETHER or name in END:
        s = copy.deepcopy(entry.doc["minecraft:atmosphere_settings"])
        for key in ("sky_zenith_color", "sky_horizon_color"):
            if key in s:
                s[key] = _map_colors(s[key], lambda c: saturate(c, look.otherworld_saturation))
    else:
        s = _overworld_atmosphere(look, family_for(look, name, entry.identifier), entry.identifier)
    return {"format_version": FORMAT["atmospherics"], "minecraft:atmosphere_settings": s}


def _day_weight(t: float) -> float:
    """1 around noon, fading to 0 by deep dusk (distance from noon 0.18 → 0.30)."""
    d = min(t, 1.0 - t)
    return max(0.0, min(1.0, (0.30 - d) / 0.12))


def _sky(colors: dict, fam: Family) -> dict:
    out = {}
    for t, c in colors.items():
        if fam.sky_mix:
            target, amount = fam.sky_mix
            c = mix(c, target, amount * _day_weight(t))
        out[t] = saturate(c, fam.sky_saturation)
    return keyframes(out)


def _overworld_atmosphere(look: Look, fam: Family, identifier: str) -> dict:
    return {
        "description": {"identifier": identifier},
        "horizon_blend_stops": {
            "min": look.blend_min,
            "start": keyframes(look.blend_start),
            "mie_start": keyframes(look.blend_mie_start),
            "max": look.blend_max,
        },
        "rayleigh_strength": keyframes(look.rayleigh),
        "sun_mie_strength": keyframes({t: min(1.5, x * fam.mie) for t, x in look.sun_mie.items()}),
        "moon_mie_strength": keyframes(look.moon_mie),
        "sun_glare_shape": keyframes(look.sun_glare),
        "sky_zenith_color": _sky(look.zenith, fam),
        "sky_horizon_color": _sky(look.horizon, fam),
    }


# -- color grading -------------------------------------------------------------

def _vec(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else [v, v, v]


def _band(band: dict) -> dict:
    return {k: (_vec(v) if k in ("contrast", "gain", "gamma", "offset", "saturation") else v)
            for k, v in band.items()}


def _color_grading(look: Look, entry) -> dict:
    name = family_name(entry.identifier, "color_grading")
    fam = family_for(look, name, entry.identifier)
    mid = dict(look.midtones)
    mid["saturation"] = round(mid["saturation"] * fam.saturation, 3)
    mid["contrast"] = round(mid["contrast"] * fam.contrast, 3)
    kelvin = look.temperature + ((fam.temperature - 6500) if fam.temperature else 0)
    return {
        "format_version": FORMAT["color_grading"],
        "minecraft:color_grading_settings": {
            "description": {"identifier": entry.identifier},
            "color_grading": {
                "midtones": _band(mid),
                "highlights": _band(look.highlights),
                "shadows": _band(look.shadows),
                "temperature": {"enabled": True, "temperature": max(1000, min(15000, kelvin)),
                                "type": "color_temperature"},
            },
            "tone_mapping": {"operator": look.tonemapper},
        },
    }


# -- water ---------------------------------------------------------------------

def _water(look: Look, entry) -> dict:
    return {
        "format_version": FORMAT["water"],
        "minecraft:water_settings": {"description": {"identifier": entry.identifier}, **copy.deepcopy(look.water)},
    }


# -- fog -----------------------------------------------------------------------

def fog_profile(identifier: str) -> str | None:
    name = identifier.split(":", 1)[1].removeprefix("fog_")
    for pattern, profile in FOG_RULES:
        if re.search(pattern, name):
            return profile
    return None


def _fog(look: Look, entry) -> dict | None:
    profile = fog_profile(entry.identifier)
    if profile is None:
        return None
    f: Fog = look.fogs[profile]
    doc = copy.deepcopy(entry.doc)
    doc["format_version"] = FORMAT["fogs"]
    doc["minecraft:fog_settings"]["volumetric"] = {
        "density": {
            "air": {"max_density": f.density, "max_density_height": f.max_height,
                    "zero_density_height": f.zero_height},
            "water": {"max_density": f.water_density, "uniform": True},
        },
        "media_coefficients": {
            "air": {"scattering": list(f.scattering), "absorption": list(f.absorption)},
            "water": {"scattering": list(f.water_scattering), "absorption": list(f.water_absorption)},
        },
        "henyey_greenstein_g": {"air": {"henyey_greenstein_g": f.g}, "water": {"henyey_greenstein_g": f.water_g}},
    }
    return doc


# -- helpers -------------------------------------------------------------------

def _map_colors(value, fn):
    """Apply fn to a color that may be hex, RGB, or keyframed."""
    if isinstance(value, dict):
        return {k: _map_colors(v, fn) for k, v in value.items()}
    if isinstance(value, str):
        return fn(hex_to_rgb(value))
    return fn(list(value[:3]))
