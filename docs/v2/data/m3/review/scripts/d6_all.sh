#!/bin/bash
# A.3 (D6): every Case File's first frame on emulated 4G, the final ordered-layout build
# (the M3 worktree's dist, served on 4214), GPU, balanced on AC; then once unthrottled.
export PATH=/home/gautham/coco_v2_ws/node/node-v24.21.0-linux-x64/bin:/usr/bin:/bin
OUT=/home/gautham/review/m3_tmp/d6_all
WEB=/home/gautham/coco_labs_ws/src/coco-labs/.claude/worktrees/v2-m3-play-casefiles/lab_web
ORIG=$(powerprofilesctl get)
restore() { powerprofilesctl set "$ORIG"; echo "profile restored to $(powerprofilesctl get)"; }
trap restore EXIT
[ "$(cat /sys/class/power_supply/ACAD/online)" = "1" ] || { echo "NOT ON AC - abort"; exit 2; }
powerprofilesctl set balanced
sleep 20
echo "start $(date -Is): profile $(powerprofilesctl get) AC 1 load $(cut -d' ' -f1-3 /proc/loadavg) driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader)"
cd "$WEB" || exit 1
mkdir -p "$OUT"
node tools/perf/casefile_check.mjs --site http://127.0.0.1:4214/coco-labs/ --out "$OUT" --throttle 4g --gpu 1 > "$OUT/4g.log" 2>&1; echo "4g exit=$?"; tail -1 "$OUT/4g.log"
[ "$(cat /sys/class/power_supply/ACAD/online)" = "1" ] || echo "AC LOST during the 4g run"
node tools/perf/casefile_check.mjs --site http://127.0.0.1:4214/coco-labs/ --out "$OUT" --throttle none --gpu 1 > "$OUT/none.log" 2>&1; echo "none exit=$?"; tail -1 "$OUT/none.log"
echo "end $(date -Is): AC $(cat /sys/class/power_supply/ACAD/online) load $(cut -d' ' -f1-3 /proc/loadavg)"
