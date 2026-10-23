#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# m6f8_run.sh -- M6F.8: the generated Depot in Gazebo (headless) with COCO and Nav2,
# driven through a goal file (docs/v2/m6/M6F8_PLAN.md). One fresh simulator per run.
#
#   COCO_WS=<overlay> tools/m6/m6f8_run.sh GOALS.json OUT_DIR [m6f8_nav.py flags...]
#
# GEN (default ~/coco_lab_runs/m6/gen/coco_depot_v1) holds gen_level.py's outputs, and the
# world is run from ~/coco_lab_runs/m6/gazebo_models/worlds/ (so ros_clean.sh's
# 'gazebo_models/worlds' sweep matches it). Steps: refuse if a simulator or launch is up;
# ros_clean.sh; launch full_world_robo.launch.py gui:=false world:=<abs> (never --fast);
# wait for /scan; list every model and its pose; teleport COCO to the goal file's start
# (/world/coco_depot_v1/set_pose); the arbiter (initial_mode:=nav) and nav.launch.py
# arbiter:=true with the generated map and params; wait for Nav2 active and an AMCL pose;
# record a bag; m6f8_nav.py through the goals; stop; ros_clean.sh. Raw logs in OUT_DIR.
set -o pipefail
ulimit -c 0
GOALS="${1:?usage: m6f8_run.sh GOALS.json OUT_DIR [m6f8_nav.py flags]}"
OUT="${2:?usage: m6f8_run.sh GOALS.json OUT_DIR}"
shift 2
NAV_FLAGS=("$@")
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
: "${COCO_WS:?set COCO_WS to the overlay built from this repo}"
GEN="${GEN:-$HOME/coco_lab_runs/m6/gen/coco_depot_v1}"
WORLD="${WORLD:-$HOME/coco_lab_runs/m6/gazebo_models/worlds/coco_depot_v1.sdf}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-79}"
CLEAN="$REPO/gazebo_models/scripts/ros_clean.sh"
mkdir -p "$OUT" || exit 3
exec > >(tee -a "$OUT/runner.log") 2>&1
say() { echo "m6f8: $* ($(date -u +%H:%M:%S) UTC)"; }

for p in 'g[z] sim' 'full_world_rob[o].launch.py' 'nav[.]launch.py' 'mission[.]launch.py'; do
    if pgrep -af "$p"; then say "REFUSING: '$p' is running"; exit 3; fi
done
bash "$CLEAN" > "$OUT/clean_before.txt" 2>&1

# shellcheck disable=SC1091
source "$REPO/setup_env.sh" > /dev/null 2>&1
# shellcheck disable=SC1091
source "$COCO_WS/install/local_setup.bash"
PY=python3
read -r SX SY STH < <("$PY" -c "import json,sys; s=json.load(open(sys.argv[1]))['start']; print(*s)" "$GOALS")
"$PY" - "$OUT/meta.json" "$REPO" "$GOALS" "$WORLD" "$GEN" <<'EOF'
import hashlib, json, os, subprocess, sys, time
out, repo, goals, world, gen = sys.argv[1:6]
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
sh = lambda *a: subprocess.run(a, capture_output=True, text=True).stdout.strip()
pk = {p: sh('dpkg-query', '-W', '-f=${Version}', p) for p in (
    'ros-jazzy-nav2-bringup', 'ros-jazzy-nav2-amcl', 'ros-jazzy-nav2-smac-planner',
    'ros-jazzy-nav2-dwb-controller', 'ros-jazzy-ros-gz-sim', 'ros-jazzy-rosbag2-py')}
json.dump({'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'evidence_class': 'STACK (full ROS 2 stack in Gazebo, headless; never hardware)',
           'git_commit': sh('git', '-C', repo, 'rev-parse', 'HEAD'),
           'git_dirty_paths': len(sh('git', '-C', repo, 'status', '--porcelain').splitlines()),
           'ros_domain_id': os.environ.get('ROS_DOMAIN_ID'), 'world_to_map': [0.0, 0.0],
           'world': world, 'world_sha256': sha(world),
           'map_yaml_sha256': sha(os.path.join(gen, 'nav2/coco_depot_v1.yaml')),
           'map_pgm_sha256': sha(os.path.join(gen, 'nav2/coco_depot_v1.pgm')),
           'nav2_params_sha256': sha(os.path.join(gen, 'nav2/nav2_params.yaml')),
           'goals': goals, 'goals_sha256': sha(goals), 'packages': pk,
           'power_profile': sh('powerprofilesctl', 'get'),
           'ac_online': open('/sys/class/power_supply/ACAD/online').read().strip(),
           'nvidia': sh('nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'),
           'launch': ['gazebo_models full_world_robo.launch.py gui:=false world:=<abs> (traverse false)',
                      'custom_teleop arbiter.launch.py initial_mode:=nav use_sim_time:=true',
                      'gazebo_models nav.launch.py arbiter:=true map:=<gen> params_file:=<gen>']},
          open(out, 'w'), indent=1)
EOF

