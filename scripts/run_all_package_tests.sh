#!/usr/bin/env bash
set -e

# Every package's tests, per package, cwd = the package dir (CLAUDE.md §8).
# The checkout is this script's repo; the workspace is <ws> above it
# (~/coco_labs_ws), or $COCO_WS.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COCO_WS="${COCO_WS:-$(cd "$REPO_DIR/../.." && pwd)}"
source "$REPO_DIR/setup_env.sh"
source "$COCO_WS/install/local_setup.bash"

MV="$COCO_WS/moveit_prefix/root/opt/ros/jazzy"
PYVER="$(python3 -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
if [ -d "$MV" ]; then
    export AMENT_PREFIX_PATH="$MV:$AMENT_PREFIX_PATH"
    export CMAKE_PREFIX_PATH="$MV:$CMAKE_PREFIX_PATH"
    export LD_LIBRARY_PATH="$MV/lib:$MV/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
    export PYTHONPATH="$MV/lib/$PYVER/site-packages:$PYTHONPATH"
    export PATH="$MV/bin:$PATH"
fi

PACKAGES=(
    "coco_config"
    "coco_sim"
    "coco_mission"
    "coco_web"
    "gazebo_models"
    "coco_rl"
    "coco_perception"
    "coco_moveit_config"
    "custom_teleop"
    "coco_lab"
    "coco_lab_ros"
)

TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0

echo "=================================================="
echo "Running full regression test suite across packages"
echo "=================================================="

for PKG in "${PACKAGES[@]}"; do
    PKG_PATH="${REPO_DIR}/${PKG}"
    if [ ! -d "${PKG_PATH}/test" ]; then
        echo "No tests found for ${PKG}"
        continue
    fi
    echo "--- Testing ${PKG} ---"
    (
        cd "${PKG_PATH}"
        pytest test -q --disable-warnings || true
    )
done
