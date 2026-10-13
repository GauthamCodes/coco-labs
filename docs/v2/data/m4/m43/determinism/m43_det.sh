#!/usr/bin/env bash
# M4.3: the 100 terrain sessions on four engines, then compare.
WT=/home/gautham/coco_labs_ws/src/coco-labs/.claude/worktrees/v2-m4-3d-arena
D=/home/gautham/coco_lab_m4_ws/m43_det
SITE=http://127.0.0.1:4244/coco-labs/
export PATH=/home/gautham/coco_v2_ws/node/node-v24.21.0-linux-x64/bin:/usr/bin:/bin
cd "$WT/lab_web" || exit 1
echo "start $(date -Is) profile $(powerprofilesctl get) AC $(cat /sys/class/power_supply/ACAD/online) load $(cut -d' ' -f1-3 /proc/loadavg) driver $(cat /proc/driver/nvidia/version 2>/dev/null | head -1 | cut -c1-80)"
node tools/perf/determinism.mjs node --out "$D"; echo "node exit=$?"
node tools/perf/determinism.mjs chromium --out "$D" --site $SITE; echo "chromium exit=$?"
node tools/perf/determinism.mjs firefox --out "$D" --site $SITE; echo "firefox exit=$?"
LD_LIBRARY_PATH="$HOME/coco_lab_m1_ws/webkit_libs/root/usr/lib/x86_64-linux-gnu" \
  node tools/perf/determinism.mjs webkit --out "$D" --site $SITE --webkit-exe "$HOME/coco_lab_m2_ws/bin/webkit_mesa.sh"
echo "webkit exit=$?"
node tools/perf/determinism.mjs compare --out "$D"; echo "compare exit=$?"
echo "end $(date -Is) profile $(powerprofilesctl get) AC $(cat /sys/class/power_supply/ACAD/online) load $(cut -d' ' -f1-3 /proc/loadavg)"
