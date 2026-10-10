#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# The frozen v1 site for /v1/ (M2.10; docs/v2/adr/0003-v1-archive.md), built
# from 9f58b83 -- the M0 merge: v1's views with M0's public fixes ("Live Stack
# (simulated)", no "real robot" for the Gazebo stack, the quiet Live probe) and
# no M1 code. Owner's ruling 2026-10-10 (docs/STATUS.md plan-change log): the
# tag coco-lab-v1-final (3571169) predates those fixes, so its build undid them
# at /v1/. The tag stays v1's freeze point.
#
#   lab_web/tools/build_v1_archive.sh OUT_DIR [WORK_DIR]
#
# Fetches that commit (depth 1, from this repository, which is only read), runs
# ITS OWN build exactly as its CI did -- build_catalog.py on its own
# coco_lab, `npm ci` on its own lockfile, `vite build` -- with the base path
# /coco-labs/v1/, runs its own dist check, and copies dist to OUT_DIR. Only
# the pinned commit is built.
#
# Needs: git with the commit (fetched here if missing), Node 24.21.x, and
# PYTHON (default python3) able to import coco_lab's requirements.
set -euo pipefail

SOURCE=9f58b8338f3364291bc1f85414c798c0c3527c7a
# absolute paths: the build below changes directory (a relative OUT_DIR once
# landed inside the clone, measured on PR #21's first CI run)
OUT=$(realpath -m "${1:?usage: build_v1_archive.sh OUT_DIR [WORK_DIR]}")
WORK=$(realpath -m "${2:-$(mktemp -d)}")
mkdir -p "$WORK"
PY=${PYTHON:-python3}
REPO=$(git rev-parse --show-toplevel)

# a shallow CI checkout may not hold it: fetch just that commit
if ! git -C "$REPO" cat-file -e "$SOURCE^{commit}" 2> /dev/null; then
  git -C "$REPO" fetch -q --depth 1 origin "$SOURCE"
fi

# a depth-1 copy of that commit: its build reads its own git metadata (the
# commit time stamps the catalog), and this repository is only read
SRC="$WORK/v1_src"
rm -rf "$SRC"
git init -q "$SRC"
git -C "$SRC" fetch -q --depth 1 "file://$REPO" "$SOURCE"
git -C "$SRC" -c advice.detachedHead=false checkout -q FETCH_HEAD
SHA=$(git -C "$SRC" rev-parse HEAD)
test "$SHA" = "$SOURCE"

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
echo "v1 archive: $SHA -> $OUT ($(du -sh "$OUT" | cut -f1))"
