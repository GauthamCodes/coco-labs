#!/usr/bin/env bash
# run_all_package_tests.sh -- every package's tests, per package, with cwd
# set to the package directory (CLAUDE.md §8), and a non-zero exit if ANY
# package fails, errors, fails to collect, or collects nothing.
#
#   scripts/run_all_package_tests.sh               run them all
#   scripts/run_all_package_tests.sh --make-venv   build $COCO_WS/test_venv first
#   scripts/run_all_package_tests.sh coco_web coco_mission   only these
#
# The checkout is this script's repo; the workspace is <ws> above it
# (~/coco_labs_ws), or $COCO_WS. Run it on a clean ROS graph (or set an
# unused ROS_DOMAIN_ID): coco_mission's fixtures construct real nodes.
#
# The interpreter matters. coco_lab and coco_lab_ros need hypothesis and
# networkx (coco_lab/requirements-test.txt); bare `pytest` on a machine
# without them dies at collection. This script used to run bare pytest
# under `|| true`, so it exited 0 with two packages never run (measured
# 2026-10-02). It now uses, in order:
#   1. $COCO_TEST_PYTHON, if set;
#   2. $COCO_WS/test_venv/bin/python, if present (--make-venv builds it,
#      with system site-packages so rclpy and the apt packages still load);
#   3. python3 -- right where rosdep installed python3-hypothesis and
#      python3-networkx.
# and refuses to start if that interpreter cannot import the test deps.
set -o pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COCO_WS="${COCO_WS:-$(cd "$REPO_DIR/../.." && pwd)}"
VENV="$COCO_WS/test_venv"

if [ "${1:-}" = "--make-venv" ]; then
    # python3-venv (ensurepip) may be absent and there may be no sudo: make
    # the venv without pip, point the system pip at it, then use its own.
    echo "[tests] building $VENV"
    /usr/bin/python3 -m venv --without-pip --system-site-packages "$VENV" || exit 1
    /usr/bin/python3 -m pip --python "$VENV/bin/python" install -q pip || exit 1
    "$VENV/bin/python" -m pip install -q -r "$REPO_DIR/coco_lab/requirements-test.txt" || exit 1
    shift
fi

# shellcheck disable=SC1091
source "$REPO_DIR/setup_env.sh" || exit 1
# shellcheck disable=SC1091
source "$COCO_WS/install/local_setup.bash" || exit 1

MV="$COCO_WS/moveit_prefix/root/opt/ros/jazzy"
PYVER="$(python3 -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
if [ -d "$MV" ]; then
    export AMENT_PREFIX_PATH="$MV:$AMENT_PREFIX_PATH"
    export CMAKE_PREFIX_PATH="$MV:$CMAKE_PREFIX_PATH"
    export LD_LIBRARY_PATH="$MV/lib:$MV/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
    export PYTHONPATH="$MV/lib/$PYVER/site-packages:$PYTHONPATH"
    export PATH="$MV/bin:$PATH"
fi

if [ -n "${COCO_TEST_PYTHON:-}" ]; then
    PY="$COCO_TEST_PYTHON"
elif [ -x "$VENV/bin/python" ]; then
    PY="$VENV/bin/python"
    # setup_env.sh puts ~/.local's site-packages FIRST on PYTHONPATH (the
    # runtime's pip --user packages must win over apt), and PYTHONPATH
    # outranks a venv's own site-packages -- so a user-site networkx 3.6.1
    # silently replaced the venv's pinned 2.8.8 (measured). Put the venv's
    # pins first for the tests.
    export PYTHONPATH="$VENV/lib/$PYVER/site-packages:$PYTHONPATH"
else
    PY="python3"
fi
if ! "$PY" -c 'import pytest, hypothesis, networkx' 2>/dev/null; then
    echo "[tests] REFUSING: $PY cannot import pytest, hypothesis and networkx." >&2
    echo "[tests] Run with --make-venv, or set COCO_TEST_PYTHON, or" >&2
    echo "[tests]   sudo apt install python3-hypothesis python3-networkx" >&2
    exit 2
fi
# No .pyc or .pytest_cache in the source tree (a .pyc under lab_web/src
# once embedded the runner's path and failed a site test).
export PYTHONDONTWRITEBYTECODE=1

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
# Optional: name packages to run only those, same interpreter and env.
if [ "$#" -gt 0 ]; then
    for PKG in "$@"; do
        case " ${PACKAGES[*]} " in
            *" $PKG "*) ;;
            *) echo "[tests] unknown package: $PKG" >&2; exit 2 ;;
        esac
    done
    PACKAGES=("$@")
fi

echo "[tests] interpreter: $PY ($("$PY" -c 'import sys, pytest, hypothesis, networkx; print(sys.version.split()[0], "pytest", pytest.__version__, "hypothesis", hypothesis.__version__, "networkx", networkx.__version__)'))"
echo "[tests] workspace:   $COCO_WS   ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}"

declare -a SUMMARY
FAILED=0
for PKG in "${PACKAGES[@]}"; do
    PKG_PATH="${REPO_DIR}/${PKG}"
    if [ ! -d "${PKG_PATH}/test" ]; then
        SUMMARY+=("$(printf '%-20s %s' "$PKG" 'NO test/ DIRECTORY')")
        FAILED=1
        continue
    fi
    echo "--- Testing ${PKG} ---"
    LOG="$(mktemp)"
    ( cd "${PKG_PATH}" && "$PY" -m pytest test -q -p no:cacheprovider --disable-warnings ) \
        > "$LOG" 2>&1
    RC=$?
    tail -n 3 "$LOG"
    LINE="$(sed 's/\x1b\[[0-9;]*m//g' "$LOG" | grep -E '[0-9]+ (passed|failed|error)|no tests ran' | tail -n 1)"
    rm -f "$LOG"
    # pytest: 0 ok, 1 tests failed, 2 interrupted (e.g. a collection error),
    # 3 internal error, 4 usage error, 5 no tests collected. Only 0 passes.
    if [ "$RC" -ne 0 ]; then
        FAILED=1
        SUMMARY+=("$(printf '%-20s FAIL (pytest exit %s) %s' "$PKG" "$RC" "$LINE")")
    else
        SUMMARY+=("$(printf '%-20s ok   %s' "$PKG" "$LINE")")
    fi
done

echo "=================================================="
printf '%s\n' "${SUMMARY[@]}"
echo "=================================================="
if [ "$FAILED" -ne 0 ]; then
    echo "[tests] FAILED: at least one package did not pass"
    exit 1
fi
echo "[tests] all ${#PACKAGES[@]} packages passed"
