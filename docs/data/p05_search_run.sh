#!/usr/bin/env bash
# Phase 5 (Lab 4): ONE searching mission, spawned from its manifest, fresh sim.
#
#   p05_search_run.sh OUT_DIR LEVEL SEED COLOUR [SEARCH_ORDER]
#
# p03c_episode_run.sh with the mission in SEARCH mode (mission.launch.py's
# default since Phase 5): the robot is told the colour only. Every level
# hands the SAME manifest to the world launch; the mission launch gets it
# too, and must reduce it to the colour (search_mission_inputs). The runner
# checks that: both nodes' region_map parameters are EMPTY, the executive
# has search=true and ramp_driver search_mode=true, and no parameter names
# a manifest. SEARCH_ORDER (e.g. bay_4,bay_1) runs a given order instead
# of coco_lab's -- a learner's, held fixed against the same placement.
#
# Added recorders: /mission/search (mode, order, belief, discovered) as a
# stream. Everything else is p03c's: fresh headless sim, never --fast,
# depth fusion off, the same bring-up and command-chain checks, domain 64.
# The commit is read from LAB_SOURCE.txt (the overlay copy has no .git).
#
#   COCO_WS=$HOME/coco_search_ws COCO_WT=$HOME/coco_search_ws/src/coco-labs \
#     bash $COCO_WT/docs/data/p05_search_run.sh OUT fixed 0 yellow
set -o pipefail
WT="${COCO_WT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
WS="${COCO_WS:?set COCO_WS to an overlay built from this tree}"
OUT="${1:?usage: p05_search_run.sh OUT_DIR LEVEL SEED COLOUR [ORDER]}"
LEVEL="${2:?level}"
SEED="${3:?seed}"
COLOUR="${4:?colour}"
ORDER="${5:-}"
# Up to four climbs and four retreats: four fetches' worth, with margin.
MISSION_BUDGET=3000
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-64}"
mkdir -p "$OUT"
exec > >(tee -a "$OUT/runner.log") 2>&1
say() { echo "p05_run: $* ($(date -u +%H:%M:%S) UTC)"; }
FAIL=0
COMPLETED=0
check() { if "$@"; then say "PASS $CHECK"; else say "FAIL $CHECK"; FAIL=1; fi; }
# `check ... || exit 4` never exits: check returns 0 even on FAIL (the same
# latent bug is in p03c_episode_run.sh, kept there as the historical runner).
# A bring-up failure that makes the rest of the run meaningless uses must().
must() { if "$@"; then say "PASS $CHECK"; else say "FAIL $CHECK"; FAIL=1; exit 4; fi; }
has() { grep -E "$1" "$2" > /dev/null; }

for p in 'g[z] sim' 'component_container_isolate[d]' 'nav_benc[h]' 'parameter_bridg[e]' \
         'full_world_rob[o].launch.py' 'nav[.]launch.py' 'mission[.]launch.py'; do
    pgrep -af "$p" && { say "REFUSING: something is already running"; exit 3; }
done
if bash "$WT/gazebo_models/scripts/ros_clean.sh" --list | tail -n +2 | grep . > /dev/null; then
    bash "$WT/gazebo_models/scripts/ros_clean.sh" --list
    say "REFUSING: ros_clean.sh would kill something"; exit 3
fi

# shellcheck disable=SC1091
source "$WT/setup_env.sh" > /dev/null 2>&1
# shellcheck disable=SC1091
source "$WS/install/local_setup.bash" || exit 1
python3 -c 'import moveit_configs_utils' || { say "REFUSING: moveit_configs_utils not importable"; exit 5; }
for pkg in coco_mission coco_perception coco_moveit_config coco_rl coco_web custom_teleop gazebo_models coco_config coco_sim; do
    printf '%s %s\n' "$pkg" "$(ros2 pkg prefix "$pkg" 2>&1)"
