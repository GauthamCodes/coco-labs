#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# R3.4 (2026-11-09): the PLANNING sessions of tools/r3/ros2_queue_r34.sh only, for the given repeats
# (default 2 3) -- the same sessions, scenarios, levels, flags and rules (fresh headless simulator per
# session, never --fast, AC + balanced only, VOID retried, DONE skipped). Used because the laptop was
# available only until 2026-11-09 ~14:00: control and localisation keep repeat 1 only (see R3_STATUS).
#   tools/r3/ros2_queue_r34_plan.sh [REPEAT...]
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
REPS=("$@"); [ ${#REPS[@]} -eq 0 ] && REPS=(2 3)
for k in "${REPS[@]}"; do
  for s in depot-nav-100 depot-narrow-30 depot-long-50 depot-clutter-50; do
    level=coco_depot_v1; [ "$s" = depot-clutter-50 ] && level=coco_depot_clutter_v1
    session "$RUNS/${s}_plan_rep$k" "$level" "$GEN3/${level}__rpp" coco_user_astar_starter \
      "$SC/${s}_plan.json" --mode plan --plan-wait 600 "${SNAP[@]}"
  done
done
echo "$(date -u +%FT%TZ) planning queue done (repeats ${REPS[*]})" >> "$RUNS/queue.log"
