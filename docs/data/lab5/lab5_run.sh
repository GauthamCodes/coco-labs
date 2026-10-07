#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# lab5_run.sh -- one Phase 6 (Lab 5, Move) session on a FRESH headless
# simulator. Phase 1C's lab1c_run.sh, adapted.
#
#   lab5_run.sh capture OUT                       freeze the scenarios' global
#                                                 paths (SmacPlanner2D, once)
#   lab5_run.sh snapshot OUT                      Experiment C: Nav2's global
#                                                 costmap before and after a
#                                                 person stops on the apron
#                                                 (scenario 'parked'); the
#                                                 robot does not move
#   lab5_run.sh run OUT SCENARIO CONTROLLER [ID]  one controller run:
#       SCENARIO   static_room | crossing | oncoming | mislocalised
#       CONTROLLER DWB | MPPI | RPP  (FollowPath's controller_id
#                  FollowPath = the mission's DWB, MPPI, RPP)
#
# Needs COCO_WS pointing at an overlay built from this repo. ROS domain 66
# unless ROS_DOMAIN_ID is set. Every process it starts is killed by process
# group, then ros_clean.sh sweeps; it REFUSES to start if anything is up
# (CLAUDE.md §5: one Gazebo at a time, never kill what is not ours).
#
# Bring-up: full_world_robo.launch.py gui:=false traverse:=true, then
# lab_stack.launch.py params_file:=<mission params + nav2_move_overlay.yaml>
# (arbiter initial_mode:=nav; nav.launch.py arbiter:=true). Never --fast.
# The lab moves the robot ONLY by one FollowPath goal carrying the frozen
# path; lab_actors moves only its own Gazebo models (gz-transport).
#
# Two bags: bag/ (everything but the two heavy debug topics, kept) and
# heavy/ (DWB /evaluation, MPPI /trajectories), which lab5_extract.py
# condenses into rollouts.json; heavy/ is then hashed and deleted unless
# KEEP_HEAVY=1 (each is ~0.5 GB; the hash stays in heavy_sha256.txt).
#
# Exit: 0 all checks passed; 1 a check failed (a RESULT, recorded);
# 3 refused; 4 VOID (infrastructure); 5 live params differ from the file.
set -o pipefail
ulimit -c 0
MODE="${1:?usage: lab5_run.sh capture|run OUT [SCENARIO CONTROLLER [RUN_ID]]}"
OUT="${2:?usage: lab5_run.sh MODE OUT}"
SCENARIO="${3:-}"
CONTROLLER="${4:-}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HERE="$REPO/docs/data/lab5"
SCEN_FILE="$REPO/coco_lab_ros/config/lab5_scenarios.json"
: "${COCO_WS:?set COCO_WS to the overlay built from this repo}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-66}"
case "$MODE" in
  capture) ;;
  snapshot) SCENARIO=parked ;;
  run)
    case "$CONTROLLER" in
      DWB) CID=FollowPath ;; MPPI) CID=MPPI ;; RPP) CID=RPP ;;
      *) echo "controller must be DWB, MPPI or RPP"; exit 2 ;;
    esac ;;
  *) echo "unknown mode $MODE"; exit 2 ;;
esac
RUN_ID="${5:-lab5-$MODE-${SCENARIO:+$SCENARIO-}${CONTROLLER:+$CONTROLLER-}$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT" || exit 3
exec > >(tee -a "$OUT/runner.log") 2>&1
say() { echo "lab5: $* ($(date -u +%H:%M:%S) UTC)"; }
FAIL=0
check() { if "$@"; then say "PASS $CHECK"; else say "FAIL $CHECK"; FAIL=1; return 1; fi; }

# -- refuse if anything is up ---------------------------------------------
# ANY simulator anywhere: refuse (one Gazebo at a time, CLAUDE.md §5).
for p in 'g[z] sim' 'full_world_rob[o].launch.py' 'mission[.]launch.py'; do
    if pgrep -af "$p"; then say "REFUSING: '$p' is running"; exit 3; fi
