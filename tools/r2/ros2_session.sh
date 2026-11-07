#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# R2.7: one Gazebo + Nav2 session with a coco_user_<name> package swapped in (tools/m6/m6f8_run.sh:
# one fresh headless simulator, never --fast; refuses if another is running).
#
#   tools/r2/ros2_session.sh LEVEL PACKAGE SCENARIOS.json OUT_DIR [ros2_bench.py flags...]
#
# LEVEL coco_depot_v1 | coco_depot_colours_v1 (G2's derivation-5 generated files, read only);
# PACKAGE a built coco_user_<name>, or "stock" for COCO's own nav.launch.py.
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LEVEL="$1"; PKG="$2"; SC="$3"; OUT="$4"; shift 4
export COCO_WS="${COCO_WS:-$HOME/coco_lab_r2_ws}"
export LEVEL
export GEN="${GEN:-$HOME/coco_lab_runs/g2/gen_d5/$LEVEL}"   # R3.4: overridable (unset = as before)
export WORLD="${WORLD:-$HOME/coco_lab_runs/g2/d5/$LEVEL/gazebo_models/worlds/$LEVEL.sdf}"
export NAV_DRIVER="$R/tools/r2/ros2_bench.py"
if [ "$PKG" != stock ]; then
  export NAV_LAUNCH="$PKG $PKG.launch.py"
  case "$PKG" in *particle_filter*|*localiser*)
    export NAV_NODES_OVERRIDE="/bt_navigator /controller_server /planner_server /map_server /local_costmap/local_costmap /global_costmap/global_costmap /velocity_smoother /collision_monitor /behavior_server"
    export COCO_INITIAL_POSE="$(python3 -c "import json,sys; print(','.join(map(str, json.load(open(sys.argv[1]))['start'])))" "$SC")";;
  esac
fi
mkdir -p "$OUT"
cp "$SC" "$OUT/scenarios.json"
echo "{\"package\": \"$PKG\", \"level\": \"$LEVEL\", \"git\": \"$(git -C "$R" rev-parse HEAD)\", \"dirty\": $(git -C "$R" diff --quiet && echo false || echo true), \"started_utc\": \"$(date -u +%FT%TZ)\", \"power\": \"$(powerprofilesctl get 2>/dev/null)\", \"ac\": \"$(cat /sys/class/power_supply/AC*/online /sys/class/power_supply/ACAD/online 2>/dev/null | head -1)\"}" > "$OUT/session.json"
"$R/tools/m6/m6f8_run.sh" "$SC" "$OUT" "$@"
RC=$?
bash "$R/gazebo_models/scripts/ros_clean.sh" > "$OUT/clean_after.txt" 2>&1
# a user node outliving its session would answer the next one's requests too
pkill -f "install/coco_user_[a-z_]*/lib/" >> "$OUT/clean_after.txt" 2>&1 || true
echo "session rc=$RC"
exit $RC
