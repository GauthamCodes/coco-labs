#!/usr/bin/env bash
# COCO 2.0 P03C Consolidation Episode Runner
set -o pipefail
WT="/home/gautham/coco-p03c-consolidation"
WS="/home/gautham/coco_consolidation_ws"

OUT="${1:?usage: consolidation_run.sh OUT_DIR colour level seed [manifest]}"
COLOUR="${2:?colour required}"
LEVEL="${3:-fixed}"
SEED="${4:-0}"
MANIFEST="${5}"

MISSION_BUDGET=1200
mkdir -p "$OUT"
exec > >(tee -a "$OUT/runner.log") 2>&1
say() { echo "p03c_run: $* ($(date -u +%H:%M:%S) UTC)"; }
FAIL=0
COMPLETED=0
check() { if "$@"; then say "PASS $CHECK"; else say "FAIL $CHECK"; FAIL=1; return 1; fi; }

# Pre-flight check
if bash "$WT/gazebo_models/scripts/ros_clean.sh" --list | tail -n +2 | grep -q .; then
    bash "$WT/gazebo_models/scripts/ros_clean.sh" --list
    say "Cleaning stale processes..."
    bash "$WT/gazebo_models/scripts/ros_clean.sh"
    sleep 3
fi

source "$WT/setup_env.sh" > /dev/null 2>&1
source "$WS/install/local_setup.bash" || exit 1
export PYTHONPATH="$WT/coco_sim:$WT/coco_config:$WS/build/custom_teleop:$WS/build/coco_config:$PYTHONPATH"

MV="/home/gautham/ros2_ws(personal)/moveit_prefix/root/opt/ros/jazzy"
PYVER="$(python3 -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
if [ -d "$MV" ]; then
    export AMENT_PREFIX_PATH="$MV:$AMENT_PREFIX_PATH"
    export CMAKE_PREFIX_PATH="$MV:$CMAKE_PREFIX_PATH"
    export LD_LIBRARY_PATH="$MV/lib:$MV/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
    export PYTHONPATH="$MV/lib/$PYVER/site-packages:$PYTHONPATH"
    export PATH="$MV/bin:$PATH"
fi

# Generate manifest if not provided
if [ -z "$MANIFEST" ]; then
    MANIFEST="$OUT/manifest.json"
    python3 -c "
import sys; sys.path.extend(['$WT/coco_sim', '$WT/coco_config'])
from coco_sim.episode import generate_episode
spec = generate_episode(seed=$SEED, level='$LEVEL', requested_colour='$COLOUR')
with open('$MANIFEST', 'w') as f:
    f.write(spec.to_json())
"
fi

say "Manifest: $MANIFEST"
cat "$MANIFEST" > "$OUT/episode_spec.json"

HEAD="$(git -C "$WT" rev-parse HEAD)"
{
    echo "head=$HEAD"
    echo "level=$LEVEL"
    echo "seed=$SEED"
    echo "colour=$COLOUR"
    echo "manifest=$MANIFEST"
    echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$OUT/meta.txt"

PGIDS=()
REC_PIDS=()
cleanup() {
    trap - EXIT INT TERM
    say "Tearing down run..."
    for pid in "${REC_PIDS[@]}"; do kill -INT "$pid" 2>/dev/null; done
    sleep 3
    for sig in INT TERM KILL; do
        alive=0
        for pg in "${PGIDS[@]}"; do kill -"$sig" -- "-$pg" 2>/dev/null && alive=1; done
        [ "$alive" = 1 ] || break
        sleep 5
    done
    bash "$WT/gazebo_models/scripts/ros_clean.sh" > "$OUT/ros_clean.log" 2>&1
    echo "ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT/meta.txt"
    if [ "$COMPLETED" = 1 ]; then
        say "torn down; runner checks $([ "$FAIL" = 0 ] && echo PASS || echo FAIL)"
    else
        say "torn down; INCOMPLETE"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

wait_for() {
    local label="$1" budget="$2"; shift 2
    local deadline=$((SECONDS + budget))
    while [ "$SECONDS" -lt "$deadline" ]; do
        "$@" && { say "$label after $((SECONDS + budget - deadline))s"; return 0; }
        sleep 3
    done
    say "$label NOT reached in ${budget}s"; return 1
}
scan_up() { timeout 8 ros2 topic echo /scan --once --field header.stamp.sec > /dev/null 2>&1; }
NAV_NODES=(/bt_navigator /controller_server /planner_server /amcl /map_server
           /local_costmap/local_costmap /global_costmap/global_costmap
           /velocity_smoother /collision_monitor /behavior_server)
nav_active() {
    local n
    for n in "${NAV_NODES[@]}"; do
        timeout 8 ros2 lifecycle get "$n" 2>/dev/null | grep -q '^active' || return 1
    done
}

say "Launching simulator with episode manifest..."
setsid ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false episode_manifest:="$MANIFEST" \
    > "$OUT/sim.log" 2>&1 &
PGIDS+=("$!")
CHECK="sim publishing /scan"; check wait_for "$CHECK" 180 scan_up || exit 4

say "Launching mission with episode manifest..."
setsid ros2 launch coco_mission mission.launch.py rviz:=false episode_manifest:="$MANIFEST" target_colour:="$COLOUR" \
    > "$OUT/mission.log" 2>&1 &
PGIDS+=("$!")
CHECK="all Nav2 lifecycle nodes active"; check wait_for "$CHECK" 300 nav_active || exit 4
say "settling 40 s for move_group, perception and web panel"
sleep 40

ros2 node list > "$OUT/nodes.txt" 2>&1
for n in /mission_executive /localization_monitor /mission_hud /ramp_driver \
         /approach_server /grasp_server /move_group /bt_navigator /collision_monitor \
         /cmd_vel_relay /cmd_vel_arbiter /velocity_smoother; do
    CHECK="node $n present"; check grep -qx "$n" "$OUT/nodes.txt"
done

say "Starting observers..."
python3 "$WT/docs/data/navigation_world_observe.py" --out "$OUT/visual_topics.json" \
    --duration "$MISSION_BUDGET" > "$OUT/observer.log" 2>&1 &
REC_PIDS+=("$!")

ros2 topic echo /mission/state --field data > "$OUT/state_stream.txt" 2>&1 &
REC_PIDS+=("$!")
sleep 5

say "Starting mission for $COLOUR ($LEVEL seed $SEED)..."
START_S=$SECONDS
timeout 30 ros2 service call /mission/start std_srvs/srv/Trigger > "$OUT/start.txt" 2>&1
cat "$OUT/start.txt"
CHECK="mission start accepted"; check grep -q 'success=True' "$OUT/start.txt"

terminal() {
    timeout 8 ros2 topic echo /mission/state --once --field data 2>/dev/null \
        | grep -Eq 'state=(COMPLETE|ABORT)\b'
}
wait_for "mission terminal" "$MISSION_BUDGET" terminal
say "wall seconds from start call to terminal detection: $((SECONDS - START_S))"
timeout 8 ros2 topic echo /mission/state --once --field data > "$OUT/final_state.txt" 2>&1
cat "$OUT/final_state.txt"
CHECK="full mission reached COMPLETE (not merely Nav2 success)"
check grep -q "state=COMPLETE " "$OUT/final_state.txt"
timeout 12 ros2 topic echo /amcl_pose --once > "$OUT/final_amcl_pose.txt" 2>&1
sleep 3

COMPLETED=1
exit "$FAIL"
