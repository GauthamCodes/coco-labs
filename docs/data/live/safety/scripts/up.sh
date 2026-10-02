#!/usr/bin/env bash
# up.sh LOGDIR [extra mission.launch.py args...]
# Fresh COCO sim + mission stack from ~/coco_live_ws (the `live` branch
# overlay), headless, on ROS_DOMAIN_ID (default 62). Refuses if a Gazebo runs.
set -o pipefail
LOG="$1"; shift
mkdir -p "$LOG"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-62}"
if pgrep -f 'g[z] sim' >/dev/null 2>&1; then echo "GAZEBO ALREADY RUNNING"; pgrep -af 'g[z] sim'; exit 1; fi
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_PACKAGE_PATH
export COCO_WS="$HOME/coco_live_ws"
source "$COCO_WS/src/coco-labs/setup_env.sh" >/dev/null || exit 1
echo "[up] sim $(date +%T)"
setsid ros2 launch gazebo_models full_world_robo.launch.py gui:=false traverse:=true > "$LOG/sim.log" 2>&1 &
for _ in $(seq 1 120); do
  ros2 topic info /diff_drive_controller/odom 2>/dev/null | grep 'Publisher count: [1-9]' >/dev/null && break
  sleep 2
done
echo "[up] stack $(date +%T)"
setsid ros2 launch coco_mission mission.launch.py rviz:=false platform:=true "$@" > "$LOG/stack.log" 2>&1 &
for _ in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1 && { echo "[up] healthz 200 $(date +%T)"; break; }
  sleep 5
done
