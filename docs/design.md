# Halcyon Visuals — Design

## Intent
A Bedrock Vibrant Visuals pack that rivals top Java shader packs in mood and color,
while staying official, cross-platform and update-proof.

## Approaches considered
1. **Data-driven Vibrant Visuals pack (chosen).** Lighting, atmospherics, color grading,
   volumetric fog, water and PBR texture sets through Mojang's documented JSON. Works on
   all Vibrant Visuals platforms and Marketplace-style distribution; limited to the knobs
   Mojang exposes.
2. **Injected RenderDragon materials** (BetterRenderDragon + compiled `.material.bin`).
   Full shader control, but Windows only, unofficial and rebuilt every game update.
   Kept as Phase 5 research.
3. **Hand-written JSON.** Hundreds of files, inconsistent by biome, painful to tune.
   Rejected in favor of a generator with one style source of truth.

## Key decisions
- **Override by identifier.** Every vanilla Vibrant Visuals identifier (`minecraft:*_lighting`,
  `*_atmospherics`, `*_color_grading`, `default_water`, biome fogs) is redefined with the
  same identifier and filename. Vanilla `client_biome` files stay untouched, so sounds,
  music and colors keep working and the pack survives new biomes.
- **Vanilla reference at build time.** The build reads `Mojang/bedrock-samples` (pinned tag)
  to discover identifiers, fog distance settings and Nether/End baselines. No Mojang files
  are committed to this repo.
- **Unknown future identifiers** fall back to the default family with a warning instead of
  failing the build.
- **Validation** mirrors the documented ranges; out-of-range values fail the build.
- **Presets** are separate packs with their own deterministic UUIDs (subpacks are Phase 4,
  pending in-game verification).
- **PBR is a separate add-on pack.** Texture sets may only reference images in their own pack,
  so the PBR pack carries copies of the vanilla color and MERS images next to the generated
  heightmaps. Keeping it separate lets the atmosphere presets work with any texture pack.
  Built `.mcpack` files therefore contain Mojang textures; the repository does not.
- **Vanilla MERS is kept.** Mojang already authors metalness, roughness, subsurface and
  light-source emissive per block; Halcyon only adds heightmaps and the faint ore glow.

- **Colored light uses shared families.** Mojang recommends reusing few light colors for
  performance; 106 blocks map to 42 colors. Block ids are checked against vanilla
  `blocks.json` (note legacy ids such as `seaLantern`). Point lights stay limited to the
  built-in set plus the conduit, because they are expensive on mobile.
- **Optional looks ship as tiny add-ons** (Pixel Shadows) stacked above a preset, so players
  toggle them without a rebuild.

## Format facts (bedrock-samples v1.26.60.5 + MicrosoftDocs/minecraft-creator)
- Manifest: `"capabilities": ["pbr"]`, `min_engine_version` ≥ 1.21.120.
- Keyframe time is a 0–1 day fraction: 0.0 noon, 0.25 sunset, 0.5 midnight, 0.75 sunrise.
  Vanilla hands the shadow caster from sun to moon at 0.292 / 0.708.
- `color_temperature` grading: higher Kelvin → cooler image (vanilla desert 4400 K,
  ice spikes 11000 K). The docs' wording is inverted; vanilla data is authoritative.
- Format versions used: lighting 1.26.0 (keyframed ambient/sky), atmospherics 1.21.40,
  color grading 1.21.90, fog 1.21.90 (`volumetric` air + water media), water 1.26.0
  (`biome_water_color_contribution`), local lighting 1.21.120, shadows 1.21.80,
  texture sets 1.21.30 (`metalness_emissive_roughness_subsurface`). Packs need
  `min_engine_version` 1.26.0.
- Can't blend between biomes, so must match pack-wide: tonemapper, orbital offset,
  water caustics, waves on/off.
- Volumetric absorption uses only the luminance of the RGB value.
- Volumetric fog: `density.air {max_density, max_density_height, zero_density_height}`,
  `media_coefficients.air {scattering, absorption}`, `henyey_greenstein_g.air`.

## Left to the builder / in-game tuning
Exact numbers are a first pass tuned from vanilla baselines and preview renders; they need
an in-game pass (Phase 3) on real hardware.