PGIDS=()
BAG_PGID=
cleanup() {
    [ -n "$BAG_PGID" ] && { kill -INT -- "-$BAG_PGID" 2>/dev/null; sleep 5; }
    for g in "${PGIDS[@]}"; do kill -INT -- "-$g" 2>/dev/null; done
    sleep 8
    for g in "${PGIDS[@]}"; do kill -TERM -- "-$g" 2>/dev/null; done
    sleep 3
    bash "$CLEAN" > "$OUT/clean_after.txt" 2>&1
    say "cleaned up ($(bash "$CLEAN" --list | tail -n +2 | wc -l) left)"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

wait_for() {
    local label="$1" budget="$2"; shift 2
    local deadline=$((SECONDS + budget))
    while [ "$SECONDS" -lt "$deadline" ]; do
        "$@" && { say "$label after $((SECONDS + budget - deadline))s"; return 0; }
        sleep 3
    done
    say "$label NOT reached in ${budget}s"; return 1
}
scan_up() { timeout 8 ros2 topic echo /scan --once --field header.stamp.sec > /dev/null 2>&1; }
NAV_NODES=(/bt_navigator /controller_server /planner_server /amcl /map_server
           /local_costmap/local_costmap /global_costmap/global_costmap
           /velocity_smoother /collision_monitor /behavior_server)
nav_active() {
    local n s
    for n in "${NAV_NODES[@]}"; do
        s=$(timeout 8 ros2 lifecycle get "$n" 2>/dev/null)
        case "$s" in active*) ;; *) return 1 ;; esac
    done
}
amcl_up() { timeout 8 ros2 topic echo /amcl_pose --once --field header.stamp.sec > /dev/null 2>&1; }

setsid ros2 launch gazebo_models full_world_robo.launch.py gui:=false world:="$WORLD" \
    > "$OUT/sim.log" 2>&1 &
PGIDS+=("$!")
wait_for "sim publishing /scan" 300 scan_up || { say "VOID: no /scan"; exit 4; }
timeout 20 gz model --list > "$OUT/models.txt" 2>&1
timeout 20 gz topic -e -t /world/coco_depot_v1/pose/info -n 1 > "$OUT/poses_at_launch.txt" 2>&1
QZ=$("$PY" -c "import math,sys; print(math.sin(float(sys.argv[1])/2))" "$STH")
QW=$("$PY" -c "import math,sys; print(math.cos(float(sys.argv[1])/2))" "$STH")
say "teleport coco to ($SX, $SY, $STH)"
timeout 20 gz service -s /world/coco_depot_v1/set_pose --reqtype gz.msgs.Pose \
    --reptype gz.msgs.Boolean --timeout 5000 \
    --req "name: 'coco', position: {x: $SX, y: $SY, z: 0.05}, orientation: {x: 0, y: 0, z: $QZ, w: $QW}" \
    > "$OUT/teleport.txt" 2>&1
cat "$OUT/teleport.txt"
sleep 3
timeout 8 ros2 topic echo /model/coco/odometry --once > "$OUT/truth_after_teleport.txt" 2>&1

setsid ros2 launch custom_teleop arbiter.launch.py initial_mode:=nav use_sim_time:=true \
    > "$OUT/arbiter.log" 2>&1 &
PGIDS+=("$!")
setsid ros2 launch gazebo_models nav.launch.py arbiter:=true use_sim_time:=true \
    map:="$GEN/nav2/coco_depot_v1.yaml" params_file:="$GEN/nav2/nav2_params.yaml" \
    > "$OUT/nav.log" 2>&1 &
PGIDS+=("$!")
wait_for "all Nav2 lifecycle nodes active" 300 nav_active || { say "VOID: Nav2 not active"; exit 4; }
wait_for "AMCL publishing a pose" 120 amcl_up || { say "VOID: no AMCL pose"; exit 4; }
sleep 5
for n in "${NAV_NODES[@]}"; do printf '%s %s\n' "$n" "$(timeout 8 ros2 lifecycle get "$n" 2>&1)"; done > "$OUT/lifecycle.txt"
ros2 topic info -v /diff_drive_controller/cmd_vel > "$OUT/wheel_publishers.txt" 2>&1

TOPICS=(/model/coco/odometry /amcl_pose /odometry/filtered /diff_drive_controller/odom
        /tf /tf_static /clock /scan /plan /received_global_plan /local_plan
        /diff_drive_controller/cmd_vel /cmd_vel_gated /cmd_vel_nav /cmd_vel_smoothed /cmd_vel
        /cmd_vel_arbiter/status /collision_monitor_state /initialpose
        /navigate_to_pose/_action/status /follow_path/_action/status)
setsid ros2 bag record --use-sim-time --include-hidden-topics -s mcap \
    -o "$OUT/bag" "${TOPICS[@]}" > "$OUT/bag.log" 2>&1 &
BAG_PGID=$!
sleep 5
"$PY" "$REPO/tools/m6/m6f8_nav.py" "$GOALS" "$OUT/results.jsonl" "${NAV_FLAGS[@]}"
RC=$?
say "goals done (rc $RC)"
timeout 20 gz topic -e -t /world/coco_depot_v1/pose/info -n 1 > "$OUT/poses_at_end.txt" 2>&1
exit "$RC"
