#!/usr/bin/env bash
# Fetch the pinned vanilla reference (Mojang/bedrock-samples) used by the build.
# Only the Vibrant Visuals config folders, client biomes, fogs and block textures are checked out.
set -euo pipefail

TAG="${HALCYON_VANILLA_TAG:-v1.26.60.5}"
DEST="${1:-.cache/bedrock-samples}"
REPO="https://github.com/Mojang/bedrock-samples"

if [ ! -d "$DEST/.git" ]; then
  mkdir -p "$(dirname "$DEST")"
  GIT_LFS_SKIP_SMUDGE=1 git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$TAG" \
    --filter=blob:none --sparse "$REPO" "$DEST"
else
  git -C "$DEST" fetch --quiet --depth 1 origin "refs/tags/$TAG:refs/tags/$TAG"
  git -C "$DEST" -c advice.detachedHead=false checkout --quiet "$TAG"
fi

git -C "$DEST" sparse-checkout set --no-cone \
  '/resource_pack/manifest.json' \
  '/resource_pack/atmospherics/' \
  '/resource_pack/color_grading/' \
  '/resource_pack/lighting/' \
  '/resource_pack/water/' \
  '/resource_pack/fogs/' \
  '/resource_pack/biomes/' \
  ${HALCYON_WITH_TEXTURES:+'/resource_pack/textures/blocks/'} \
  ${HALCYON_WITH_TEXTURES:+'/resource_pack/textures/terrain_texture.json'}

echo "vanilla reference: $DEST @ $(git -C "$DEST" describe --tags 2>/dev/null || echo "$TAG")"
