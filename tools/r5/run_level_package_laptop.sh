#!/usr/bin/env bash
# R5.4: a downloaded level package on the laptop's own ROS 2 Jazzy (README path B): COCO's packages from
# an overlay built by scripts/build_overlay.sh (COCO_WS), the package built in its own workspace.
#   bash tools/r5/run_level_package_laptop.sh PACKAGE_DIR WS_DIR [USER_PACKAGE]
# The launch runs in its own process group, which this script ends (never anyone else's processes).
DIR="$(cd "$(dirname "${1:?package dir}")" && pwd)"; P="$(basename "$1")"; WS="${2:?workspace}"; USER_PKG="${3:-}"
TAG="${USER_PKG:-stock}"
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if pgrep -f 'g[z] sim' > /dev/null || pgrep -f '[i]saac|[f]ranka_ws' > /dev/null; then echo "NOT STARTED: a simulator is running"; exit 3; fi
export COCO_WS="${COCO_WS:-$HOME/coco_lab_r3_ws}"
set +u; source "$R/setup_env.sh" > /dev/null || exit 1
mkdir -p "$WS/src" && rm -rf "$WS/src/$P" && cp -r "$DIR/$P" "$WS/src/"
cd "$WS" && colcon build --symlink-install --packages-select "$P" > build.log 2>&1 || { tail -5 build.log; exit 1; }
source install/local_setup.bash
setsid ros2 launch "$P" level.launch.py gui:=false ${USER_PKG:+user_package:=$USER_PKG} > "$WS/launch_${P}_$TAG.log" 2>&1 &
L=$!
timeout 1200 ros2 run "$P" run_goals --out "$WS/results_${P}_$TAG.json"; rc=$?
kill -INT -- "-$L" 2>/dev/null; sleep 8; kill -KILL -- "-$L" 2>/dev/null
echo "rc=$rc"
