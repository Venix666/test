"""Read the vanilla reference pack (a Mojang/bedrock-samples checkout)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOTS = {
    "lighting": "minecraft:lighting_settings",
    "atmospherics": "minecraft:atmosphere_settings",
    "color_grading": "minecraft:color_grading_settings",
    "water": "minecraft:water_settings",
    "fogs": "minecraft:fog_settings",
}


@dataclass(frozen=True)
class Entry:
    filename: str
    identifier: str
    doc: dict


def load_json(path: Path) -> dict:
    """Load Mojang JSON, which may contain // comments."""
    text = path.read_text(encoding="utf-8-sig")
    text = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*', lambda m: m.group(1) or "", text)
    return json.loads(text)


class Vanilla:
    def __init__(self, root: Path):
        root = Path(root)
        self.pack = root / "resource_pack" if (root / "resource_pack").is_dir() else root
        if not (self.pack / "lighting").is_dir():
            raise FileNotFoundError(
                f"{self.pack} is not a vanilla resource pack (no lighting/). "
                "Run tools/fetch_vanilla.sh first."
            )

    def entries(self, folder: str) -> list[Entry]:
        """Every settings document in a Vibrant Visuals folder, sorted by filename."""
        root_key = ROOTS[folder]
        out = []
        for path in sorted((self.pack / folder).glob("*.json")):
            doc = load_json(path)
            if root_key not in doc:
                continue
            ident = doc[root_key]["description"]["identifier"]
            out.append(Entry(path.name, ident, doc))
        return out

    def known_blocks(self) -> set[str] | None:
        """Vanilla block names (no namespace) from blocks.json, or None if not fetched."""
        path = self.pack / "blocks.json"
        if not path.is_file():
            return None
        return {k for k in load_json(path) if k != "format_version"}

    def client_biomes(self) -> list[dict]:
        out = []
        for path in sorted((self.pack / "biomes").glob("*.client_biome.json")):
            out.append(load_json(path)["minecraft:client_biome"])
        return out