done
# The sweep is SCOPED TO THIS ROS DOMAIN. ros_clean.sh matches by process
# name across the whole machine; on 2026-10-07 it would have killed an
# orphaned target_finder of ANOTHER workspace (~/coco_m1_ws, domain 181).
# A process belongs to a run here iff its environment says ROS_DOMAIN_ID =
# ours -- true of every process this runner (or an earlier run of it)
# starts, false of anything another session started on its own domain.
ours() {   # PIDs ros_clean.sh would kill that are on our domain
    local pid
    for pid in $(bash "$REPO/gazebo_models/scripts/ros_clean.sh" --list | tail -n +2 | awk '{print $1}'); do
        if tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | grep -x "ROS_DOMAIN_ID=$ROS_DOMAIN_ID" > /dev/null; then
            echo "$pid"
        fi
    done
}
foreign() {
    bash "$REPO/gazebo_models/scripts/ros_clean.sh" --list | tail -n +2 | while read -r pid rest; do
        [ -n "$pid" ] || continue
        tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | grep -x "ROS_DOMAIN_ID=$ROS_DOMAIN_ID" > /dev/null || echo "$pid $rest"
    done
}
sweep() {   # TERM, TERM, KILL our domain's survivors only
    local sig pids
    for sig in TERM TERM KILL; do
        pids=$(ours)
        [ -z "$pids" ] && return 0
        kill "-$sig" $pids 2>/dev/null
        sleep 2
    done
    [ -z "$(ours)" ]
}
if [ -n "$(ours)" ]; then
    say "REFUSING: processes of an earlier run on domain $ROS_DOMAIN_ID are up:"; ours; exit 3
fi
FOREIGN_AT_START="$(foreign)"
[ -n "$FOREIGN_AT_START" ] && say "NOTE: not ours (other domains), left alone: $FOREIGN_AT_START"

source "$REPO/setup_env.sh" > /dev/null 2>&1
PY=python3
[ -x "${LAB_PY:-}" ] && PY="$LAB_PY"
LAB_LAUNCH="$(readlink -f "$(ros2 pkg prefix coco_lab_ros)/share/coco_lab_ros/launch/lab_stack.launch.py")"
[ "$LAB_LAUNCH" = "$REPO/coco_lab_ros/launch/lab_stack.launch.py" ] || {
    say "REFUSING: lab_stack.launch.py resolves to $LAB_LAUNCH, not this repo"; exit 3; }

# -- the scenario -----------------------------------------------------------------
if [ "$MODE" = run ]; then
    read -r PATH_FILE HAS_ACTORS INJECT < <("$PY" - "$SCEN_FILE" "$SCENARIO" <<'EOF'
import json, sys
s = {x['id']: x for x in json.load(open(sys.argv[1]))['scenarios']}.get(sys.argv[2])
if s is None:
    print('- - -'); sys.exit(0)
inj = s.get('inject')
print(s['path'], 1 if s.get('actors') else 0,
      f"{inj['dx']},{inj['dy']},{inj['dyaw']},{inj['sigma_xy']}" if inj else '-')
EOF
)
    [ "$PATH_FILE" = "-" ] && { say "unknown scenario $SCENARIO"; exit 2; }
    PATH_ABS="$REPO/coco_lab_ros/config/lab5_paths/$PATH_FILE"
    [ -f "$PATH_ABS" ] || { say "REFUSING: no frozen path $PATH_ABS (run capture first)"; exit 3; }
fi

