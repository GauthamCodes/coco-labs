#!/usr/bin/env bash
# Milestone 0A -- the collision monitor's SLOWDOWN/STOP, measured on the
# consolidated main, ONE fresh simulator.
#
#   m0a_cmdpath_run.sh REPO OUT_DIR stop|slowdown|control
#
# Topology B exactly as nav_tour_run.sh brings it up (sim ->
# arbiter.launch.py initial_mode:=nav -> nav.launch.py arbiter:=true), in
# the FROZEN coco_world.world with its own map, because every historical
# STOP-probe number (C2-M5.0, C2-NAV.42/43/47) was measured in that world
# and c2nav42_cmdpath.py's wall face (x = -3.90) is that world's. Then the
# live graph is read, and c2nav42_cmdpath.py stop is run unchanged.
#
# MODE (3rd argument):
#   stop      c2nav42_cmdpath.py stop, unchanged -- the historical probe.
#   slowdown  a static side wall is spawned with its face 0.32 m to the
#             robot's left, beside its path: inside PolygonSlow (+/-0.40 m
#             square), outside PolygonStop (0.25 m circle) and out of the
#             path, so FootprintApproach does not see it. A stand-in
#             controller holds raw 0.30 m/s on /cmd_vel_nav past it while
#             c2nav42_cmdpath.py record records every link.
#   control   the same drive and recorder with NO wall: the attribution run.
set -o pipefail
WT="${1:?usage: m0a_cmdpath_run.sh REPO OUT_DIR MODE}"
OUT="${2:?usage: m0a_cmdpath_run.sh REPO OUT_DIR MODE}"
MODE="${3:?usage: m0a_cmdpath_run.sh REPO OUT_DIR stop|slowdown|control}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${COCO_WS:?set COCO_WS to an overlay built from REPO}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-77}"
mkdir -p "$OUT"
exec > >(tee -a "$OUT/runner.log") 2>&1
say() { echo "m0a_cmdpath: $* ($(date -u +%H:%M:%S) UTC)"; }

for p in 'g[z] sim' 'component_container_isolate[d]' 'parameter_bridg[e]' \
         'full_world_rob[o].launch.py' 'nav[.]launch.py' 'mission[.]launch.py'; do
    pgrep -af "$p" && { say "REFUSING: something is already running"; exit 3; }
done

