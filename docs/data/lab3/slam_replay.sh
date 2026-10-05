#!/bin/bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# Phase 4 (Lab 3): run ONE SLAM backend on ONE recorded drive.
#
#   slam_replay.sh BACKEND ARM DRIVE_DIR OUT
#
# BACKEND  slam_toolbox | cartographer
# MODE (environment) async (default) | sync -- slam_toolbox only:
#          async_slam_toolbox_node (the project's slam.launch.py; drops scans
#          when it falls behind) or sync_slam_toolbox_node (the SAME params;
#          processes every scan, so the result does not depend on the
#          machine's load). Cartographer's online node queues, never drops.
# ARM      loop   -- the backend as configured (loop closure on)
#          noloop -- loop closure off: slam_toolbox do_loop_closing false;
#                    Cartographer POSE_GRAPH.optimize_every_n_nodes 0
#          loop_noodom -- Cartographer only, a DIAGNOSTIC: global SLAM on,
#                    wheel odometry off (cartographer/coco_2d_loop_noodom.lua)
# DRIVE_DIR  a make_drive.py output (its bag/ is replayed)
#
# The drive's bag is played at 1.0x with its recorded clock (--clock 100,
# the bag's own timestamps are sim time), topics /scan /tf /tf_static and
# the wheel odometry only -- the truth topic is NOT played. The backend
# runs online, exactly as it would on the robot; slam_record.py logs its
# map -> odom and its last /map. No simulator is started: a recorded drive
# replayed. Each child is its own process group, killed on exit.
#
# slam_toolbox: gazebo_models/config/slam_params.yaml UNCHANGED (the
# project's configuration), lifecycle configured + activated as
# slam.launch.py does. Cartographer: the released 2.0.9003 debs in the
# user-space prefix $CARTO_PREFIX (no sudo on this machine), config
# docs/data/lab3/cartographer/coco_2d.lua (see its header).
set -u
set -o pipefail
ulimit -c 0
BACKEND="${1:?usage: slam_replay.sh BACKEND ARM DRIVE_DIR OUT}"
ARM="${2:?}"
DRIVE="${3:?}"
OUT="${4:?}"
RATE="${RATE:-1.0}"
MODE="${MODE:-async}"
case "$MODE" in async|sync) ;; *) echo "bad MODE: $MODE"; exit 2 ;; esac
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HERE="$REPO/docs/data/lab3"
CARTO_PREFIX="${CARTO_PREFIX:-$HOME/coco_labs_ws/cartographer_prefix/root}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-67}"
case "$BACKEND/$ARM" in
    slam_toolbox/loop|slam_toolbox/noloop|cartographer/loop|cartographer/noloop|cartographer/loop_noodom) ;;
    *) echo "bad BACKEND/ARM: $BACKEND/$ARM"; exit 2 ;;
esac
[ -d "$DRIVE/bag" ] || { echo "no bag in $DRIVE"; exit 2; }
[ -e "$OUT" ] && { echo "refusing: $OUT exists"; exit 3; }
# a previous run's processes may still be exiting (measured: two round-2 runs
# were refused straight after the run before them, under a load of ~20):
# wait up to 60 s, then refuse and NAME what is running
PAT='a?sync_slam_toolbo[x]|cartographer_nod[e]|cartographer_occupancy_grid_nod[e]|lab3_slam_recor[d]|slam_recor[d].py'
for _ in $(seq 1 12); do
    pgrep -f "$PAT" > /dev/null || break
    sleep 5
done
if pgrep -f "$PAT" > /dev/null; then
    echo "refusing: a SLAM backend or recorder is already running:"
    pgrep -af "$PAT" | cut -c1-160
    exit 4
fi
mkdir -p "$OUT"
set +u
. /opt/ros/jazzy/setup.bash
set -u
if [ "$BACKEND" = cartographer ]; then
    export AMENT_PREFIX_PATH="$CARTO_PREFIX/opt/ros/jazzy:$AMENT_PREFIX_PATH"
    export LD_LIBRARY_PATH="$CARTO_PREFIX/opt/ros/jazzy/lib:$CARTO_PREFIX/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
fi
say() { echo "slam_replay: $* ($(date -u +%H:%M:%S) UTC)" | tee -a "$OUT/runner.log"; }

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

