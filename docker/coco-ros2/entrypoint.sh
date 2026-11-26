#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# coco-ros2 -- R5.1: COCO's ROS 2 stack (Gazebo Harmonic headless, Nav2, cmd_vel_arbiter) on one
# COCO Lab level, with a WebSocket bridge, in one container. LIVE means this stack running now;
# it is a simulation (Gazebo), never hardware.
#
#   docker run --rm -p 8765:8765 ghcr.io/gauthamcodes/coco-ros2 --level depot
#
#   coco-ros2 [--level NAME] [--port N]   start (default --level depot, port 8765)
#   coco-ros2 levels                      the levels this image carries
#   coco-ros2 check [--json]              the acceptance check against the running stack
#                                         (docker exec <container> coco-ros2 check)
#   coco-ros2 shell | <command...>        a shell, or any command, with ROS and COCO's overlay
#
# The bring-up is tools/m6/m6f8_run.sh's, the one every recorded Depot STACK run used: the
# simulator (full_world_robo.launch.py gui:=false world:=<level>), wait for /scan, teleport COCO
# to the level's start, re-spawn diff_drive_controller with the level's odometry calibration
# (derivation 5), cmd_vel_arbiter (initial_mode:=nav), Nav2 through the arbiter (nav.launch.py
# arbiter:=true with the level's map and parameters), wait until every Nav2 lifecycle node is
# active and AMCL publishes a pose. The image adds: Xvfb (software OpenGL for the GPU LiDAR and
# the camera; no GPU is assumed), /odom (docker/coco-ros2/odom_relay.py) and foxglove_bridge.
# Not started: tools/g2/actor_scenario.py -- the Depot's actors stand at their t = 0 poses.
#
# No `set -e`/`set -u` (ROS's setup scripts read unset variables; a failure must tear the rest
# down and say why, not vanish), as docker/entrypoint.sh.
set -o pipefail
ulimit -c 0

COCO=/opt/coco
INDEX="$COCO/levels/index.json"
LOGS="${COCO_LOG_DIR:-/tmp/coco}"
PORT="${COCO_BRIDGE_PORT:-8765}"
LEVEL="${COCO_LEVEL:-depot}"
SCAN_TIMEOUT="${COCO_SCAN_TIMEOUT:-300}"
NAV_TIMEOUT="${COCO_NAV_TIMEOUT:-300}"
AMCL_TIMEOUT="${COCO_AMCL_TIMEOUT:-120}"

say() { echo "[coco-ros2] $* ($(date -u +%H:%M:%S) UTC)"; }
die() { echo "[coco-ros2] FATAL: $*" >&2; exit 1; }

ros_env() {
  # shellcheck disable=SC1091
  source /opt/ros/jazzy/setup.bash || die "no ROS 2 Jazzy in this image"
  # shellcheck disable=SC1091
  source /opt/coco_ws/install/setup.bash || die "no COCO overlay at /opt/coco_ws/install"
}

usage() { sed -n '9,15p' "$0" | sed 's/^# \{0,1\}//'; }

PGIDS=()
NAMES=()
CLEANED=
cleanup() {
  [ -n "$CLEANED" ] && return
  CLEANED=1
  say "shutting down"
  local g
  for g in "${PGIDS[@]}"; do kill -INT -- "-$g" 2>/dev/null; done
  sleep 5
  for g in "${PGIDS[@]}"; do kill -TERM -- "-$g" 2>/dev/null; done
  sleep 2
  for g in "${PGIDS[@]}"; do kill -KILL -- "-$g" 2>/dev/null; done
  rm -f "$LOGS/ready.json"
}

# Each part in its own session, so a whole launch tree is signalled at once (docker/entrypoint.sh's
# reason: killing only a launcher leaves its nodes publishing).
start() {
  local name="$1"; shift
  setsid "$@" > "$LOGS/$name.log" 2>&1 &
  PGIDS+=("$!")
  NAMES+=("$name")
}

