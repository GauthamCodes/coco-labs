#!/usr/bin/env bash
# Fresh COCO stack on a private domain, logs here. Mirrors run_platform.sh --native.
set -o pipefail
D="$(cd "$(dirname "$0")" && pwd)"
export ROS_DOMAIN_ID=62
if pgrep -f 'g[z] sim' >/dev/null 2>&1; then echo "GAZEBO ALREADY RUNNING"; pgrep -af 'g[z] sim'; exit 1; fi
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_PACKAGE_PATH
source "$HOME/coco_labs_ws/src/coco-labs/setup_env.sh" || exit 1
echo "[up] sim $(date +%T)"
setsid ros2 launch gazebo_models full_world_robo.launch.py gui:=false traverse:=true > "$D/sim.log" 2>&1 &
for _ in $(seq 1 120); do
  ros2 topic info /diff_drive_controller/odom 2>/dev/null | grep 'Publisher count: [1-9]' >/dev/null && break
  sleep 2
done
echo "[up] stack $(date +%T)"
setsid ros2 launch coco_mission mission.launch.py rviz:=false platform:=true > "$D/stack.log" 2>&1 &
for _ in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1 && { echo "[up] healthz 200 $(date +%T)"; break; }
  sleep 5
done
