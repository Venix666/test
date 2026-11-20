"""Checks against the pinned real vanilla pack (skipped until tools/fetch_vanilla.sh has run)."""

import logging

import pytest

from halcyon.gen import generate
from halcyon.limits import validate
from halcyon.style import PRESETS

KINDS = {
    "minecraft:atmosphere_identifier": ("atmosphere_identifier", "minecraft:atmosphere_settings"),
    "minecraft:color_grading_identifier": ("color_grading_identifier", "minecraft:color_grading_settings"),
    "minecraft:lighting_identifier": ("lighting_identifier", "minecraft:lighting_settings"),
    "minecraft:water_identifier": ("water_identifier", "minecraft:water_settings"),
}


@pytest.mark.parametrize("look", PRESETS.values(), ids=PRESETS.keys())
def test_every_biome_resolves_to_halcyon_settings(look, real_vanilla, caplog):
    with caplog.at_level(logging.WARNING):
        docs = generate(look, real_vanilla)
    assert not caplog.records, caplog.text  # every vanilla identifier has a family
    for doc in docs.values():
        validate(doc)

    provided = {}
    for doc in docs.values():
        root = next(k for k in doc if k.startswith("minecraft:"))
        provided.setdefault(root, set()).add(doc[root]["description"]["identifier"])

    for biome in real_vanilla.client_biomes():
        for component, (field, root) in KINDS.items():
            ref = biome["components"].get(component, {}).get(field)
            if ref:
                assert ref in provided[root], f"{biome['description']['identifier']} → {ref}"


def test_pbr_texture_sets_only_reference_files_in_the_pack(real_vanilla):
    import json

    from halcyon import pbr

    if not pbr.textures_root(real_vanilla).is_dir():
        pytest.skip("run HALCYON_WITH_TEXTURES=1 tools/fetch_vanilla.sh")
    files = pbr.generate(real_vanilla)
    sets = {k: json.loads(v) for k, v in files.items() if k.endswith(".texture_set.json")}
    assert len(sets) > 1000
    stems = {k.rsplit(".", 1)[0] for k in files}
    for path, doc in sets.items():
        folder = path.rsplit("/", 1)[0]
        for ref in doc["minecraft:texture_set"].values():
            assert f"{folder}/{ref}" in stems, f"{path} → {ref}"
