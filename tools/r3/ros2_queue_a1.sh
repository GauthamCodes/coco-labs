#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# R3 Part A follow-ups to R2.7 (Gautham's answers 2 and 3, 2026-11-06), one fresh simulator at a
# time (never two, never --fast), raw runs in ~/coco_lab_runs/r3/a1/ (read-only evidence after):
#   costs: the 5 Depot drives again for Lazy Theta*, the A* starter and stock Nav2, recording the
#          live global and local costmap cost under every plan the controller receives
#          (ros2_bench.py --costs) -- to confirm or reject "Theta*'s paths hug corners";
#   snap1..snap3: the 20 planning scenarios, stock Nav2 asked twice (as given, and with start and
#          goal snapped to the nearest free cell, as COCO Lab does) beside the A* starter.
# A session that comes back VOID (rc 3/4) is retried up to 3 times (R2.7's rule).
#   tools/r3/ros2_queue_a1.sh [STEP...]     (default: costs snap1 snap2 snap3)
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
D="$R/docs/v2/r2/data/r27"
RUNS="$HOME/coco_lab_runs/r3/a1"
S="$R/tools/r2/ros2_session.sh"
on_ac() { [ "$(cat /sys/class/power_supply/AC*/online /sys/class/power_supply/ACAD/online 2>/dev/null | head -1)" = 1 ] && [ "$(powerprofilesctl get 2>/dev/null)" = balanced ]; }
# R3: also wait for AC and the balanced profile (R2.7's sessions once ran on power-saver)
quiet() {
  while pgrep -f 'g[z] sim' > /dev/null || pgrep -f 'nav[.]launch.py' > /dev/null || ! on_ac; do sleep 20; done
  sleep 30
}
session() {  # session OUT LEVEL PACKAGE SCENARIOS flags...
  local out="$1" level="$2" pkg="$3" sc="$4"; shift 4
  local try rc
  for try in 1 2 3 4; do
    [ -f "$out/DONE" ] && return 0
    quiet
    [ -d "$out" ] && mv "$out" "${out}_void$try"
    "$S" "$level" "$pkg" "$sc" "$out" "$@"
    rc=$?
    echo "$(date -u +%FT%TZ) $out rc=$rc" >> "$RUNS/queue.log"
    if [ "$rc" -ne 3 ] && [ "$rc" -ne 4 ]; then touch "$out/DONE"; return 0; fi
  done
}
mkdir -p "$RUNS"
STEPS=("$@"); [ ${#STEPS[@]} -eq 0 ] && STEPS=(costs snap1 snap2 snap3)
for step in "${STEPS[@]}"; do
  case "$step" in
    costs) for pkg in coco_user_theta_star coco_user_astar_starter stock; do
             session "$RUNS/costs_$pkg" coco_depot_v1 "$pkg" "$D/depot5_drive.json" --mode drive \
               --timeout 420 --costs "$RUNS/costs_$pkg/costs.jsonl"
           done ;;
    snap[123]) session "$RUNS/plan_$step" coco_depot_v1 coco_user_astar_starter "$R/tools/r3/depot20_snap.json" \
                 --mode plan --plan-wait 600 --snap compute_path_to_pose ;;
  esac
done
echo "$(date -u +%FT%TZ) queue done" >> "$RUNS/queue.log"
