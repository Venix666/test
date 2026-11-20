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