# -- provenance ---------------------------------------------------------------
MISSION="$REPO/gazebo_models/config/nav2_params.yaml"
OVERLAY="$REPO/coco_lab_ros/config/nav2_move_overlay.yaml"
MERGED="$OUT/nav2_move_params.yaml"
ros2 run coco_lab_ros lab_params merge --base "$MISSION" --overlay "$OVERLAY" --out "$MERGED" > "$OUT/params_merge.txt" || exit 3
cat "$OUT/params_merge.txt"
"$PY" - "$OUT/meta.json" "$REPO" "$MODE" "$SCENARIO" "$CONTROLLER" "${CID:-}" "$RUN_ID" "$MERGED" "${PATH_ABS:-}" <<'EOF'
import hashlib, json, os, subprocess, sys, time
out, repo, mode, scenario, controller, cid, run_id, merged, path_abs = sys.argv[1:10]
def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def git(*a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True).stdout.strip()
src = os.path.join(repo, 'LAB_SOURCE.txt')
pkgs = {}
for p in ('ros-jazzy-nav2-dwb-controller', 'ros-jazzy-nav2-mppi-controller',
          'ros-jazzy-nav2-regulated-pure-pursuit-controller', 'ros-jazzy-nav2-controller',
          'ros-jazzy-nav2-smac-planner', 'ros-jazzy-nav2-costmap-2d', 'ros-jazzy-nav2-amcl',
          'ros-jazzy-nav2-collision-monitor', 'ros-jazzy-nav2-velocity-smoother', 'ros-jazzy-rosbag2-py'):
    pkgs[p] = subprocess.run(['dpkg-query', '-W', '-f=${Version}', p], capture_output=True, text=True).stdout
g = 'gazebo_models/'
scen_file = os.path.join(repo, 'coco_lab_ros/config/lab5_scenarios.json')
meta = {
    'run_id': run_id, 'mode': mode, 'scenario': scenario or None,
    'controller': controller or None, 'controller_id': cid or None,
    'git_commit': git('rev-parse', 'HEAD') or None,
    'git_dirty_paths': len([l for l in git('status', '--porcelain').splitlines() if l.strip()]) if git('rev-parse', 'HEAD') else None,
    'lab_source': open(src).read().strip() if os.path.exists(src) else None,
    'ros_domain_id': os.environ.get('ROS_DOMAIN_ID'),
    'launch': ['gazebo_models full_world_robo.launch.py gui:=false traverse:=true',
               'coco_lab_ros lab_stack.launch.py params_file:=<merged> (arbiter initial_mode:=nav; nav.launch.py arbiter:=true)'],
    'sha256': {
        'mission_nav2_params': sha(os.path.join(repo, g + 'config/nav2_params.yaml')),
        'overlay': sha(os.path.join(repo, 'coco_lab_ros/config/nav2_move_overlay.yaml')),
        'merged': sha(merged),
        'scenarios': sha(scen_file),
        'path': sha(path_abs) if path_abs else None,
        'map_yaml': sha(os.path.join(repo, g + 'maps/coco_navigation.yaml')),
        'map_pgm': sha(os.path.join(repo, g + 'maps/coco_navigation.pgm')),
        'world': sha(os.path.join(repo, g + 'worlds/coco_navigation.world')),
        'navigation_world_json': sha(os.path.join(repo, g + 'config/navigation_world.json')),
    },
    'world_to_map': json.load(open(os.path.join(repo, g + 'config/navigation_world.json')))['world_to_map'],
    'packages': pkgs,
    'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'loadavg_start': open('/proc/loadavg').read().split()[:3],
}
if scenario:
    meta['scenario_def'] = {x['id']: x for x in json.load(open(scen_file))['scenarios']}[scenario]
json.dump(meta, open(out, 'w'), sort_keys=True, indent=1)
print('meta', meta['git_commit'], meta['lab_source'])
EOF
MISSION_SHA=$(sha256sum "$MISSION" | cut -d' ' -f1)
CHECK="mission nav2_params.yaml byte-identical to e06dc94 (06c308af...)"
check test "$MISSION_SHA" = 06c308aff78d4e7327212bbca280f62be7a7baef604ae41676e886b72301db8c