done > "$OUT/resolve.txt"
cat "$OUT/resolve.txt"
while read -r pkg prefix; do
    case "$prefix" in
        "$WS"/install/*) ;;
        *) say "REFUSING: $pkg does not resolve into $WS/install"; exit 5;;
    esac
done < "$OUT/resolve.txt"

read -r HEAD DIRTY < "$WT/LAB_SOURCE.txt"
{
    echo "head=$HEAD"
    echo "dirty_paths=$DIRTY"
    echo "level=$LEVEL"
    echo "seed=$SEED"
    echo "colour=$COLOUR"
    echo "search_order=${ORDER:-policy}"
    echo "ros_domain_id=$ROS_DOMAIN_ID"
    echo "nav2_params_sha256=$(sha256sum "$WT/gazebo_models/config/nav2_params.yaml" | cut -d' ' -f1)"
    echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$OUT/meta.txt"
say "git $HEAD, dirty paths: $DIRTY, episode $LEVEL seed=$SEED colour=$COLOUR"

# --- the episode, before anything runs ----------------------------------
coco_episode generate --level "$LEVEL" --seed "$SEED" --colour "$COLOUR" \
    --out "$OUT/manifest.json" || exit 6
coco_episode inputs --manifest "$OUT/manifest.json" --out "$OUT/mission_inputs.json" || exit 6
EXPECT_MAP="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["region_map"])' "$OUT/mission_inputs.json")"
# Searching, the region map must be EMPTY whatever the level: the mission
# launch reduces the manifest to the colour (search_mission_inputs).
EXPECT_PARAM=""
if [ "$LEVEL" = fixed ]; then
    WORLD_EPISODE=()
    MISSION_EPISODE=()
else
    WORLD_EPISODE=("episode_manifest:=$OUT/manifest.json")
    MISSION_EPISODE=("episode_manifest:=$OUT/manifest.json")
fi
MISSION_SEARCH=()
[ -n "$ORDER" ] && MISSION_SEARCH=("search_order:=$ORDER")
echo "told channel would have been: $EXPECT_MAP (NOT given to the robot)"
cat "$OUT/mission_inputs.json"

PGIDS=()
REC_PIDS=()
cleanup() {
    trap - EXIT INT TERM
    for pid in "${REC_PIDS[@]}"; do kill -INT "$pid" 2>/dev/null; done
    sleep 5
    for sig in INT TERM KILL; do
        alive=0
        for pg in "${PGIDS[@]}"; do kill -"$sig" -- "-$pg" 2>/dev/null && alive=1; done
        [ "$alive" = 1 ] || break
        sleep 8
    done
    bash "$WT/gazebo_models/scripts/ros_clean.sh" > "$OUT/ros_clean.log" 2>&1
    bash "$WT/gazebo_models/scripts/ros_clean.sh" --list > "$OUT/ros_clean_after.txt" 2>&1
    echo "ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT/meta.txt"
    if [ "$COMPLETED" = 1 ]; then
        say "torn down; runner checks $([ "$FAIL" = 0 ] && echo PASS || echo FAIL)"
    else
        say "torn down; INCOMPLETE -- stopped before every check ran, not a result"
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
        timeout 8 ros2 lifecycle get "$n" 2>/dev/null | grep '^active' > /dev/null || return 1
    done
}
spawn_ok() {
    coco_episode readback --manifest "$OUT/manifest.json" --out "$OUT/readback_spawn.json" \
        > /dev/null 2>&1
}
sim_seconds() {
    timeout 8 ros2 topic echo /clock --once --field clock 2>/dev/null \
        | python3 -c 'import sys,re; t=sys.stdin.read(); s=re.search(r"sec: (\d+)",t); n=re.search(r"nanosec: (\d+)",t); print(f"{int(s.group(1))+int(n.group(1))/1e9:.3f}" if s and n else "nan")'
}

setsid ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false \
    "${WORLD_EPISODE[@]}" "episode_record:=$OUT/spawned_manifest.json" \
    > "$OUT/sim.log" 2>&1 &
PGIDS+=("$!")
CHECK="sim publishing /scan"; must wait_for "$CHECK" 180 scan_up

# --- did gz build the manifest? -----------------------------------------
CHECK="gz read-back matches the manifest (xy 5 mm, z 5 mm, tilt 0.05 rad, layout valid)"
check wait_for "$CHECK" 90 spawn_ok
cat "$OUT/readback_spawn.json"
if [ "$LEVEL" = fixed ]; then
    # the default world launch drew its own requested colour; the POSES must match
    CHECK="spawned targets equal the manifest targets"
    check python3 -c 'import json,sys; a=json.load(open(sys.argv[1]))["targets"]; b=json.load(open(sys.argv[2]))["targets"]; sys.exit(0 if a==b else 1)' \
        "$OUT/manifest.json" "$OUT/spawned_manifest.json"
else
    CHECK="spawned manifest is byte-identical to the generated one"
    check cmp "$OUT/manifest.json" "$OUT/spawned_manifest.json"
fi
CHECK="world launch logged the episode"; check has '\[episode\] ep-' "$OUT/sim.log"

setsid ros2 launch coco_mission mission.launch.py rviz:=false target_colour:="$COLOUR" \
    "${MISSION_EPISODE[@]}" "${MISSION_SEARCH[@]}" > "$OUT/mission.log" 2>&1 &
PGIDS+=("$!")
CHECK="all Nav2 lifecycle nodes active"; must wait_for "$CHECK" 300 nav_active
say "settling 60 s for move_group, perception and the web panel"
sleep 60

for n in "${NAV_NODES[@]}"; do
    printf '%s %s\n' "$n" "$(timeout 8 ros2 lifecycle get "$n" 2>&1)"
done > "$OUT/lifecycle.txt"

CHECK="live nav2 parameter readback matches shipped file"
check python3 -P "$WT/gazebo_models/scripts/nav_params_overlay.py" verify-live \
    --params "$WT/gazebo_models/config/nav2_params.yaml" --out "$OUT/params_live.txt"

ros2 node list > "$OUT/nodes.txt" 2>&1
for n in /mission_executive /localization_monitor /mission_hud /ramp_driver \
         /approach_server /grasp_server /move_group /bt_navigator /collision_monitor \
         /cmd_vel_relay /cmd_vel_arbiter /velocity_smoother; do
    CHECK="node $n present"; check grep -x "$n" "$OUT/nodes.txt" > /dev/null
done
CHECK="exactly one node named like the arbiter"
check test "$(grep -c arbiter "$OUT/nodes.txt")" = 1

# --- what the robot side was told ---------------------------------------
{
    for n in /mission_executive /ramp_driver; do
        printf '%s region_map=[%s]\n' "$n" \
            "$(timeout 10 ros2 param get "$n" region_map 2>&1 | sed -n 's/^String value is: //p')"
    done
} > "$OUT/region_params.txt"
cat "$OUT/region_params.txt"
CHECK="executive and ramp_driver hold NO region map (told the colour only)"
check test "$(grep -c "region_map=\[${EXPECT_PARAM}\]\$" "$OUT/region_params.txt")" = 2
{
    printf 'executive search=%s\n' "$(timeout 10 ros2 param get /mission_executive search 2>&1)"
    printf 'executive search_order=%s\n' "$(timeout 10 ros2 param get /mission_executive search_order 2>&1)"
    printf 'ramp_driver search_mode=%s\n' "$(timeout 10 ros2 param get /ramp_driver search_mode 2>&1)"
} > "$OUT/search_params.txt"
cat "$OUT/search_params.txt"
CHECK="executive search=true and ramp_driver search_mode=true"
check test "$(grep -c 'Boolean value is: True' "$OUT/search_params.txt")" = 2
CHECK="executive logged SEARCH mode at start"
check has 'SEARCH mode: told the colour only' "$OUT/mission.log"
CHECK="no node parameter carries a manifest path"
check bash -c "! ros2 param dump /mission_executive 2>/dev/null | grep manifest"

echo '{"topology": "B"}' > "$OUT/resolved_b.json"
python3 -P "$WT/gazebo_models/scripts/nav_params_overlay.py" verify-topology \
    --resolved "$OUT/resolved_b.json" --out "$OUT/topology_live.txt"
cat "$OUT/topology_live.txt"
CHECK="wheel owner + every command-chain link (arbiter-mode line excluded: idle is correct before start)"
check bash -c "! grep '^MISMATCH' '$OUT/topology_live.txt' | grep -v 'arbiter mode'"
CHECK="topology_live.txt contains the chain section"
check has 'command chain, link by link' "$OUT/topology_live.txt"

for t in /cmd_vel_nav /cmd_vel_smoothed /cmd_vel /cmd_vel_gated /diff_drive_controller/cmd_vel \
         /cmd_vel_rl /cmd_vel_approach /cmd_vel_teleop; do
    echo "===== $t"
    ros2 topic info -v "$t"
done > "$OUT/graph_chain.txt" 2>&1
CHECK="exactly one publisher on /diff_drive_controller/cmd_vel"
check test "$(ros2 topic info /diff_drive_controller/cmd_vel 2>/dev/null | sed -n 's/^Publisher count: //p')" = 1

{
    echo "depth_cloud processes:"
    pgrep -af 'image_proc/resize_nod[e]|point_cloud_xyz_nod[e]|depth_cloud[.]launch' || echo "  none"
    for n in /local_costmap/local_costmap /global_costmap/global_costmap; do
        printf '%s voxel_layer.observation_sources=%s\n' "$n" \
            "$(timeout 10 ros2 param get "$n" voxel_layer.observation_sources 2>&1 | tr '\n' ' ')"
        printf '%s obstacle_layer.observation_sources=%s\n' "$n" \
            "$(timeout 10 ros2 param get "$n" obstacle_layer.observation_sources 2>&1 | tr '\n' ' ')"
    done
} > "$OUT/depth_off.txt"
CHECK="depth fusion off (no depth-cloud process, every observation source is scan)"
check bash -c "grep '^  none$' '$OUT/depth_off.txt' > /dev/null && test \$(grep -c 'String value is: scan \$' '$OUT/depth_off.txt') = 4"

CHECK="no launched process died during bring-up"
must bash -c "! grep -E 'process has died|exited with code [1-9]' '$OUT/mission.log' '$OUT/sim.log'"

# --- the mission, nominal, nothing injected -----------------------------
python3 -P "$WT/docs/data/c2nav42_cmdpath.py" record --out "$OUT/cmdpath" \
    --duration "$MISSION_BUDGET" --until-terminal > "$OUT/cmdpath.log" 2>&1 &
REC_PIDS+=("$!")
CMDPATH_PID=$!
python3 -P "$WT/docs/data/c2m51_hrec.py" --out "$OUT/hrec.csv" --tag p05 \
    --stop-on-terminal > "$OUT/hrec.log" 2>&1 &
REC_PIDS+=("$!")
ros2 topic echo /mission/state --field data > "$OUT/state_stream.txt" 2>&1 &
REC_PIDS+=("$!")
ros2 topic echo /mission/search --field data > "$OUT/search_stream.txt" 2>&1 &
REC_PIDS+=("$!")
# The bundle's provenance names a rosbag: the mission's own lines and the
# ground-truth odometry (home error), stopped with INT like the others.
ros2 bag record -o "$OUT/bag" /mission/state /mission/search \
    /mission/search_region /perception/status /ramp/status /approach/status \
    /grasp/status /model/coco/odometry > "$OUT/bag.log" 2>&1 &
REC_PIDS+=("$!")
# Added after the first matrix: two episodes lost their target in
# SEARCH_TARGET and nothing had recorded what perception reported. Each is
# a 5 Hz key=value line; `sel found seen` and `lateral` are the ones read.
for stream in perception ramp approach; do
    ros2 topic echo "/$stream/status" --field data \
        > "$OUT/${stream}_status.txt" 2>&1 &
    REC_PIDS+=("$!")
done
sleep 8

say "starting the mission ($COLOUR)"
START_S=$SECONDS
SIM_START="$(sim_seconds)"
timeout 30 ros2 service call /mission/start std_srvs/srv/Trigger > "$OUT/start.txt" 2>&1
cat "$OUT/start.txt"
CHECK="mission start accepted"; must has 'success=True' "$OUT/start.txt"

terminal() {
    timeout 8 ros2 topic echo /mission/state --once --field data 2>/dev/null \
        | grep -E 'state=(COMPLETE|ABORT)\b' > /dev/null
}
wait_for "mission terminal" "$MISSION_BUDGET" terminal
WALL_S=$((SECONDS - START_S))
SIM_END="$(sim_seconds)"
say "wall seconds from start call to terminal detection: $WALL_S"
timeout 8 ros2 topic echo /mission/state --once --field data > "$OUT/final_state.txt" 2>&1
cat "$OUT/final_state.txt"
timeout 12 ros2 topic echo /amcl_pose --once > "$OUT/final_amcl_pose.txt" 2>&1
coco_episode readback --manifest "$OUT/manifest.json" --out "$OUT/readback_end.json" > /dev/null 2>&1
python3 - "$OUT" > "$OUT/final_gz.json" <<'PY'
import json, sys
from coco_sim.backends.gazebo import read_gz_poses
poses = read_gz_poses(['coco'])
print(json.dumps({k: vars(v) for k, v in poses.items()}, indent=2))
PY
sleep 3
kill -INT "$CMDPATH_PID" 2>/dev/null
wait "$CMDPATH_PID"
tail -40 "$OUT/cmdpath.log"

CHECK="no launched process died during the mission"
check bash -c "! grep -E 'process has died|exited with code [1-9]' '$OUT/mission.log' '$OUT/sim.log'"

# --- the EpisodeResult ---------------------------------------------------
STATE="$(sed -n 's/.*state=\([A-Z_]*\).*/\1/p' "$OUT/final_state.txt" | head -1)"
REASON="$(sed -n 's/.* reason=\([^ ]*\).*/\1/p' "$OUT/final_state.txt" | head -1)"
if [ "$STATE" = COMPLETE ]; then
    ARGS=(--outcome complete)
elif [ "$STATE" = ABORT ]; then
    ARGS=(--outcome failed --reason "${REASON:-unknown}")
else
    ARGS=(--outcome void --reason "no terminal state within ${MISSION_BUDGET}s wall")
fi
SIM_S="$(python3 -c 'import sys; a,b=sys.argv[1:]; print(f"{float(b)-float(a):.3f}")' "$SIM_START" "$SIM_END")"
coco_episode result --manifest "$OUT/manifest.json" "${ARGS[@]}" \
    --timing "mission_sim_s=$SIM_S" --timing "mission_wall_s=$WALL_S" \
    --commit "$HEAD" --policy phase5_24deg_s0p0 \
    --measurements "{\"runner_checks_pass\": $([ "$FAIL" = 0 ] && echo true || echo false), \"search_order_arg\": \"${ORDER:-policy}\"}" \
    --out "$OUT/result.json"
cat "$OUT/result.json" | head -20
COMPLETED=1
exit "$FAIL"
