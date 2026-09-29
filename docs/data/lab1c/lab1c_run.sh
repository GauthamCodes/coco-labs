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
# lab1c_run.sh -- one Phase 1C session on a FRESH headless simulator.
#
#   lab1c_run.sh conformance OUT            the Smac/NavFn conformance sweep
#   lab1c_run.sh run OUT ALGO [RUN_ID]      one real run: ALGO in astar,
#                                           dijkstra, greedy (plan §E.2)
#   lab1c_run.sh dry OUT                    the dry run: a real A* run whose
#                                           data is NOT used (plan I.8)
#
# Needs COCO_WS pointing at an overlay built from this repo. ROS domain 65
# unless ROS_DOMAIN_ID is set. Every process it starts is killed by process
# group, then ros_clean.sh sweeps; it REFUSES to start if anything is up
# (CLAUDE.md §5: one Gazebo at a time, never kill what is not ours).
#
# Bringup (plan §C.3): full_world_robo.launch.py gui:=false traverse:=true,
# then lab_stack.launch.py (arbiter initial_mode:=nav + nav.launch.py
# arbiter:=true params_file:=<merged>). Never --fast.
#
# Exit: 0 all checks passed; 1 a check failed (a RESULT, recorded);
# 3 refused; 4 VOID (infrastructure, plan E.2/F-1); 5 F-3 (params differ).
set -o pipefail
# No core files: a crashing process must not fill the disk (the container
# work measured apport writing 12 GB of cores on this machine).
ulimit -c 0
MODE="${1:?usage: lab1c_run.sh conformance|run|dry OUT [ALGO] [RUN_ID]}"
OUT="${2:?usage: lab1c_run.sh MODE OUT}"
ALGO="${3:-astar}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HERE="$REPO/docs/data/lab1c"
: "${COCO_WS:?set COCO_WS to the overlay built from this repo}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-65}"
case "$ALGO" in
  astar) HEUR=euclidean ;; dijkstra) HEUR=zero ;; greedy) HEUR=euclidean ;;
  *) echo "unknown algorithm $ALGO"; exit 2 ;;
esac
[ "$MODE" = dry ] && ALGO=astar && HEUR=euclidean
RUN_ID="${4:-lab1c-$MODE-$([ "$MODE" = conformance ] || echo "$ALGO-")$(date -u +%Y%m%dT%H%M%SZ)}"
# G* (owner decision D-4): world (0.5, 6.0), yaw 0 -> map (2.5, 6.0).
GOAL_X=2.5; GOAL_Y=6.0; GOAL_YAW=0.0
mkdir -p "$OUT" || exit 3
exec > >(tee -a "$OUT/runner.log") 2>&1
say() { echo "lab1c: $* ($(date -u +%H:%M:%S) UTC)"; }
FAIL=0
check() { if "$@"; then say "PASS $CHECK"; else say "FAIL $CHECK"; FAIL=1; return 1; fi; }

# -- refuse if anything is up ---------------------------------------------
for p in 'g[z] sim' 'component_container_isolate[d]' 'parameter_bridg[e]' \
         'full_world_rob[o].launch.py' 'nav[.]launch.py' 'mission[.]launch.py' \
         'lab_stack[.]launch.py' 'cmd_vel_arbite[r]'; do
    if pgrep -af "$p"; then say "REFUSING: '$p' is running"; exit 3; fi
done
if bash "$REPO/gazebo_models/scripts/ros_clean.sh" --list | tail -n +2 | grep . >/dev/null; then
    bash "$REPO/gazebo_models/scripts/ros_clean.sh" --list
    say "REFUSING: ros_clean.sh would kill something"; exit 3
fi

source "$REPO/setup_env.sh" > /dev/null 2>&1
PY=python3
[ -x "${LAB_PY:-}" ] && PY="$LAB_PY"
LAB_LAUNCH="$(readlink -f "$(ros2 pkg prefix coco_lab_ros)/share/coco_lab_ros/launch/lab_stack.launch.py")"
[ "$LAB_LAUNCH" = "$REPO/coco_lab_ros/launch/lab_stack.launch.py" ] || {
    say "REFUSING: lab_stack.launch.py resolves to $LAB_LAUNCH, not this repo"; exit 3; }

