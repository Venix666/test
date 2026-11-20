"""Validation against the ranges documented in Mojang's bedrock-samples docs.

Every generated document goes through `validate()`; any problem fails the build.
"""

from __future__ import annotations

import re

TONEMAPPERS = {"aces", "hable", "reinhard", "reinhard_luma", "reinhard_luminance", "generic"}
TEMPERATURE_TYPES = {"white_balance", "color_temperature"}
_IDENT = re.compile(r"^[a-z0-9_.\-]+:[a-z0-9_.\-/]+$")


class ValidationError(ValueError):
    pass


def validate(doc: dict) -> None:
    errors: list[str] = []
    _Checker(errors).document(doc)
    if errors:
        raise ValidationError("; ".join(errors))


class _Checker:
    def __init__(self, errors: list[str]):
        self.errors = errors

    # -- primitives -------------------------------------------------------
    def fail(self, path: str, msg: str) -> None:
        self.errors.append(f"{path}: {msg}")

    def number(self, path, v, lo, hi):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            self.fail(path, f"expected number, got {v!r}")
        elif not lo <= v <= hi:
            self.fail(path, f"{v} outside [{lo}, {hi}]")

    def color(self, path, v):
        if isinstance(v, str):
            if not re.fullmatch(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{8})", v):
                self.fail(path, f"bad hex color {v!r}")
            return
        if not isinstance(v, list) or len(v) not in (3, 4):
            self.fail(path, f"expected RGB list, got {v!r}")
            return
        for i, c in enumerate(v):
            self.number(f"{path}[{i}]", c, 0, 255)

    def keyed(self, path, v, check):
        """A value that may be a constant or a {time: value} keyframe dict."""
        if isinstance(v, dict):
            if not v:
                self.fail(path, "empty keyframes")
            for k, x in v.items():
                try:
                    t = float(k)
                except ValueError:
                    self.fail(path, f"keyframe key {k!r} is not a number")
                    continue
                if not 0.0 <= t <= 1.0:
                    self.fail(path, f"keyframe time {t} outside [0, 1]")
                check(f"{path}[{k}]", x)
        else:
            check(path, v)

    def vec3(self, path, v, lo, hi):
        if not isinstance(v, list) or len(v) != 3:
            self.fail(path, f"expected 3 numbers, got {v!r}")
            return
        for i, x in enumerate(v):
            self.number(f"{path}[{i}]", x, lo, hi)

    def identifier(self, path, settings):
        ident = settings.get("description", {}).get("identifier")
        if not isinstance(ident, str) or not _IDENT.match(ident):
            self.fail(path, f"identifier must be namespaced, got {ident!r}")

    def version(self, doc):
        fv = doc.get("format_version")
        if not isinstance(fv, str) or not re.fullmatch(r"\d+\.\d+\.\d+", fv):
            self.fail("format_version", f"expected 'x.y.z', got {fv!r}")

    # -- documents --------------------------------------------------------
    def document(self, doc):
        handlers = {
            "minecraft:lighting_settings": self.lighting,
            "minecraft:atmosphere_settings": self.atmosphere,
            "minecraft:color_grading_settings": self.color_grading,
            "minecraft:water_settings": self.water,
            "minecraft:fog_settings": self.fog,
        }
        roots = [k for k in doc if k in handlers]
        if len(roots) != 1:
            self.fail("document", f"expected exactly one settings root, found {roots}")
            return
        self.version(doc)
        settings = doc[roots[0]]
        self.identifier(roots[0], settings)
        handlers[roots[0]](roots[0], settings)

    def lighting(self, p, s):
        dl = s.get("directional_lights", {})
        orbital = dl.get("orbital", {})
        for body in ("sun", "moon"):
            light = orbital.get(body)
            if light is None:
                continue
            bp = f"{p}.orbital.{body}"
            if "illuminance" in light:
                self.keyed(f"{bp}.illuminance", light["illuminance"],
                           lambda q, x: self.number(q, x, 0.0, 200000.0))
            if "color" in light:
                self.keyed(f"{bp}.color", light["color"], self.color)
        if "orbital_offset_degrees" in orbital:
            self.keyed(f"{p}.orbital_offset_degrees", orbital["orbital_offset_degrees"],
                       lambda q, x: self.number(q, x, -90.0, 90.0))
        flash = dl.get("flash")
        if flash:
            self.number(f"{p}.flash.illuminance", flash.get("illuminance", 0), 0.0, 200000.0)
            if "color" in flash:
                self.color(f"{p}.flash.color", flash["color"])
        if "emissive" in s:
            self.number(f"{p}.emissive.desaturation", s["emissive"].get("desaturation", 0), 0.0, 1.0)
        if "ambient" in s:
            amb = s["ambient"]
            for key in ("color", "illuminance"):
                if key not in amb:
                    self.fail(f"{p}.ambient", f"missing required {key}")
            if "color" in amb:
                self.keyed(f"{p}.ambient.color", amb["color"], self.color)
            if "illuminance" in amb:
                self.keyed(f"{p}.ambient.illuminance", amb["illuminance"],
                           lambda q, x: self.number(q, x, 0.0, 5.0))
        if "sky" in s:
            self.keyed(f"{p}.sky.intensity", s["sky"].get("intensity", 1.0),
                       lambda q, x: self.number(q, x, 0.1, 1.0))

    def atmosphere(self, p, s):
        for key in ("rayleigh_strength", "sun_mie_strength", "moon_mie_strength", "sun_glare_shape"):
            if key in s:
                self.keyed(f"{p}.{key}", s[key], lambda q, x: self.number(q, x, 0.0, 100.0))
        for key in ("sky_zenith_color", "sky_horizon_color"):
            if key in s:
                self.keyed(f"{p}.{key}", s[key], self.color)
        for key, v in s.get("horizon_blend_stops", {}).items():
            if key not in ("min", "start", "mie_start", "max"):
                self.fail(f"{p}.horizon_blend_stops", f"unknown stop {key!r}")
            self.keyed(f"{p}.horizon_blend_stops.{key}", v, lambda q, x: self.number(q, x, 0.0, 1.0))

    def color_grading(self, p, s):
        cg = s.get("color_grading", {})
        for band in ("midtones", "highlights", "shadows"):
            b = cg.get(band)
            if b is None:
                continue
            bp = f"{p}.{band}"
            for key, (lo, hi) in {"contrast": (0, 4), "gain": (0, 10), "gamma": (0, 4),
                                  "offset": (0, 4), "saturation": (0, 10)}.items():
                if key in b:
                    self.vec3(f"{bp}.{key}", b[key], lo, hi)
            if "highlightsMin" in b:
                self.number(f"{bp}.highlightsMin", b["highlightsMin"], 1.0, 4.0)
            if "shadowsMax" in b:
                self.number(f"{bp}.shadowsMax", b["shadowsMax"], 0.1, 1.0)
        t = cg.get("temperature")
        if t:
            self.number(f"{p}.temperature", t.get("temperature", 6500), 1000, 15000)
            if t.get("type", "color_temperature") not in TEMPERATURE_TYPES:
                self.fail(f"{p}.temperature.type", f"unknown type {t.get('type')!r}")
        op = s.get("tone_mapping", {}).get("operator")
        if op is not None and op not in TONEMAPPERS:
            self.fail(f"{p}.tone_mapping.operator", f"unknown operator {op!r}")

    def water(self, p, s):
        pc = s.get("particle_concentrations", {})
        for key, hi in {"chlorophyll": 10.0, "cdom": 15.0, "suspended_sediment": 300.0}.items():
            if key in pc:
                self.number(f"{p}.particle_concentrations.{key}", pc[key], 0.0, hi)
        if "biome_water_color_contribution" in s:
            self.number(f"{p}.biome_water_color_contribution", s["biome_water_color_contribution"], 0.0, 1.0)
        ca = s.get("caustics", {})
        for key, (lo, hi) in {"frame_length": (0.01, 5.0), "power": (1, 6), "scale": (0.1, 5.0)}.items():
            if key in ca:
                self.number(f"{p}.caustics.{key}", ca[key], lo, hi)
        wv = s.get("waves", {})
        ranges = {"depth": (0.0, 3.0), "direction_increment": (0.0, 360.0), "frequency": (0.01, 3.0),
                  "frequency_scaling": (0.0, 2.0), "mix": (0.0, 1.0), "octaves": (1, 30),
                  "pull": (-1.0, 1.0), "shape": (1.0, 10.0), "speed": (0.01, 10.0),
                  "speed_scaling": (0.0, 2.0)}
        for key, (lo, hi) in ranges.items():
            if key in wv:
                self.number(f"{p}.waves.{key}", wv[key], lo, hi)
        if "octaves" in wv and not isinstance(wv["octaves"], int):
            self.fail(f"{p}.waves.octaves", "must be an integer")

    def fog(self, p, s):
        vol = s.get("volumetric")
        if not vol:
            return
        d = vol.get("density", {}).get("air")
        if d:
            self.number(f"{p}.density.max_density", d.get("max_density", 0), 0.0, 1.0)
            lo, hi = d.get("max_density_height", 0), d.get("zero_density_height", 0)
            self.number(f"{p}.density.max_density_height", lo, -64, 320)
            self.number(f"{p}.density.zero_density_height", hi, -64, 320)
            if hi < lo:
                self.fail(f"{p}.density", "zero_density_height below max_density_height")
        m = vol.get("media_coefficients", {}).get("air")
        if m:
            self.vec3(f"{p}.media.scattering", m.get("scattering"), 0.0, 1.0)
            self.vec3(f"{p}.media.absorption", m.get("absorption"), 0.0, 1.0)
        g = vol.get("henyey_greenstein_g", {}).get("air")
        if g:
            self.number(f"{p}.henyey_greenstein_g", g.get("henyey_greenstein_g"), -1.0, 1.0)
