#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# Put the frozen v1 site at OUT_DIR for the Pages artifact (M3.0;
# docs/v2/adr/0003-v1-archive.md):
#
#   lab_web/tools/fetch_v1_site.sh OUT_DIR
#
# Fetches the orphan branch v1-site at ONE PINNED COMMIT (depth 1; never the
# branch tip), checks every file against its SHA256SUMS and the tree hash
# pinned here (lab_web/tools/v1_site.py verify), and copies it to OUT_DIR,
# SHA256SUMS and V1_SITE.json included (served as the archive's provenance).
# Nothing is built. Changing
# the archive means a new v1-site commit AND a change to the two pins below,
# reviewed like any other change.
set -euo pipefail

V1_SITE_COMMIT=36e65003d37d9be246110c2dd2c27944aabed193
V1_SITE_TREE=6857ff56a2646c0772a2b7780e50f2e1eb910ae289ae3a222fdab6ee9b2bde2b

OUT=$(realpath -m "${1:?usage: fetch_v1_site.sh OUT_DIR}")
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(git -C "$HERE" rev-parse --show-toplevel)
PY=${PYTHON:-python3}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

if ! git -C "$REPO" cat-file -e "$V1_SITE_COMMIT^{commit}" 2> /dev/null; then
  git -C "$REPO" fetch -q --depth 1 origin "$V1_SITE_COMMIT"
fi
git -C "$REPO" archive "$V1_SITE_COMMIT" | tar -x -C "$WORK"
"$PY" "$HERE/v1_site.py" verify "$WORK" --expect-tree "$V1_SITE_TREE"

rm -rf "$OUT"
mkdir -p "$(dirname "$OUT")"
cp -r "$WORK" "$OUT"
test -f "$OUT/index.html" || { echo "refusing: no $OUT/index.html" >&2; exit 3; }
echo "v1 site: v1-site@$V1_SITE_COMMIT (tree $V1_SITE_TREE) -> $OUT ($(du -sh "$OUT" | cut -f1))"