wait_for() {
  local label="$1" budget="$2"; shift 2
  local deadline=$((SECONDS + budget))
  while [ "$SECONDS" -lt "$deadline" ]; do
    "$@" && { say "$label after $((SECONDS + budget - deadline)) s"; return 0; }
    sleep 3
  done
  say "$label NOT reached in ${budget} s"
  return 1
}

fail() {
  local what="$1" log="$2"
  say "FAILED: $what; the last lines of $log:"
  tail -n 40 "$LOGS/$log" >&2 2>/dev/null
  exit 4
}

scan_up() { timeout 8 ros2 topic echo /scan --once --field header.stamp.sec > /dev/null 2>&1; }
amcl_up() { timeout 8 ros2 topic echo /amcl_pose --once --field header.stamp.sec > /dev/null 2>&1; }
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

run_stack() {
  mkdir -p "$LOGS"
  rm -f "$LOGS/ready.json"
  [ -f "$INDEX" ] || die "no level index at $INDEX -- the image did not build its levels"
  local env_out
  env_out=$(python3 "$COCO/bin/level_env.py" "$INDEX" "$LEVEL") || {
    python3 "$COCO/bin/level_env.py" "$INDEX" --list >&2; exit 2; }
  eval "$env_out"
  ros_env
  trap 'cleanup; exit 0' TERM INT
  trap cleanup EXIT

  say "COCO's ROS 2 stack (LIVE when running: a simulation in Gazebo, never hardware)"
  say "  level ${LEVEL_ALIAS} = ${LEVEL_ID} (${LEVEL_KIND}; files ${LEVEL_VERIFIED})"
  say "  bridge ws://0.0.0.0:${PORT} (foxglove_bridge); RMW ${RMW_IMPLEMENTATION}"

  # 1. software OpenGL for Gazebo's sensors (gpu_lidar, rgbd_camera): no GPU is assumed
  start xvfb Xvfb :99 -screen 0 1280x1024x24 +extension GLX +render -noreset -nolisten tcp
  export DISPLAY=:99
  wait_for "Xvfb up" 30 test -e /tmp/.X11-unix/X99 || fail "Xvfb did not start" xvfb.log

  # 2. the simulator, headless (server only; never --fast)
  if [ -n "$LEVEL_WORLD" ]; then
    start sim ros2 launch gazebo_models full_world_robo.launch.py gui:=false world:="$LEVEL_WORLD"
  else
    start sim ros2 launch gazebo_models full_world_robo.launch.py gui:=false
  fi
  wait_for "the simulator publishing /scan" "$SCAN_TIMEOUT" scan_up \
    || fail "no /scan from the simulator" sim.log

  # 3. the bridge (early, so a browser sees the stack come up), and /odom
  start bridge ros2 run foxglove_bridge foxglove_bridge --ros-args \
    --params-file "$COCO/config/foxglove_bridge.yaml" -p "port:=${PORT}"
  start odom_relay python3 "$COCO/bin/odom_relay.py" --ros-args -p use_sim_time:=true

  # 4. COCO to the level's start (Gazebo's world frame), as m6f8_run.sh
  if [ "$LEVEL_TELEPORT" = true ]; then
    say "teleport COCO to (${START_X}, ${START_Y}, ${START_THETA})"
    timeout 20 gz service -s "/world/${LEVEL_ID}/set_pose" --reqtype gz.msgs.Pose \
      --reptype gz.msgs.Boolean --timeout 5000 \
      --req "name: 'coco', position: {x: ${START_X}, y: ${START_Y}, z: 0.05}, orientation: {x: 0, y: 0, z: ${START_QZ}, w: ${START_QW}}" \
      > "$LOGS/teleport.log" 2>&1
    say "  gz answered: $(tr '\n' ' ' < "$LOGS/teleport.log" | head -c 200)"
    sleep 3
    # Gazebo's truth after the teleport, kept beside the logs (m6f8_run.sh's truth_after_teleport);
    # `coco-ros2 check` compares AMCL's pose with the truth
    timeout 8 ros2 topic echo /model/coco/odometry --once --field pose.pose.position \
      > "$LOGS/truth_after_teleport.log" 2>&1
  fi

  # 5. the level's odometry calibration (derivation 5), as m6f8_run.sh: re-spawn the controller
  if [ -n "$LEVEL_CALIBRATION" ]; then
    say "odometry calibration: diff_drive_controller re-spawned with wheel_separation_multiplier ${LEVEL_MULTIPLIER}"
    {
      timeout 30 ros2 control set_controller_state diff_drive_controller inactive
      timeout 30 ros2 control unload_controller diff_drive_controller
      timeout 90 ros2 run controller_manager spawner diff_drive_controller -c /controller_manager -p "$LEVEL_CALIBRATION"
      timeout 15 ros2 control list_controllers
    } > "$LOGS/calibration.log" 2>&1
    local got
    got=$(timeout 15 ros2 param get /diff_drive_controller wheel_separation_multiplier 2>&1 \
          | tee -a "$LOGS/calibration.log" | grep -oE '[0-9.]+$')
    python3 -c "import sys; sys.exit(0 if abs(float(sys.argv[1]) - float(sys.argv[2])) < 1e-9 else 1)" \
      "${got:-nan}" "$LEVEL_MULTIPLIER" 2>/dev/null \
      || fail "wheel_separation_multiplier is '${got}', not ${LEVEL_MULTIPLIER}" calibration.log
    grep -q 'diff_drive_controller.*active' "$LOGS/calibration.log" \
      || fail "diff_drive_controller not active after the re-spawn" calibration.log
  fi

  # 6. the arbiter (the only wheel publisher), then Nav2 through it
  start arbiter ros2 launch custom_teleop arbiter.launch.py initial_mode:=nav use_sim_time:=true
  if [ -n "$LEVEL_MAP" ]; then
    start nav ros2 launch gazebo_models nav.launch.py arbiter:=true use_sim_time:=true \
      map:="$LEVEL_MAP" params_file:="$LEVEL_PARAMS"
  else
    start nav ros2 launch gazebo_models nav.launch.py arbiter:=true use_sim_time:=true
  fi
  wait_for "every Nav2 lifecycle node active" "$NAV_TIMEOUT" nav_active \
    || fail "Nav2 did not reach active" nav.log
  wait_for "AMCL publishing a pose" "$AMCL_TIMEOUT" amcl_up || fail "no AMCL pose" nav.log

  printf '{"level": "%s", "id": "%s", "bridge_port": %s, "ready_utc": "%s", "nav2": "active"}\n' \
    "$LEVEL_ALIAS" "$LEVEL_ID" "$PORT" "$(date -u +%FT%TZ)" > "$LOGS/ready.json"
  say "READY: Nav2 active on ${LEVEL_ID}; connect to ws://localhost:${PORT}"

  # Hold the container on the stack: if any part exits, say which and stop the rest.
  while :; do
    wait -n
    local k
    for k in "${!PGIDS[@]}"; do
      if ! kill -0 "${PGIDS[$k]}" 2>/dev/null; then
        say "${NAMES[$k]} exited; stopping (see $LOGS/${NAMES[$k]}.log)"
        tail -n 20 "$LOGS/${NAMES[$k]}.log" >&2 2>/dev/null
        exit 5
      fi
    done
  done
}

case "${1:-}" in
  levels) python3 "$COCO/bin/level_env.py" "$INDEX" --list ;;
  check) shift; ros_env; exec python3 "$COCO/bin/check.py" "$@" ;;
  shell) ros_env; exec /bin/bash ;;
  -h|--help|help) usage ;;
  ''|--*)
    while [ $# -gt 0 ]; do
      case "$1" in
        --level) LEVEL="${2:?--level needs a name}"; shift 2 ;;
        --level=*) LEVEL="${1#*=}"; shift ;;
        --port) PORT="${2:?--port needs a number}"; shift 2 ;;
        --port=*) PORT="${1#*=}"; shift ;;
        *) usage >&2; die "unknown option $1" ;;
      esac
    done
    run_stack ;;
  *) ros_env; exec "$@" ;;
esac