PGIDS=()
BAG_PGIDS=()
WATCH_PID=""
VOID=""
cleanup() {
    trap - EXIT INT TERM
    [ -n "$WATCH_PID" ] && kill -INT "$WATCH_PID" 2>/dev/null
    for pg in "${BAG_PGIDS[@]}"; do
        # rosbag2 ignores SIGINT when backgrounded (measured, Phase 5): TERM
        kill -TERM -- "-$pg" 2>/dev/null
        for _ in $(seq 1 30); do kill -0 -- "-$pg" 2>/dev/null || break; sleep 1; done
    done
    sleep 2
    for sig in INT TERM KILL; do
        alive=0
        for pg in "${PGIDS[@]}"; do kill -"$sig" -- "-$pg" 2>/dev/null && alive=1; done
        [ "$alive" = 1 ] || break
        sleep 8
    done
    sweep > "$OUT/sweep.log" 2>&1; echo "sweep exit $?" >> "$OUT/sweep.log"
    { echo "ours:"; ours; echo "foreign (left alone):"; foreign; } > "$OUT/ros_clean_after.txt" 2>&1
    "$PY" - "$OUT/meta.json" "$VOID" "$FAIL" <<'EOF'
import json, sys, time
p, void, fail = sys.argv[1:4]
m = json.load(open(p))
m['ended_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
m['loadavg_end'] = open('/proc/loadavg').read().split()[:3]
m['void_reason'] = void or None
m['runner_checks_failed'] = fail == '1'
json.dump(m, open(p, 'w'), sort_keys=True, indent=1)
EOF
    say "torn down; void='${VOID}' checks $([ "$FAIL" = 0 ] && echo PASS || echo FAIL)"
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
    local n s
    for n in "${NAV_NODES[@]}"; do
        s=$(timeout 8 ros2 lifecycle get "$n" 2>/dev/null)
        case "$s" in active*) ;; *) return 1 ;; esac
    done
}
amcl_up() { timeout 8 ros2 topic echo /amcl_pose --once --field header.stamp.sec > /dev/null 2>&1; }

# -- bring up ----------------------------------------------------------------------
setsid ros2 launch gazebo_models full_world_robo.launch.py gui:=false traverse:=true \
    > "$OUT/sim.log" 2>&1 &
PGIDS+=("$!")
wait_for "sim publishing /scan" 240 scan_up || { VOID="simulator did not publish /scan"; exit 4; }
setsid ros2 launch coco_lab_ros lab_stack.launch.py params_file:="$MERGED" \
    > "$OUT/stack.log" 2>&1 &
PGIDS+=("$!")
wait_for "all Nav2 lifecycle nodes active" 300 nav_active || { VOID="Nav2 not active"; exit 4; }
wait_for "AMCL publishing a pose" 120 amcl_up || { VOID="AMCL never published a pose"; exit 4; }
sleep 10
for n in "${NAV_NODES[@]}"; do printf '%s %s\n' "$n" "$(timeout 8 ros2 lifecycle get "$n" 2>&1)"; done > "$OUT/lifecycle.txt"

CHECK="live controller_server, planner_server and costmap params == merged file"
if ! check "$PY" -P "$HERE/lab5_watch.py" params --merged "$MERGED" --out "$OUT/params_readback.json"; then
    VOID="live parameters differ from the merged file"; exit 5
fi
CHECK="every overlay key (MPPI.*, RPP.*) is declared by its controller"
check "$PY" - "$OUT/params_readback.json" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1]))
bad = [u for u in r['undeclared'] if u[0] == '/controller_server'
       and u[1].split('.')[0] in ('MPPI', 'RPP')]
