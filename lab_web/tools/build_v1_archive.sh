#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# The frozen v1 site, built from the tag coco-lab-v1-final, for /v1/ (M2.10;
# docs/v2/adr/0003-v1-archive.md).
#
#   lab_web/tools/build_v1_archive.sh OUT_DIR [WORK_DIR]
#
# Clones the tag (depth 1, from this repository, which is only read), runs
# ITS OWN build exactly as its CI did -- build_catalog.py on its own
# coco_lab, `npm ci` on its own lockfile, `vite build` -- with the base path
# /coco-labs/v1/, runs its own dist check, and copies dist to OUT_DIR. The
# tag must be the frozen commit; anything else is refused.
#
# Needs: git with the tag (fetched here if missing), Node 24.21.x, and
# PYTHON (default python3) able to import coco_lab's requirements.
set -euo pipefail

TAG=coco-lab-v1-final
FROZEN=35711693d11da99218fa85050db60c6e10462bd2
# absolute paths: the build below changes directory (a relative OUT_DIR once
# landed inside the clone, measured on PR #21's first CI run)
OUT=$(realpath -m "${1:?usage: build_v1_archive.sh OUT_DIR [WORK_DIR]}")
WORK=$(realpath -m "${2:-$(mktemp -d)}")
mkdir -p "$WORK"
PY=${PYTHON:-python3}
REPO=$(git rev-parse --show-toplevel)

if ! git -C "$REPO" rev-parse -q --verify "refs/tags/$TAG" > /dev/null; then
  git -C "$REPO" fetch --depth 1 origin "refs/tags/$TAG:refs/tags/$TAG"
fi
SHA=$(git -C "$REPO" rev-list -n 1 "$TAG")
if [ "$SHA" != "$FROZEN" ]; then
  echo "refusing: $TAG is $SHA, not the frozen $FROZEN" >&2
  exit 2
fi

# a depth-1 clone at the tag: its build reads its own git metadata (the
# commit time stamps the catalog), and this repository is only read
SRC="$WORK/v1_src"
rm -rf "$SRC"
git -c advice.detachedHead=false clone -q --depth 1 --branch "$TAG" "file://$REPO" "$SRC"
test "$(git -C "$SRC" rev-parse HEAD)" = "$FROZEN"

cd "$SRC"
PYTHONPATH="$SRC/coco_lab" PYTHONDONTWRITEBYTECODE=1 "$PY" lab_web/tools/build_catalog.py > "$WORK/v1_catalog.log"
cd "$SRC/lab_web"
npm ci --no-audit --no-fund > "$WORK/v1_npm.log" 2>&1
LAB_BASE=/coco-labs/v1/ npm run build > "$WORK/v1_build.log" 2>&1
node tools/check_dist.mjs > "$WORK/v1_check_dist.json"

rm -rf "$OUT"
mkdir -p "$(dirname "$OUT")"
cp -r dist "$OUT"
test -f "$OUT/index.html" || { echo "refusing: no $OUT/index.html after the copy" >&2; exit 3; }
echo "v1 archive: $TAG = $SHA -> $OUT ($(du -sh "$OUT" | cut -f1))"