# -- provenance ---------------------------------------------------------------
MISSION="$REPO/gazebo_models/config/nav2_params.yaml"
OVERLAY="$REPO/coco_lab_ros/config/nav2_lab_overlay.yaml"
MERGED="$OUT/nav2_lab_params.yaml"
ros2 run coco_lab_ros lab_params merge --base "$MISSION" --overlay "$OVERLAY" --out "$MERGED" > "$OUT/params_merge.txt" || exit 3
cat "$OUT/params_merge.txt"
"$PY" - "$OUT/meta.json" "$REPO" "$MODE" "$ALGO" "$HEUR" "$RUN_ID" "$MERGED" <<'EOF'
import hashlib, json, os, subprocess, sys, time
out, repo, mode, algo, heur, run_id, merged = sys.argv[1:8]
def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def git(*a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True).stdout.strip()
pkgs = {}
for p in ('ros-jazzy-nav2-smac-planner', 'ros-jazzy-nav2-navfn-planner', 'ros-jazzy-nav2-costmap-2d',
          'ros-jazzy-nav2-planner', 'ros-jazzy-nav2-controller', 'ros-jazzy-rosbag2-py'):
    pkgs[p] = subprocess.run(['dpkg-query', '-W', '-f=${Version}', p], capture_output=True, text=True).stdout
