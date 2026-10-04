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
# rl_replay.sh BAG OUT [RATE]  -- replay a recorded lab2 session's wheel
# odometry and IMU into robot_localization's ekf_node, offline, and record
# what it estimates. No simulator: the INPUTS are the bag's own messages,
# so the wheel-odometry baseline and the EKF see identical conditions.
#
#   BAG   a lab2_run.sh session's bag directory (rosbag2, mcap)
#   OUT   where to write rl_bag/ (the EKF's /odometry/filtered) and logs
#   RATE  playback rate (default 4); the EKF runs on the bag's clock
#
# Needs COCO_WS (an overlay of this repo) for the config path. Runs on ROS
# domain 68 unless ROS_DOMAIN_ID is set, so it never shares a graph with a
# live session. RL_EXEC overrides the EKF executable (default: ros2 run
# robot_localization ekf_node).
set -o pipefail
ulimit -c 0
BAG="${1:?usage: rl_replay.sh BAG OUT [RATE]}"
OUT="${2:?usage: rl_replay.sh BAG OUT [RATE]}"
RATE="${3:-4}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
: "${COCO_WS:?set COCO_WS to the overlay built from this repo}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-68}"
source "$REPO/setup_env.sh" > /dev/null 2>&1
CONFIG="${RL_CONFIG:-$REPO/coco_lab_ros/config/ekf_odom_imu.yaml}"
mkdir -p "$OUT" || exit 3
[ -e "$OUT/rl_bag" ] && { echo "refusing: $OUT/rl_bag exists"; exit 3; }
say() { echo "rl_replay: $* ($(date -u +%H:%M:%S) UTC)"; }

PGIDS=()
cleanup() {
    trap - EXIT INT TERM
    for sig in INT TERM KILL; do
        alive=0
        for pg in "${PGIDS[@]}"; do kill -"$sig" -- "-$pg" 2>/dev/null && alive=1; done
        [ "$alive" = 1 ] || break
        sleep 3
    done
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if [ -n "${RL_EXEC:-}" ]; then
    setsid "$RL_EXEC" --ros-args -r __node:=ekf_filter_node --params-file "$CONFIG" \
        > "$OUT/ekf.log" 2>&1 &
else
    setsid ros2 run robot_localization ekf_node --ros-args -r __node:=ekf_filter_node \
        --params-file "$CONFIG" > "$OUT/ekf.log" 2>&1 &
fi
PGIDS+=("$!")
setsid ros2 bag record --use-sim-time -s mcap -o "$OUT/rl_bag" /odometry/filtered \
    > "$OUT/record.log" 2>&1 &
REC=$!
PGIDS+=("$REC")
sleep 4
say "playing $BAG at ${RATE}x"
ros2 bag play "$BAG" --clock 100 -r "$RATE" \
    --topics /diff_drive_controller/odom /imu /tf_static > "$OUT/play.log" 2>&1
say "playback finished ($?)"
sleep 3
kill -INT -- "-$REC" 2>/dev/null
for _ in $(seq 1 20); do kill -0 -- "-$REC" 2>/dev/null || break; sleep 1; done
sha256sum "$CONFIG" > "$OUT/config.sha256"
cp "$CONFIG" "$OUT/ekf_odom_imu.yaml"
say "done"
