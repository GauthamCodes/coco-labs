#!/usr/bin/env bash
# R5.4: a downloaded level package, run exactly as its README's path A says (in COCO's image), one at a time.
#   bash tools/r5/run_level_package_docker.sh PACKAGE_DIR IMAGE
set -o pipefail
DIR="$(cd "$(dirname "${1:?package dir}")" && pwd)"; P="$(basename "$1")"; IMAGE="${2:?image}"
rm -f "$DIR/$P/results.json" "$DIR/$P/launch.log"
timeout 1200 docker run --rm --ulimit core=0 -v "$DIR/$P:/ws/src/$P" --entrypoint bash "$IMAGE" -c "
  source /opt/ros/jazzy/setup.bash && source /opt/coco_ws/install/setup.bash &&
  cd /ws && colcon build --packages-select $P && source install/setup.bash &&
  (ros2 launch $P level.launch.py > /ws/src/$P/launch.log 2>&1 &) &&
  ros2 run $P run_goals --out /ws/src/$P/results.json"
echo "rc=$?"