print('readback', r['per_node'], 'undeclared (all)', len(r['undeclared']), 'overlay undeclared', bad)
sys.exit(1 if bad else 0)
EOF
CHECK="all three controllers loaded (controller_server log)"
check grep -q "Created controller : RPP" "$OUT/stack.log"
CHECK="wheel topic: exactly one publisher, cmd_vel_arbiter (start)"
check "$PY" -P "$HERE/lab5_watch.py" once --out "$OUT/checks_start.json"
CHECK="arbiter mode nav (start)"
check grep '"arbiter_status": "mode=nav ' "$OUT/checks_start.json" > /dev/null
ros2 topic list -t --include-hidden-topics > "$OUT/topics.txt" 2>&1
for t in /diff_drive_controller/cmd_vel /cmd_vel_gated /cmd_vel_nav /cmd_vel_smoothed /cmd_vel \
         /cmd_vel_teleop /cmd_vel_rl /cmd_vel_approach /mission/mode /evaluation /trajectories \
         /optimal_trajectory /lookahead_point /lookahead_collision_arc /local_plan; do
    echo "===== $t"; ros2 topic info -v "$t"
done > "$OUT/graph_start.txt" 2>&1
"$PY" -P "$HERE/lab5_watch.py" watch --out "$OUT/watch.jsonl" > "$OUT/watch.log" 2>&1 &
WATCH_PID=$!

# -- the session ----------------------------------------------------------------------
if [ "$MODE" = capture ]; then
    say "capturing frozen paths"
    CHECK="every scenario path captured from SmacPlanner2D"
    check "$PY" -P "$HERE/lab5_capture.py" --scenarios "$SCEN_FILE" --out "$OUT/paths" --meta "$OUT/meta.json"
elif [ "$MODE" = snapshot ]; then
    CHECK="the global costmap settled (before)"
    check "$PY" -P "$HERE/lab5_snapshot.py" --out "$OUT/costmap_before.json" --timeout 120 || { VOID="no settled costmap"; exit 4; }
    setsid ros2 run coco_lab_ros lab_actors --ros-args -p use_sim_time:=true \
        -p scenario:=parked -p scenarios_file:="$SCEN_FILE" \
        > "$OUT/actors.log" 2>&1 &
    PGIDS+=("$!")
    actor_spawned() { grep -q "spawned .* ok" "$OUT/actors.log"; }
    CHECK="the parked person spawned in Gazebo"
    wait_for "actor spawned" 60 actor_spawned || { FAIL=1; VOID="actor did not spawn"; exit 4; }
    say "PASS $CHECK"
    CHECK="the global costmap changed and settled again (after)"
    check "$PY" -P "$HERE/lab5_snapshot.py" --out "$OUT/costmap_after.json" \
        --differ-from "$OUT/costmap_before.json" --timeout 120
    timeout 8 ros2 topic echo /scan --once > "$OUT/scan_after.txt" 2>&1
