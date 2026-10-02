#!/usr/bin/env bash
# Live: what coco_web_platform publishes and calls on the graph.
D="$(cd "$(dirname "$0")" && pwd)"
R=/home/gautham/.claude/jobs/eb997671/tmp/runs/node_info
"$D/up.sh" "$R" >/dev/null 2>&1
sleep 15
"$D/ros.sh" ros2 node info /coco_web_platform > "$R/node_info.txt" 2>&1
"$D/ros.sh" ros2 topic info /diff_drive_controller/cmd_vel -v > "$R/wheel_topic.txt" 2>&1
bash "$HOME/coco_live_ws/src/coco-labs/gazebo_models/scripts/ros_clean.sh" 2>&1 | tail -1
cat "$R/node_info.txt"
grep -E "Node name|Publisher count" "$R/wheel_topic.txt"
