#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# R2.7: the laptop validation, one fresh simulator at a time (never two, never --fast), in order:
#   planning repeat 3; drives (stock Nav2, the A* starter, Theta*: 5 Depot scenarios each);
#   the pure-pursuit starter on the four colour rounds, 5 runs each; the particle-filter smoke run.
# Raw runs in ~/coco_lab_runs/r2/; a session that comes back VOID (rc 3/4) is retried up to 3 times.
#   tools/r2/ros2_queue.sh [STEP...]     (default: every step)
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
D="$R/docs/v2/r2/data/r27"
RUNS="$HOME/coco_lab_runs/r2"
S="$R/tools/r2/ros2_session.sh"
quiet() { while pgrep -f 'g[z] sim' > /dev/null || pgrep -f 'nav[.]launch.py' > /dev/null; do sleep 20; done; sleep 30; }
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
STEPS=("$@"); [ ${#STEPS[@]} -eq 0 ] && STEPS=(plan3 drive colours localiser)
for step in "${STEPS[@]}"; do
  case "$step" in
    plan3) session "$RUNS/plan_rep3" coco_depot_v1 coco_user_astar_starter "$D/depot20_plan.json" \
             --mode plan --plan-wait 600 --spawn coco_user_theta_star:user_theta_compute_path_to_pose ;;
    drive) for pkg in stock coco_user_astar_starter coco_user_theta_star; do
             session "$RUNS/drive_$pkg" coco_depot_v1 "$pkg" "$D/depot5_drive.json" --mode drive --timeout 420
           done ;;
    colours) for i in 1 2 3 4 5; do for c in red green blue yellow; do
               session "$RUNS/pp_${c}_$i" coco_depot_colours_v1 coco_user_pure_pursuit "$D/goals/colour_$c.json" \
                 --mode round --initial-pose --timeout 420
             done; done ;;
    # the check run on the balanced power profile (the sessions above ran on power-saver)
    balanced) session "$RUNS/plan_balanced_1" coco_depot_v1 coco_user_astar_starter "$D/depot20_plan.json" \
                --mode plan --plan-wait 600 --spawn coco_user_theta_star:user_theta_compute_path_to_pose
              session "$RUNS/drive_balanced_coco_user_theta_star" coco_depot_v1 coco_user_theta_star \
                "$D/depot5_drive.json" --mode drive --timeout 420 ;;
    localiser) session "$RUNS/pf_red_1" coco_depot_colours_v1 coco_user_particle_filter "$D/goals/colour_red.json" \
                 --mode round --initial-pose --timeout 420 ;;
  esac
done
echo "$(date -u +%FT%TZ) queue done" >> "$RUNS/queue.log"
