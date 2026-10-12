#!/usr/bin/env bash
# M4.3: make the terrain sessions and measure what they exercise (CPython).
set -e
WT=/home/gautham/coco_labs_ws/src/coco-labs/.claude/worktrees/v2-m4-3d-arena
D=/home/gautham/coco_lab_m4_ws/m43_det
export PATH=/home/gautham/coco_v2_ws/node/node-v24.21.0-linux-x64/bin:/usr/bin:/bin
cd "$WT/lab_web"
node tools/perf/determinism.mjs make --out "$D" --terrain 1
cd "$WT/coco_lab"
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /home/gautham/coco_labs_ws/test_venv/bin/python \
  /home/gautham/coco_lab_m4_ws/bin/m43_coverage.py "$D/sessions.json" "$D/coverage_cpython.json"