else
    SLIM=(/model/coco/odometry /amcl_pose /tf /tf_static /clock /scan
          /lab/plan /lab/status /lab/actors
          /diff_drive_controller/cmd_vel /cmd_vel_gated /cmd_vel_nav /cmd_vel_smoothed /cmd_vel
          /cmd_vel_arbiter/status /collision_monitor_state /mission/mode
          /follow_path/_action/status /follow_path/_action/feedback
          /local_plan /transformed_global_plan /received_global_plan
          /optimal_trajectory /lookahead_point /lookahead_collision_arc
          /local_costmap/costmap /local_costmap/published_footprint /initialpose
          /spin/_action/status /backup/_action/status /wait/_action/status)
    HEAVY=(/evaluation /trajectories)
    setsid ros2 bag record --use-sim-time --include-hidden-topics -s mcap \
        -o "$OUT/bag" "${SLIM[@]}" > "$OUT/bag.log" 2>&1 &
    BAG_PGIDS+=("$!")
    setsid ros2 bag record --use-sim-time -s mcap \
        -o "$OUT/heavy" "${HEAVY[@]}" > "$OUT/heavy.log" 2>&1 &
    BAG_PGIDS+=("$!")
    sleep 8
    if [ "$HAS_ACTORS" = 1 ]; then
        setsid ros2 run coco_lab_ros lab_actors --ros-args -p use_sim_time:=true \
            -p scenario:="$SCENARIO" -p scenarios_file:="$SCEN_FILE" \
            > "$OUT/actors.log" 2>&1 &
        PGIDS+=("$!")
        actor_spawned() { grep -q "spawned .* ok" "$OUT/actors.log"; }
        CHECK="actor spawned in Gazebo"
        wait_for "actor spawned" 60 actor_spawned || { FAIL=1; VOID="actor did not spawn"; exit 4; }
        say "PASS $CHECK"
        sleep 3
    fi
    if [ "$INJECT" != "-" ]; then
        IFS=, read -r DX DY DYAW SIG <<< "$INJECT"
        say "injecting the mislocalisation: /initialpose offset ($DX, $DY, $DYAW) sigma $SIG"
        CHECK="operator /initialpose injected and AMCL answered"
        check "$PY" -P "$HERE/lab5_watch.py" inject --dx "$DX" --dy "$DY" --dyaw "$DYAW" \
            --sigma "$SIG" --settle 8 --out "$OUT/inject.json"
    fi
    say "lab_planner path_file=$PATH_FILE controller_id=$CID, run $RUN_ID"
    setsid ros2 run coco_lab_ros lab_planner --ros-args -p use_sim_time:=true \
        -p path_file:="$PATH_ABS" -p controller_id:="$CID" \
        -p out_dir:="$OUT/plan" -p run_id:="$RUN_ID" -p follow_timeout:=300.0 \
        > "$OUT/planner.log" 2>&1 &
    PGIDS+=("$!")
    CHECK="lab_planner reached a terminal status"
    check "$PY" -P "$HERE/lab5_watch.py" wait-status --out "$OUT/status.json" --timeout 600
    sleep 5
fi

CHECK="wheel topic: exactly one publisher, cmd_vel_arbiter (end)"
check "$PY" -P "$HERE/lab5_watch.py" once --out "$OUT/checks_end.json"
for t in /diff_drive_controller/cmd_vel /cmd_vel_gated /cmd_vel_teleop /cmd_vel_rl /cmd_vel_approach /mission/mode; do
    echo "===== $t"; ros2 topic info -v "$t"
done > "$OUT/graph_end.txt" 2>&1
kill -INT "$WATCH_PID" 2>/dev/null; wait "$WATCH_PID" 2>/dev/null; WATCH_PID=""
CHECK="every watch sample: wheel owner cmd_vel_arbiter only, arbiter inputs unchanged, lab nodes clean"
check "$PY" - "$OUT" <<'EOF'
import json, sys
out = sys.argv[1]
rows = [json.loads(l) for l in open(out + '/watch.jsonl') if l.strip()]
start = json.load(open(out + '/checks_start.json'))['publishers']
bad = []
for r in rows:
    if not r['wheel_ok']:
        bad.append(('wheel', r['wall'], r['publishers']['/diff_drive_controller/cmd_vel']))
    for t, names in r['publishers'].items():
        if t != '/diff_drive_controller/cmd_vel' and names != start[t]:
            bad.append(('input changed', t, start[t], names))
    for node in ('lab_planner', 'lab_actors'):
        lp = r.get(node)
        if lp and lp['violations']:
            bad.append((node, lp['violations']))
    if r['arbiter_status'] is not None and not r['arbiter_status'].startswith('mode=nav '):
        bad.append(('arbiter mode', r['arbiter_status']))
mid = rows[len(rows) // 2] if rows else None
json.dump({'samples': len(rows), 'violations': bad[:50], 'violation_count': len(bad),
           'start': rows[0] if rows else None, 'middle': mid, 'end': rows[-1] if rows else None},
          open(out + '/checks.json', 'w'), sort_keys=True, indent=1)
print('watch samples', len(rows), 'violations', len(bad))
sys.exit(1 if bad or not rows else 0)
EOF
say "session finished"
exit "$FAIL"
