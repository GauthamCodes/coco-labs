#!/usr/bin/env bash
# G2.5 proof, step 2 (the laptop, ROS 2 Jazzy): a bag the browser exported, opened by real ROS 2.
#
#   tools/g2/bag_proof.sh BAG.mcap OUT_DIR
#
# 1. `ros2 bag info BAG`                                  -> OUT/bag_info.txt
# 2. rviz2 (tools/g2/coco_model_bag.rviz, use_sim_time) on this desktop's display, then
#    `ros2 bag play BAG --clock 100` (the bag's sim time on /clock); while it plays: `ros2 topic hz /scan`, the latched /map's
#    header from a subscriber that joined late, /scan's frame       -> OUT/play_log.txt
# 3. RViz's own window, twice (gnome-screenshot -w: that window only, never the screen)
#                                                        -> OUT/rviz_*.png
# No simulator runs. Its own ROS domain (82), so nothing else on the machine is disturbed; every
# process it starts is stopped by PID at the end (ros_clean.sh is not used: it stops every rviz2).
set -u
BAG="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set +u; source /opt/ros/jazzy/setup.bash >/dev/null 2>&1; set -u
export ROS_DOMAIN_ID=82 DISPLAY="${DISPLAY:-:1}" PYTHONUNBUFFERED=1
pids=()
cleanup() { for p in "${pids[@]}"; do kill "$p" 2>/dev/null; done; sleep 1; for p in "${pids[@]}"; do kill -9 "$p" 2>/dev/null; done; }
trap cleanup EXIT

{ echo "# ros2 bag info $(basename "$BAG")  ($(date -u +%FT%TZ), ROS 2 $ROS_DISTRO)"; ros2 bag info "$BAG"; } > "$OUT/bag_info.txt" 2>&1
echo "bag info rc=$?"

rviz2 -d "$HERE/coco_model_bag.rviz" --ros-args -p use_sim_time:=true > "$OUT/rviz2.log" 2>&1 &
pids+=($!)
sleep 8
{
  echo "# ros2 bag play $(basename "$BAG") --clock 100  ($(date -u +%FT%TZ))"
  ros2 bag play "$BAG" --clock 100 > "$OUT/bag_play.log" 2>&1 &
  play=$!; pids+=($play)
  sleep 6
  echo "## ros2 topic hz /scan (6 s, while playing)"
  timeout 6 ros2 topic hz /scan 2>&1 | tail -4
  echo "## /map from a late subscriber (transient local: the bag player re-offers it)"
  timeout 8 ros2 topic echo --once --qos-durability transient_local --qos-reliability reliable /map nav_msgs/msg/OccupancyGrid --field info 2>&1 | head -20
  echo "## /scan header"
  timeout 5 ros2 topic echo --once /scan --field header 2>&1 | head -6
  echo "## ros2 topic list (while playing)"
  timeout 5 ros2 topic list 2>&1
} > "$OUT/play_log.txt" 2>&1
wid=$(xdotool search --name "RViz" | tail -1)
echo "rviz window: ${wid:-none}"
if [ -n "${wid:-}" ]; then
  wmctrl -i -a "$wid"; sleep 1.5
  gnome-screenshot -w -f "$OUT/rviz_1.png"
  sleep 8
  wmctrl -i -a "$wid"; sleep 1
  gnome-screenshot -w -f "$OUT/rviz_2.png"
fi
wait "${pids[1]}" 2>/dev/null
echo "play done"
