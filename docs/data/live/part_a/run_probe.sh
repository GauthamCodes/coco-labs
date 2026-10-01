#!/usr/bin/env bash
D="$(cd "$(dirname "$0")" && pwd)"
export ROS_DOMAIN_ID=62
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_PACKAGE_PATH
source "$HOME/coco_labs_ws/src/coco-labs/setup_env.sh" >/dev/null 2>&1
cd "$D" || exit 1
python3 "$D/recorder.py" "$D/ros.jsonl" &
REC=$!
sleep 3
python3 "$D/probe.py" "$D/ws.jsonl"
echo "probe exit $?"
sleep 2
kill -INT "$REC"
wait "$REC" 2>/dev/null
echo done
