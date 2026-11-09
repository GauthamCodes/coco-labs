#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# R3.4: the Gazebo + Nav2 baselines on COCO-Bench v1's validated subsets (STACK, simulation). One fresh
# headless simulator per session (never two, never --fast), on AC and the balanced profile only; raw
# runs in ~/coco_lab_runs/r3/r34/ (read-only evidence afterwards); slim bags (BAG_SLIM=1).
#   planning: depot-nav-100, depot-narrow-30, depot-long-50, depot-clutter-50 (20 each, by tier):
#             Nav2's Smac 2D, NavFn and Smac Hybrid-A*, each asked as given (stock) and snapped, and
#             the A* starter as a ROS 2 node;
#   control:  ctrl-corridor-30, ctrl-corners-30 (20 each), ctrl-dynamic-30 (15 pairs: the actors
#             yielding, and keeping their schedule): Nav2 with RPP, DWB and MPPI, stock planner;
#   localisation: loc-track-30 (20): AMCL, and the particle-filter starter in its place.
# Repeat 1 of everything first, then 2, then 3 (partial data stay balanced). A session that comes back
# VOID (rc 3/4) is retried up to 3 times (R2.7's rule); a session with DONE is skipped (resumable).
#   tools/r3/ros2_queue_r34.sh [REPEAT...]     (default: 1 2 3)
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SC="$R/docs/v2/r3/data/r34/scenarios"
RUNS="$HOME/coco_lab_runs/r3/r34"
GEN3="$HOME/coco_lab_runs/r3/gen_d5"
S="$R/tools/r2/ros2_session.sh"
export BAG_SLIM=1
on_ac() { [ "$(cat /sys/class/power_supply/AC*/online /sys/class/power_supply/ACAD/online 2>/dev/null | head -1)" = 1 ] && [ "$(powerprofilesctl get 2>/dev/null)" = balanced ]; }
quiet() {
  while pgrep -f 'g[z] sim' > /dev/null || pgrep -f 'nav[.]launch.py' > /dev/null || ! on_ac; do sleep 20; done
  sleep 30
}
session() {  # session OUT LEVEL GEN PACKAGE SCENARIOS flags...
  local out="$1" level="$2" gen="$3" pkg="$4" sc="$5"; shift 5
  local try rc world
  if [ "$level" = coco_depot_clutter_v1 ]; then
    world="$HOME/coco_lab_runs/r3/d5/$level/gazebo_models/worlds/$level.sdf"
  else
    world="$HOME/coco_lab_runs/g2/d5/$level/gazebo_models/worlds/$level.sdf"
  fi
  for try in 1 2 3 4; do
    [ -f "$out/DONE" ] && return 0
    quiet
    [ -d "$out" ] && mv "$out" "${out}_void$try"
    GEN="$gen" WORLD="$world" "$S" "$level" "$pkg" "$sc" "$out" "$@"
    rc=$?
    echo "$(date -u +%FT%TZ) $out rc=$rc" >> "$RUNS/queue.log"
    if [ "$rc" -ne 3 ] && [ "$rc" -ne 4 ]; then touch "$out/DONE"; return 0; fi
  done
}
mkdir -p "$RUNS"
SNAP=(--snap compute_path_to_pose --snap compute_path_to_pose@NavFn --snap compute_path_to_pose@SmacHybrid)
REPS=("$@"); [ ${#REPS[@]} -eq 0 ] && REPS=(1 2 3)
for k in "${REPS[@]}"; do
  for s in depot-nav-100 depot-narrow-30 depot-long-50 depot-clutter-50; do
    level=coco_depot_v1; [ "$s" = depot-clutter-50 ] && level=coco_depot_clutter_v1
    session "$RUNS/${s}_plan_rep$k" "$level" "$GEN3/${level}__rpp" coco_user_astar_starter \
      "$SC/${s}_plan.json" --mode plan --plan-wait 600 "${SNAP[@]}"
  done
  for c in rpp dwb mppi; do
    for s in ctrl-corridor-30 ctrl-corners-30 ctrl-dynamic-30; do
      session "$RUNS/${s}_${c}_rep$k" coco_depot_v1 "$GEN3/coco_depot_v1__$c" stock \
        "$SC/${s}_drive.json" --mode drive --timeout 420
    done
    session "$RUNS/ctrl-dynamic-30-noyield_${c}_rep$k" coco_depot_v1 "$GEN3/coco_depot_v1__${c}__noyield" \
      stock "$SC/ctrl-dynamic-30_noyield_drive.json" --mode drive --timeout 420
  done
  session "$RUNS/loc-track-30_amcl_rep$k" coco_depot_v1 "$GEN3/coco_depot_v1__rpp" stock \
    "$SC/loc-track-30_drive.json" --mode drive --timeout 420
  session "$RUNS/loc-track-30_pf_rep$k" coco_depot_v1 "$GEN3/coco_depot_v1__rpp" coco_user_particle_filter \
    "$SC/loc-track-30_drive.json" --mode drive --timeout 420
done
echo "$(date -u +%FT%TZ) queue done" >> "$RUNS/queue.log"
