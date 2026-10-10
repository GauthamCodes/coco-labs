#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# Build the frozen v1 site from source, self-contained (M3.0;
# docs/v2/adr/0003-v1-archive.md):
#
#   lab_web/tools/build_v1_site.sh OUT_DIR [WORK_DIR]
#
# 1. build_v1_archive.sh builds 9f58b83 with that commit's own tooling;
# 2. v1_site.py assemble self-hosts Pyodide (the pinned npm package, plus the
#    micropip wheel fetched once from the pinned CDN directory and checked
#    against pyodide-lock.json) and writes V1_SITE.json and SHA256SUMS.
#
# Run once to make the orphan branch v1-site, and weekly by
# .github/workflows/v1_reproducible.yml to check the build still reproduces.
# Needs: Node 24.21.x, lab_web's npm ci (for node_modules/pyodide), curl, and
# PYTHON (default python3) able to import coco_lab's requirements.
set -euo pipefail

OUT=$(realpath -m "${1:?usage: build_v1_site.sh OUT_DIR [WORK_DIR]}")
WORK=$(realpath -m "${2:-$(mktemp -d)}")
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PY=${PYTHON:-python3}
mkdir -p "$WORK"

"$HERE/build_v1_archive.sh" "$WORK/dist" "$WORK/archive"

PYODIDE_DIR="$HERE/../node_modules/pyodide"
WHEELS="$WORK/wheels"
mkdir -p "$WHEELS"
# the wheels the v1 worker loads beyond the core, named by the lock (v1_site.py checks each sha256)
for f in $("$PY" -c "import json,sys; sys.path.insert(0, '$HERE'); import v1_site as V; print(' '.join(n for n, _ in V.wheels_needed(json.load(open('$PYODIDE_DIR/pyodide-lock.json')))))"); do
  curl -sfL -o "$WHEELS/$f" "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/$f"
done

rm -rf "$OUT"
"$PY" "$HERE/v1_site.py" assemble "$WORK/dist" "$OUT" --pyodide "$PYODIDE_DIR" --wheels "$WHEELS"
