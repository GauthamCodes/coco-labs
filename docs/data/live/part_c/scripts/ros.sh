#!/usr/bin/env bash
# ros.sh CMD...: run a command in the live overlay's ROS environment.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-62}"
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_PACKAGE_PATH
export COCO_WS="$HOME/coco_live_ws"
source "$COCO_WS/src/coco-labs/setup_env.sh" >/dev/null 2>&1
exec "$@"