g = 'gazebo_models/'
meta = {
    'run_id': run_id, 'mode': mode, 'algorithm': algo, 'heuristic': heur,
    'graph': 'C1', 'tie_break': 'low_h',
    'goal_map': [2.5, 6.0, 0.0], 'goal_world': [0.5, 6.0, 0.0],
    'git_commit': git('rev-parse', 'HEAD'),
    'git_dirty_paths': len([l for l in git('status', '--porcelain').splitlines() if l.strip()]),
    'ros_domain_id': os.environ.get('ROS_DOMAIN_ID'),
    'launch': ['gazebo_models full_world_robo.launch.py gui:=false traverse:=true',
               'coco_lab_ros lab_stack.launch.py params_file:=<merged> (arbiter initial_mode:=nav; nav.launch.py arbiter:=true)'],
    'sha256': {
        'mission_nav2_params': sha(os.path.join(repo, g + 'config/nav2_params.yaml')),
        'overlay': sha(os.path.join(repo, 'coco_lab_ros/config/nav2_lab_overlay.yaml')),
        'merged': sha(merged),
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
json.dump(meta, open(out, 'w'), sort_keys=True, indent=1)
print('meta', meta['git_commit'], 'dirty paths', meta['git_dirty_paths'])
EOF
MISSION_SHA=$(sha256sum "$MISSION" | cut -d' ' -f1)
CHECK="mission nav2_params.yaml byte-identical to e06dc94 (06c308af...)"
check test "$MISSION_SHA" = 06c308aff78d4e7327212bbca280f62be7a7baef604ae41676e886b72301db8c

PGIDS=()
BAG_PGID=""
WATCH_PID=""
VOID=""
cleanup() {
    trap - EXIT INT TERM
    [ -n "$WATCH_PID" ] && kill -INT "$WATCH_PID" 2>/dev/null
    if [ -n "$BAG_PGID" ]; then
        kill -INT -- "-$BAG_PGID" 2>/dev/null
        for _ in $(seq 1 30); do kill -0 -- "-$BAG_PGID" 2>/dev/null || break; sleep 1; done
    fi
    sleep 2
    for sig in INT TERM KILL; do
        alive=0
        for pg in "${PGIDS[@]}"; do kill -"$sig" -- "-$pg" 2>/dev/null && alive=1; done
        [ "$alive" = 1 ] || break
        sleep 8
    done
    bash "$REPO/gazebo_models/scripts/ros_clean.sh" > "$OUT/ros_clean.log" 2>&1
    bash "$REPO/gazebo_models/scripts/ros_clean.sh" --list > "$OUT/ros_clean_after.txt" 2>&1
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

# -- bring up ----------------------------------------------------------------------
setsid ros2 launch gazebo_models full_world_robo.launch.py gui:=false traverse:=true \
    > "$OUT/sim.log" 2>&1 &
PGIDS+=("$!")
wait_for "sim publishing /scan" 240 scan_up || { VOID="F-1: simulator did not publish /scan"; exit 4; }
setsid ros2 launch coco_lab_ros lab_stack.launch.py params_file:="$MERGED" \
    > "$OUT/stack.log" 2>&1 &
PGIDS+=("$!")
wait_for "all Nav2 lifecycle nodes active" 300 nav_active || { VOID="F-1: Nav2 not active"; exit 4; }
sleep 10
for n in "${NAV_NODES[@]}"; do printf '%s %s\n' "$n" "$(timeout 8 ros2 lifecycle get "$n" 2>&1)"; done > "$OUT/lifecycle.txt"

CHECK="live planner_server + global_costmap params == merged file (F-3)"
if ! check "$PY" -P "$HERE/lab1c_watch.py" params --merged "$MERGED" --out "$OUT/params_readback.json"; then
    VOID="F-3: live parameters differ from the merged file"; exit 5
fi
CHECK="wheel topic: exactly one publisher, cmd_vel_arbiter (start)"
check "$PY" -P "$HERE/lab1c_watch.py" once --out "$OUT/checks_start.json"
CHECK="arbiter mode nav (start)"
check grep '"arbiter_status": "mode=nav ' "$OUT/checks_start.json" > /dev/null
ros2 topic list -t --include-hidden-topics > "$OUT/topics.txt" 2>&1
for t in /diff_drive_controller/cmd_vel /cmd_vel_gated /cmd_vel_nav /cmd_vel_smoothed /cmd_vel \
         /cmd_vel_teleop /cmd_vel_rl /cmd_vel_approach /mission/mode /unsmoothed_plan \
         /global_costmap/costmap_raw; do
    echo "===== $t"; ros2 topic info -v "$t"
done > "$OUT/graph_start.txt" 2>&1
"$PY" -P "$HERE/lab1c_watch.py" watch --out "$OUT/watch.jsonl" > "$OUT/watch.log" 2>&1 &
WATCH_PID=$!

# -- the session ----------------------------------------------------------------------
if [ "$MODE" = conformance ]; then
    say "conformance sweep"
    CHECK="conformance sweep ran to completion"
    check "$PY" -P "$HERE/lab1c_conformance.py" --out "$OUT" --meta "$OUT/meta.json"
else
    TOPICS=(/model/coco/odometry /amcl_pose /tf /tf_static /clock
            /lab/plan /lab/status /lab/costmap_snapshot /lab/trace_gz
            /diff_drive_controller/cmd_vel /cmd_vel_gated /cmd_vel_nav /cmd_vel_smoothed /cmd_vel
            /cmd_vel_arbiter/status /collision_monitor_state /mission/mode
            /follow_path/_action/status /follow_path/_action/feedback
            /spin/_action/status /backup/_action/status /drive_on_heading/_action/status
            /wait/_action/status /assisted_teleop/_action/status)
    setsid ros2 bag record --use-sim-time --include-hidden-topics -s mcap \
        -o "$OUT/bag" "${TOPICS[@]}" > "$OUT/bag.log" 2>&1 &
    BAG_PGID=$!
    sleep 8
    say "lab_planner $ALGO/$HEUR -> map ($GOAL_X, $GOAL_Y, $GOAL_YAW), run $RUN_ID"
    setsid ros2 run coco_lab_ros lab_planner --ros-args -p use_sim_time:=true \
        -p algorithm:="$ALGO" -p heuristic:="$HEUR" -p graph:=C1 \
        -p goal_x:=$GOAL_X -p goal_y:=$GOAL_Y -p goal_yaw:=$GOAL_YAW \
        -p out_dir:="$OUT/plan" -p run_id:="$RUN_ID" -p follow_timeout:=900.0 \
        > "$OUT/planner.log" 2>&1 &
    PGIDS+=("$!")
    CHECK="lab_planner reached a terminal status"
    check "$PY" -P "$HERE/lab1c_watch.py" wait-status --out "$OUT/status.json" --timeout 1200
    sleep 5
fi

CHECK="wheel topic: exactly one publisher, cmd_vel_arbiter (end)"
check "$PY" -P "$HERE/lab1c_watch.py" once --out "$OUT/checks_end.json"
for t in /diff_drive_controller/cmd_vel /cmd_vel_gated /cmd_vel_teleop /cmd_vel_rl /cmd_vel_approach /mission/mode; do
    echo "===== $t"; ros2 topic info -v "$t"
done > "$OUT/graph_end.txt" 2>&1
kill -INT "$WATCH_PID" 2>/dev/null; wait "$WATCH_PID" 2>/dev/null; WATCH_PID=""
CHECK="every watch sample: wheel owner cmd_vel_arbiter only, arbiter inputs unchanged, lab_planner clean"
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
    lp = r.get('lab_planner')
    if lp and lp['violations']:
        bad.append(('lab_planner', lp['violations']))
    if r['arbiter_status'] is not None and not r['arbiter_status'].startswith('mode=nav '):
        bad.append(('arbiter mode', r['arbiter_status']))
no_status = sum(1 for r in rows if r['arbiter_status'] is None)
mid = rows[len(rows) // 2] if rows else None
json.dump({'samples': len(rows), 'samples_without_arbiter_status': no_status,
           'violations': bad[:50], 'violation_count': len(bad),
           'start': rows[0] if rows else None, 'middle': mid, 'end': rows[-1] if rows else None},
          open(out + '/checks.json', 'w'), sort_keys=True, indent=1)
print('watch samples', len(rows), 'violations', len(bad))
sys.exit(1 if bad or not rows else 0)
EOF
say "session finished"
exit "$FAIL"