{
    echo "{"
    echo "  \"backend\": \"$BACKEND\", \"arm\": \"$ARM\", \"rate\": $RATE, \"mode\": \"$MODE\","
    echo "  \"drive\": \"$DRIVE\", \"ros_domain_id\": $ROS_DOMAIN_ID,"
    echo "  \"started_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"loadavg_start\": \"$(cut -d' ' -f1-3 /proc/loadavg)\","
    echo "  \"git_head\": \"$(git -C "$REPO" rev-parse HEAD 2>/dev/null)\","
    echo "  \"slam_toolbox\": \"$(dpkg-query -W -f='${Version}' ros-jazzy-slam-toolbox 2>/dev/null)\","
    echo "  \"cartographer_debs\": \"$(tr '\n' ' ' < "$CARTO_PREFIX/../debs.sha256" 2>/dev/null)\""
    echo "}"
} > "$OUT/meta.json"

if [ "$BACKEND" = slam_toolbox ]; then
    PARAMS=("--params-file" "$REPO/gazebo_models/config/slam_params.yaml")
    cp "$REPO/gazebo_models/config/slam_params.yaml" "$OUT/"
    if [ "$ARM" = noloop ]; then
        printf 'slam_toolbox:\n  ros__parameters:\n    do_loop_closing: false\n' > "$OUT/noloop.yaml"
        PARAMS+=("--params-file" "$OUT/noloop.yaml")
    fi
    setsid ros2 run slam_toolbox "${MODE}_slam_toolbox_node" --ros-args \
        -r __node:=slam_toolbox "${PARAMS[@]}" -p use_sim_time:=true \
        > "$OUT/backend.log" 2>&1 &
    PGIDS+=("$!")
    sleep 4
    ros2 lifecycle set /slam_toolbox configure >> "$OUT/runner.log" 2>&1
    ros2 lifecycle set /slam_toolbox activate >> "$OUT/runner.log" 2>&1
    ros2 lifecycle get /slam_toolbox >> "$OUT/runner.log" 2>&1
else
    BASENAME=coco_2d.lua
    [ "$ARM" = noloop ] && BASENAME=coco_2d_no_loop.lua
    [ "$ARM" = loop_noodom ] && BASENAME=coco_2d_loop_noodom.lua
    # cartographer resolves include "map_builder.lua" against its COMPILED-IN
    # share path (/opt/ros/jazzy/share/cartographer), absent for a user-space
    # prefix: stage the released files verbatim beside ours, one directory
    mkdir -p "$OUT/config"
    cp "$CARTO_PREFIX/opt/ros/jazzy/share/cartographer/configuration_files/"*.lua "$OUT/config/"
    cp "$HERE/cartographer/"*.lua "$OUT/config/"
    setsid ros2 run cartographer_ros cartographer_node \
        -configuration_directory "$OUT/config" \
        -configuration_basename "$BASENAME" \
        --ros-args -p use_sim_time:=true -r odom:=/diff_drive_controller/odom \
        > "$OUT/backend.log" 2>&1 &
    PGIDS+=("$!")
    setsid ros2 run cartographer_ros cartographer_occupancy_grid_node \
        -resolution 0.05 -publish_period_sec 1.0 \
        --ros-args -p use_sim_time:=true > "$OUT/grid.log" 2>&1 &
    PGIDS+=("$!")
    sleep 4
fi
setsid python3 "$HERE/slam_record.py" --out "$OUT/record.json" \
    > "$OUT/record.log" 2>&1 &
REC=$!
PGIDS+=("$REC")
sleep 4
say "playing $DRIVE/bag at ${RATE}x"
T0=$(date +%s.%N)
ros2 bag play "$DRIVE/bag" --clock 100 -r "$RATE" --disable-keyboard-controls \
    --topics /scan /tf /tf_static /diff_drive_controller/odom \
    > "$OUT/play.log" 2>&1
RC=$?
T1=$(date +%s.%N)
say "playback finished (rc $RC, $(echo "$T1 - $T0" | bc) s wall)"
sleep 10
kill -INT -- "-$REC" 2>/dev/null
for _ in $(seq 1 30); do kill -0 -- "-$REC" 2>/dev/null || break; sleep 1; done
echo "{\"play_rc\": $RC, \"play_wall_s\": $(echo "$T1 - $T0" | bc), \"loadavg_end\": \"$(cut -d' ' -f1-3 /proc/loadavg)\"}" > "$OUT/end.json"
say "done"
