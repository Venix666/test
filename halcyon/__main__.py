"""CLI: python -m halcyon {build,preview}."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .style import PRESETS

DEFAULT_VANILLA = Path(".cache/bedrock-samples")


def _presets(name: str):
    return list(PRESETS.values()) if name == "all" else [PRESETS[name]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="halcyon", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    choices = ["all", *PRESETS]

    b = sub.add_parser("build", help="generate the .mcpack files")
    b.add_argument("--vanilla", type=Path, default=DEFAULT_VANILLA,
                   help="Mojang/bedrock-samples checkout (see tools/fetch_vanilla.sh)")
    b.add_argument("--preset", choices=choices, default="all")
    b.add_argument("--out", type=Path, default=Path("dist"))
    b.add_argument("--no-pbr", action="store_true", help="skip the PBR add-on pack")
    b.add_argument("--no-glowing-ores", action="store_true", help="PBR pack without ore glow")

    p = sub.add_parser("preview", help="render day-cycle preview PNGs")
    p.add_argument("--preset", choices=choices, default="all")
    p.add_argument("--out", type=Path, default=Path("docs/previews"))
    p.add_argument("--vanilla", type=Path, default=DEFAULT_VANILLA,
                   help="also render the PBR contact sheet when block textures are present")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "build":
        from .pack import build_pack
        from .vanilla import Vanilla

        vanilla = Vanilla(args.vanilla)
        for look in _presets(args.preset):
            print(build_pack(look, vanilla, args.out))
        if not args.no_pbr:
            if _has_textures(vanilla):
                from .pack import build_pbr_pack

                print(build_pbr_pack(vanilla, args.out, glowing_ores=not args.no_glowing_ores))
            else:
                logging.warning("no block textures: skipping PBR pack "
                                "(run HALCYON_WITH_TEXTURES=1 tools/fetch_vanilla.sh)")
    else:
        from .preview import render, render_pbr
        from .vanilla import Vanilla

        for look in _presets(args.preset):
            print(render(look, args.out / f"{look.name}.png"))
        try:
            vanilla = Vanilla(args.vanilla)
        except FileNotFoundError:
            vanilla = None
        if vanilla is not None and _has_textures(vanilla):
            print(render_pbr(vanilla, args.out / "pbr.png"))
    return 0


def _has_textures(vanilla) -> bool:
    return (vanilla.pack / "textures" / "blocks").is_dir()


if __name__ == "__main__":
    sys.exit(main())
