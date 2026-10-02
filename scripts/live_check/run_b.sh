#!/usr/bin/env bash
# run_b.sh OVERLAY_WS LAB_WEB_DIR OUT SCENARIO [ARGS...]
#
# One Phase 2 Part B measurement run, from a FRESH simulator:
#   1. sim + mission.launch.py (platform:=true) from the overlay, headless
#   2. ROS recorder (wall clock): wheel topic, every arbiter input, modes,
#      mission state, /plan, ground truth, wheel publisher count
#   3. `vite preview` of LAB_WEB_DIR's built dist on :4173
#   4. live_b.py drives the Live tab in headless Firefox
#   5. teardown: preview, recorder, ros_clean.sh; reports leftovers
# Refuses to start if any Gazebo is running (CLAUDE.md: one at a time,
# never kill a simulator this did not start).
set -o pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WS="$1"; LAB="$2"; OUT="$3"; shift 3
mkdir -p "$OUT"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-62}"
if pgrep -f 'g[z] sim' >/dev/null 2>&1; then
  echo "A Gazebo is already running; not starting a second one." >&2
  pgrep -af 'g[z] sim' >&2
  exit 1
fi
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_PACKAGE_PATH
export COCO_WS="$WS"
# shellcheck disable=SC1091
source "$WS/src/coco-labs/setup_env.sh" >/dev/null || exit 1
echo "[run_b] sim $(date +%T)"
setsid ros2 launch gazebo_models full_world_robo.launch.py gui:=false traverse:=true \
  > "$OUT/sim.log" 2>&1 &
for _ in $(seq 1 120); do
  ros2 topic info /diff_drive_controller/odom 2>/dev/null | grep 'Publisher count: [1-9]' >/dev/null && break
  sleep 2
done
echo "[run_b] stack $(date +%T)"
setsid ros2 launch coco_mission mission.launch.py rviz:=false platform:=true \
  > "$OUT/stack.log" 2>&1 &
for _ in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1 && break
  sleep 5
done
echo "[run_b] healthz $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/healthz) $(date +%T)"
python3 "$HERE/recorder.py" "$OUT/ros.jsonl" &
REC=$!
( cd "$LAB" && exec setsid npx vite preview --port 4173 --strictPort ) > "$OUT/preview.log" 2>&1 &
PREVIEW=$!
for _ in $(seq 1 30); do
  curl -fsS http://localhost:4173/coco-labs/ >/dev/null 2>&1 && break
  sleep 1
done
python3 "$HERE/live_b.py" "$OUT" "http://localhost:4173/coco-labs/?view=live" "$@"
echo "[run_b] live_b exit $?"
kill -INT "$REC" 2>/dev/null; wait "$REC" 2>/dev/null
kill -TERM -- "-$PREVIEW" 2>/dev/null
bash "$WS/src/coco-labs/gazebo_models/scripts/ros_clean.sh" 2>&1 | tail -1
sleep 3
echo "[run_b] left: gz $(pgrep -f 'g[z] sim' | wc -l), preview $(pgrep -f 'vite previe[w]' | wc -l)"
