import pytest

from halcyon import lights
from halcyon.gen import generate
from halcyon.limits import ValidationError, validate
from halcyon.style import PRESETS, VIBRANT


def test_default_point_lights_stay_point_lights_with_new_colors():
    doc = lights.local_lighting()
    s = doc["minecraft:local_light_settings"]
    for name in ("torch", "lantern", "soul_torch", "end_rod", "candle", "red_candle", "copper_lantern"):
        assert s[f"minecraft:{name}"]["light_type"] == "point_light", name
    assert s["minecraft:glowstone"]["light_type"] == "static_light"
    assert s["minecraft:soul_torch"]["light_color"] != s["minecraft:torch"]["light_color"]


def test_dyed_candles_are_tinted_but_keep_full_strength():
    pal = lights.palette()
    red, blue = pal["red_candle"], pal["blue_candle"]
    assert red[0] > red[2] and blue[2] > pal["candle"][2]
    assert max(pal["black_candle"]) == 255


def test_unknown_blocks_are_dropped(caplog):
    doc = lights.local_lighting(known_blocks={"torch"})
    assert list(doc["minecraft:local_light_settings"]) == ["minecraft:torch"]
    assert "glowstone" in caplog.text


def test_light_saturation_zero_gives_neutral_light():
    s = lights.local_lighting(saturation=0.0)["minecraft:local_light_settings"]
    r, g, b = (int(s["minecraft:soul_torch"]["light_color"][i:i + 2], 16) for i in (1, 3, 5))
    assert max(r, g, b) - min(r, g, b) <= 1


@pytest.mark.parametrize("style,expected", [("soft", "soft_shadows"), ("blocky", "blocky_shadows")])
def test_shadow_styles(style, expected):
    doc = {"format_version": "1.21.80", **lights.shadows(style)}
    validate(doc)
    assert doc["minecraft:shadow_settings"]["shadow_style"] == expected


def test_bad_light_type_fails_validation():
    with pytest.raises(ValidationError):
        validate({"format_version": "1.21.120",
                  "minecraft:local_light_settings": {"minecraft:torch": {"light_type": "spot"}}})


@pytest.mark.parametrize("look", PRESETS.values(), ids=PRESETS.keys())
def test_pack_wide_consistency_rules(look, vanilla):
    """Mojang: orbital offset, tonemapper and caustics/waves can't blend between biomes."""
    docs = generate(look, vanilla)
    offsets = {d["minecraft:lighting_settings"]["directional_lights"]["orbital"]["orbital_offset_degrees"]
               for d in docs.values() if "minecraft:lighting_settings" in d}
    tonemappers = {d["minecraft:color_grading_settings"]["tone_mapping"]["operator"]
                   for d in docs.values() if "minecraft:color_grading_settings" in d}
    water = [d["minecraft:water_settings"] for d in docs.values() if "minecraft:water_settings" in d]
    assert len(offsets) == 1 and len(tonemappers) == 1
    assert len({str(w["caustics"]) for w in water}) == 1
    assert len({w["waves"]["enabled"] for w in water}) == 1


def test_fog_adds_underwater_light_shafts(vanilla):
    docs = generate(VIBRANT, vanilla)
    vol = docs["fogs/swampland_fog_setting.json"]["minecraft:fog_settings"]["volumetric"]
    clear = docs["fogs/plains_fog_setting.json"]["minecraft:fog_settings"]["volumetric"]
    assert vol["density"]["water"]["uniform"] is True
    assert vol["density"]["water"]["max_density"] > clear["density"]["water"]["max_density"]  # murky swamp
    assert clear["henyey_greenstein_g"]["water"]["henyey_greenstein_g"] > 0.8  # crisp shafts in clear water


def test_new_settings_files_are_generated(vanilla):
    docs = generate(VIBRANT, vanilla)
    assert docs["local_lighting/local_lighting.json"]["format_version"] == "1.21.120"
    assert docs["shadows/global.json"]["minecraft:shadow_settings"]["shadow_style"] == "soft_shadows"
    for doc in docs.values():
        validate(doc)
