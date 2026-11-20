import json
import logging
import zipfile

import pytest

from halcyon.gen import fog_profile, generate
from halcyon.limits import validate
from halcyon.pack import build_pack, manifest
from halcyon.style import CINEMATIC, PRESETS, VIBRANT


@pytest.mark.parametrize("look", PRESETS.values(), ids=PRESETS.keys())
def test_every_vanilla_identifier_is_overridden_in_place(look, vanilla):
    docs = generate(look, vanilla)
    for folder in ("lighting", "atmospherics", "color_grading", "water"):
        for entry in vanilla.entries(folder):
            doc = docs[f"{folder}/{entry.filename}"]
            root = next(k for k in doc if k.startswith("minecraft:"))
            assert doc[root]["description"]["identifier"] == entry.identifier
    for doc in docs.values():
        validate(doc)


def test_fog_gets_volumetrics_and_keeps_distance(vanilla):
    docs = generate(VIBRANT, vanilla)
    plains = docs["fogs/plains_fog_setting.json"]["minecraft:fog_settings"]
    assert plains["distance"]["water"]["fog_end"] == 60.0
    assert plains["volumetric"]["henyey_greenstein_g"]["air"]["henyey_greenstein_g"] > 0.5  # god rays
    assert docs["fogs/plains_fog_setting.json"]["format_version"] == "1.21.90"
    assert "fogs/hell_fog_setting.json" not in docs  # Nether fog stays vanilla


@pytest.mark.parametrize("ident,profile", [
    ("minecraft:fog_plains", "temperate"),
    ("minecraft:fog_frozen_ocean", "cold"),
    ("minecraft:fog_deep_warm_ocean", "ocean"),
    ("minecraft:fog_mangrove_swamp", "swamp"),
    ("minecraft:fog_roofed_forest_mutated", "dark_forest"),
    ("minecraft:fog_the_end", "end"),
    ("minecraft:fog_pale_garden", None),
    ("minecraft:fog_crimson_forest", None),
])
def test_fog_profiles(ident, profile):
    assert fog_profile(ident) == profile


def test_nether_lighting_is_derived_in_orbital_layout(vanilla):
    doc = generate(VIBRANT, vanilla)["lighting/nether_lighting.json"]
    s = doc["minecraft:lighting_settings"]
    assert doc["format_version"] == "1.21.80"
    assert set(s["directional_lights"]["orbital"]) >= {"sun", "moon"}
    assert "sun" not in s["directional_lights"]
    r, g, b = s["ambient"]["color"]
    assert r > g > b  # warm Nether ambience
    assert s["ambient"]["illuminance"] == 0.5  # vanilla brightness kept


def test_unknown_identifier_falls_back_with_warning(vanilla, caplog):
    with caplog.at_level(logging.WARNING):
        docs = generate(VIBRANT, vanilla)
    assert "future_biome_lighting" in caplog.text
    s = docs["lighting/future_biome_lighting.json"]["minecraft:lighting_settings"]
    assert s["description"]["identifier"] == "minecraft:future_biome_lighting"
    assert "orbital" in s["directional_lights"]


def test_family_temperature_is_relative_to_preset(vanilla):
    docs = generate(VIBRANT, vanilla)
    temp = lambda f: docs[f"color_grading/{f}"]["minecraft:color_grading_settings"]["color_grading"]["temperature"]["temperature"]
    assert temp("cold_color_grading.json") > temp("color_grading.json") == VIBRANT.temperature


def test_manifest_requires_vibrant_visuals_and_has_stable_uuids():
    m = manifest(VIBRANT, "1.2.3")
    assert m["capabilities"] == ["pbr"]
    assert m["header"]["min_engine_version"] >= [1, 21, 120]
    assert m["header"]["version"] == [1, 2, 3]
    assert m == manifest(VIBRANT, "1.2.3")
    ids = {manifest(VIBRANT)["header"]["uuid"], manifest(CINEMATIC)["header"]["uuid"],
           manifest(VIBRANT)["modules"][0]["uuid"]}
    assert len(ids) == 3


def test_mcpack_archive_is_loadable(vanilla, tmp_path):
    archive = build_pack(VIBRANT, vanilla, tmp_path, version="0.0.1")
    with zipfile.ZipFile(archive) as z:
        names = set(z.namelist())
        assert {"manifest.json", "pack_icon.png", "lighting/global.json", "water/water.json"} <= names
        for name in names - {"manifest.json", "pack_icon.png"}:
            validate(json.loads(z.read(name)))
    assert (tmp_path / "Halcyon-Vibrant" / "manifest.json").is_file()