# shellcheck disable=SC1091
source "$WT/setup_env.sh" > /dev/null 2>&1
# shellcheck disable=SC1091
source "$WS/install/local_setup.bash" || exit 1
{
    echo "head=$(git -C "$WT" rev-parse HEAD)"
    echo "dirty_paths=$(git -C "$WT" status --porcelain --untracked-files=no | wc -l)"
    echo "overlay=$WS"
    echo "ros_domain_id=$ROS_DOMAIN_ID"
    echo "world=coco_world.world"
    echo "mode=$MODE"
    echo "nav2_params_sha256=$(sha256sum "$WT/gazebo_models/config/nav2_params.yaml" | cut -d' ' -f1)"
    echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$OUT/meta.txt"
cat "$OUT/meta.txt"

PGIDS=()
cleanup() {
    trap - EXIT INT TERM
    for sig in INT TERM KILL; do
        alive=0
        for pg in "${PGIDS[@]}"; do kill -"$sig" -- "-$pg" 2>/dev/null && alive=1; done
        [ "$alive" = 1 ] || break
        sleep 8
    done
    bash "$WT/gazebo_models/scripts/ros_clean.sh" > "$OUT/ros_clean.log" 2>&1
    bash "$WT/gazebo_models/scripts/ros_clean.sh" --list > "$OUT/ros_clean_after.txt" 2>&1
    echo "ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT/meta.txt"
    say "torn down"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

wait_for() {
    local label="$1" budget="$2"; shift 2
    local deadline=$((SECONDS + budget))
    while [ "$SECONDS" -lt "$deadline" ]; do
        if "$@"; then say "ready: $label"; return 0; fi
        sleep 2
    done
    say "TIMEOUT: $label"; exit 4
}
scan_up() { timeout 8 ros2 topic echo /scan --once > /dev/null 2>&1; }
arbiter_up() { timeout 8 ros2 topic echo /cmd_vel_arbiter/status --once > /dev/null 2>&1; }
monitor_active() { ros2 lifecycle get /collision_monitor 2>/dev/null | grep '^active' > /dev/null; }
smoother_active() { ros2 lifecycle get /velocity_smoother 2>/dev/null | grep '^active' > /dev/null; }

MAPS="$(ros2 pkg prefix gazebo_models)/share/gazebo_models/maps"
setsid ros2 launch gazebo_models full_world_robo.launch.py gui:=false \
    world:=coco_world.world > "$OUT/sim.log" 2>&1 &
PGIDS+=($!)
wait_for "sim publishing /scan" 180 scan_up
if [ "$MODE" = slowdown ]; then
    # Face at y = +0.32 (centre 0.345, 0.05 thick), x in [-2.6, -1.3]: the
    # robot starts at x = -2.0 and a 10 s drive capped at 0.09 m/s ends
    # near x = -1.1, so wall points stay inside the +/-0.40 m square
    # throughout. gate_cube_north's face (y = +0.80) and gate_cube_south's
    # (y = -0.50) are both outside the square.
    WALL_SDF='<?xml version="1.0"?><sdf version="1.9"><model name="m0a_side_wall"><static>true</static><link name="l"><collision name="c"><geometry><box><size>1.3 0.05 0.5</size></box></geometry></collision><visual name="v"><geometry><box><size>1.3 0.05 0.5</size></box></geometry></visual></link></model></sdf>'
    ros2 run ros_gz_sim create -name m0a_side_wall -string "$WALL_SDF" \
        -x -1.95 -y 0.345 -z 0.25 > "$OUT/spawn_wall.log" 2>&1 || { say "wall spawn failed"; exit 6; }
    say "side wall spawned: face y=+0.32, x -2.6..-1.3"
fi
setsid ros2 launch custom_teleop arbiter.launch.py initial_mode:=nav > "$OUT/arbiter.log" 2>&1 &
PGIDS+=($!)
wait_for "cmd_vel_arbiter status" 90 arbiter_up
setsid ros2 launch gazebo_models nav.launch.py arbiter:=true \
    map:="$MAPS/coco_world.yaml" > "$OUT/nav.log" 2>&1 &
PGIDS+=($!)
wait_for "velocity_smoother active" 240 smoother_active
wait_for "collision_monitor active" 240 monitor_active
sleep 5

# The live command path, read off the graph before the probe drives.
for t in /cmd_vel_nav /cmd_vel_smoothed /cmd_vel /cmd_vel_gated /diff_drive_controller/cmd_vel; do
    echo "===== $t"
    ros2 topic info -v "$t" 2>&1 | grep -E 'Type:|Publisher count|Subscription count|Node name|Endpoint type'
done > "$OUT/topology_live.txt"
cat "$OUT/topology_live.txt"
ros2 param get /collision_monitor PolygonSlow.slowdown_ratio > "$OUT/slowdown_ratio.txt" 2>&1
cat "$OUT/slowdown_ratio.txt"

if [ "$MODE" = stop ]; then
    say "probe: c2nav42_cmdpath.py stop"
    python3 -P "$WT/docs/data/c2nav42_cmdpath.py" stop --out "$OUT/cmdpath" > "$OUT/cmdpath.log" 2>&1
    say "probe exit $?"
else
    say "recorder: c2nav42_cmdpath.py record"
    python3 -P "$WT/docs/data/c2nav42_cmdpath.py" record --out "$OUT/cmdpath" \
        --duration 45 > "$OUT/cmdpath.log" 2>&1 &
    REC=$!
    sleep 6
    HZ=()
    for t in /cmd_vel /cmd_vel_gated /diff_drive_controller/cmd_vel; do
        f="$OUT/hz_$(echo "$t" | tr '/' '_').txt"
        timeout 14 ros2 topic hz "$t" > "$f" 2>&1 &
        HZ+=($!)
    done
    python3 "$HERE/m0a_slowdown_drive.py" --speed 0.30 --drive 10.0 > "$OUT/drive.log" 2>&1
    say "drive: $(tail -1 "$OUT/drive.log")"
    wait "$REC"
    say "recorder exit $?"
    # Named pids only: a bare `wait` would also wait on the setsid launches.
    wait "${HZ[@]}"
fi
tail -80 "$OUT/cmdpath.log"
