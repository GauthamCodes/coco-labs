#!/bin/bash
# A.3 (D6): first frame on emulated 4G, three layouts, the same 12 Case Files (the 3 that missed
# in M3 + 9 across every lab), 3 rounds interleaved: M3's one file (control, the review clone on
# 4224), split (4231) and ordered (4232). GPU, balanced on AC. Restores the power profile on exit.
NODE=/home/gautham/coco_v2_ws/node/node-v24.21.0-linux-x64/bin/node
export PATH=/home/gautham/coco_v2_ws/node/node-v24.21.0-linux-x64/bin:/usr/bin:/bin
OUT=/home/gautham/review/m3_tmp/d6_compare
WEB=/home/gautham/coco_labs_ws/src/coco-labs/.claude/worktrees/v2-m3-play-casefiles/lab_web
ONLY=lab2_rl_fidelity_1_tour,lab3_1_tour,lab3_s1_tour,lab2_kidnap_shipped_k4_r2,lab2_kidnap_recovery_k2,lab4_a1_fixed_red,lab5_static_room_mppi_1,lab5_crossing_dwb_1,lab1_run_astar,lab5_mislocalised_dwb_1,lab4_b2_colours_s1_red,lab2_kidnap_recovery_k1
ORIG=$(powerprofilesctl get)
restore() { powerprofilesctl set "$ORIG"; echo "profile restored to $(powerprofilesctl get)"; }
trap restore EXIT
[ "$(cat /sys/class/power_supply/ACAD/online)" = "1" ] || { echo "NOT ON AC - abort"; exit 2; }
powerprofilesctl set balanced
sleep 20
echo "start $(date -Is): profile $(powerprofilesctl get) AC 1 load $(cut -d' ' -f1-3 /proc/loadavg) driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader)"
cd "$WEB" || exit 1
for r in 1 2 3; do
  for v in m3:4224 split:4231 ordered:4232; do
    n=${v%%:*}; p=${v##*:}
    [ "$(cat /sys/class/power_supply/ACAD/online)" = "1" ] || { echo "AC LOST - abort"; exit 3; }
    mkdir -p "$OUT/$n/round_$r"
    # the control (M3's build) predates the scans_ready mark: it uses the M3 checker
    if [ "$n" = m3 ]; then CHECK=/home/gautham/rv3/lab_web/tools/perf/casefile_check.mjs; else CHECK=tools/perf/casefile_check.mjs; fi
    "$NODE" "$CHECK" --site "http://127.0.0.1:$p/coco-labs/" --out "$OUT/$n/round_$r" --only "$ONLY" --throttle 4g --gpu 1 2>&1 | tail -1 | sed "s/^/$n round $r: /"
  done
done
echo "end $(date -Is): load $(cut -d' ' -f1-3 /proc/loadavg)"
