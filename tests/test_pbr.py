import io
import json

import numpy as np
import pytest
from PIL import Image

from halcyon.pbr import generate, heightmap, rule_for
from halcyon.vanilla import Vanilla


def _save(path, arr, mode, fmt="PNG"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype(np.uint8), mode).save(path, fmt)


def _texture_set(path, **layers):
    path.write_text(json.dumps({"format_version": "1.21.30", "minecraft:texture_set": layers}))


@pytest.fixture
def pack(tmp_path):
    rp = tmp_path / "resource_pack"
    (rp / "lighting").mkdir(parents=True)
    blocks = rp / "textures" / "blocks"
    stone = np.full((16, 16, 4), 128, np.uint8)
    stone[..., 3] = 255
    stone[4:8, 4:8, :3] = 60  # a dark pit
    _save(blocks / "stone.png", stone, "RGBA")
    _save(blocks / "stone_mers.tga", np.full((16, 16, 4), 100, np.uint8), "RGBA", "TGA")
    _texture_set(blocks / "stone.texture_set.json", color="stone",
                 metalness_emissive_roughness_subsurface="stone_mers")

    ore = stone.copy()
    ore[10:12, 10:12, :3] = [40, 220, 230]  # diamond speck
    _save(blocks / "deep" / "diamond_ore.png", ore, "RGBA")
    _save(blocks / "deep" / "diamond_ore_mers.tga", np.zeros((16, 16, 3), np.uint8), "RGB", "TGA")
    _texture_set(blocks / "deep" / "diamond_ore.texture_set.json", color="diamond_ore",
                 metalness_emissive_roughness_subsurface="diamond_ore_mers")

    _save(blocks / "lava_still.png", stone, "RGBA")
    _texture_set(blocks / "lava_still.texture_set.json", color="lava_still", normal="lava_still_normal")
    return Vanilla(tmp_path)


def _img(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_heightmap_follows_luma_and_flattens_transparency():
    rgba = np.full((4, 4, 4), 200, np.uint8)
    rgba[0, 0, :3] = 50
    rgba[3, 3, 3] = 0
    h = heightmap(rgba, rule_for("stone"))
    assert h[0, 0] < h[1, 1]
    assert h[3, 3] == 128


def test_flat_materials_get_a_narrower_range_than_rough_ones():
    rgba = np.random.default_rng(1).integers(0, 255, (16, 16, 4), dtype=np.uint8)
    rgba[..., 3] = 255
    flat, rough = heightmap(rgba, rule_for("glass")), heightmap(rgba, rule_for("cobblestone"))
    assert np.ptp(flat) < np.ptp(rough) / 3


@pytest.mark.parametrize("name,source", [("brick", "saturation"), ("diamond_ore", "ore"),
                                         ("deepslate/deepslate_gold_ore", "ore"), ("stone", "luma")])
def test_rules(name, source):
    assert rule_for(name).source == source


def test_texture_sets_gain_heightmaps_and_keep_vanilla_layers(pack):
    files = generate(pack)
    ts = json.loads(files["textures/blocks/stone.texture_set.json"])
    assert ts["format_version"] == "1.21.30"
    assert ts["minecraft:texture_set"] == {
        "color": "stone", "metalness_emissive_roughness_subsurface": "stone_mers", "heightmap": "stone_heightmap"}
    vanilla_dir = pack.pack / "textures" / "blocks"
    assert files["textures/blocks/stone.png"] == (vanilla_dir / "stone.png").read_bytes()
    assert files["textures/blocks/stone_mers.tga"] == (vanilla_dir / "stone_mers.tga").read_bytes()
    h = _img(files["textures/blocks/stone_heightmap.png"])
    assert h.mode == "L" and h.size == (16, 16)
    assert np.array(h)[5, 5] < np.array(h)[0, 0]  # the dark pit is recessed


def test_blocks_with_vanilla_normals_are_left_alone(pack):
    assert not any("lava_still" in k for k in generate(pack))


def test_ore_specks_glow_and_mers_mode_is_kept(pack):
    files = generate(pack)
    mers = _img(files["textures/blocks/deep/diamond_ore_mers.tga"])
    assert mers.mode == "RGB"
    g = np.array(mers)[..., 1]
    assert g[10, 10] > 0 and g[0, 0] == 0
    height = np.array(_img(files["textures/blocks/deep/diamond_ore_heightmap.png"]))
    assert height[10, 10] > height[0, 0]  # specks protrude


def test_glowing_ores_can_be_disabled(pack):
    files = generate(pack, glowing_ores=False)
    original = (pack.pack / "textures" / "blocks" / "deep" / "diamond_ore_mers.tga").read_bytes()
    assert files["textures/blocks/deep/diamond_ore_mers.tga"] == original
