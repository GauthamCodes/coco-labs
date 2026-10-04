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
# lab2_run.sh -- one Phase 3 (Lab 2, Localise) session on a FRESH headless
# simulator. Modelled on docs/data/lab1c/lab1c_run.sh.
#
#   lab2_run.sh fidelity OUT              scans at 40 seeded poses, then the
#                                         three scripted drives (straight,
#                                         square, tour), all bagged
#   lab2_run.sh kidnap OUT ARM TARGET     the kidnap A/B: ARM shipped|recovery,
#                                         TARGET K1..K5 (map frame, below)
#
# Needs COCO_WS pointing at an overlay built from this repo. ROS domain 66
# unless ROS_DOMAIN_ID is set. Every process it starts is killed by process
# group, then ros_clean.sh sweeps; it REFUSES to start if anything is up
# (CLAUDE.md §5: one Gazebo at a time, never kill what is not ours).
#
# Bringup: full_world_robo.launch.py gui:=false traverse:=true, then
# coco_lab_ros lab_stack.launch.py params_file:=<mission + loc overlay>
# (arbiter initial_mode:=nav; nav.launch.py arbiter:=true). Never --fast.
# The robot is moved only by gz set_pose (the kidnap) and /cmd_vel_teleop,
# an arbiter INPUT; the wheel topic's publishers are checked throughout.
#
# Exit: 0 all checks passed; 1 a check failed (a RESULT, recorded);
# 3 refused; 4 VOID (infrastructure); 5 live params differ from the merge.
set -o pipefail
ulimit -c 0
MODE="${1:?usage: lab2_run.sh fidelity|kidnap OUT [ARM TARGET]}"
OUT="${2:?usage: lab2_run.sh MODE OUT}"
ARM="${3:-shipped}"
TARGET="${4:-}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HERE="$REPO/docs/data/lab2"
L1C="$REPO/docs/data/lab1c"
: "${COCO_WS:?set COCO_WS to the overlay built from this repo}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-66}"
case "$ARM" in shipped|recovery) ;; *) echo "unknown arm $ARM"; exit 2 ;; esac
# Kidnap targets, MAP frame (x, y, yaw): free cells with >= 0.75 m of
# clearance on the saved map, away from the spawn at (0, 0).
case "$TARGET" in
  K1) TO="16.0,0.0,1.5708" ;;
  K2) TO="-3.0,7.0,0.0" ;;
  K3) TO="14.0,6.5,3.1416" ;;
  K4) TO="-3.0,-7.0,1.5708" ;;
  K5) TO="2.0,-7.5,0.0" ;;
  "") [ "$MODE" = kidnap ] && { echo "kidnap needs a TARGET K1..K5"; exit 2; } ;;
  *) echo "unknown target $TARGET"; exit 2 ;;
esac
mkdir -p "$OUT" || exit 3
exec > >(tee -a "$OUT/runner.log") 2>&1
say() { echo "lab2: $* ($(date -u +%H:%M:%S) UTC)"; }
FAIL=0
check() { if "$@"; then say "PASS $CHECK"; else say "FAIL $CHECK"; FAIL=1; return 1; fi; }

# -- refuse if anything is up ---------------------------------------------
for p in 'g[z] sim' 'component_container_isolate[d]' 'parameter_bridg[e]' \
         'full_world_rob[o].launch.py' 'nav[.]launch.py' 'mission[.]launch.py' \
         'lab_stack[.]launch.py' 'cmd_vel_arbite[r]' 'ekf_nod[e]'; do
    if pgrep -af "$p"; then say "REFUSING: '$p' is running"; exit 3; fi
done
if bash "$REPO/gazebo_models/scripts/ros_clean.sh" --list | tail -n +2 | grep . >/dev/null; then
    bash "$REPO/gazebo_models/scripts/ros_clean.sh" --list
    say "REFUSING: ros_clean.sh would kill something"; exit 3
fi

source "$REPO/setup_env.sh" > /dev/null 2>&1
PY=python3
LAB_LAUNCH="$(readlink -f "$(ros2 pkg prefix coco_lab_ros)/share/coco_lab_ros/launch/lab_stack.launch.py")"
[ "$LAB_LAUNCH" = "$REPO/coco_lab_ros/launch/lab_stack.launch.py" ] || {
    say "REFUSING: lab_stack.launch.py resolves to $LAB_LAUNCH, not this repo"; exit 3; }

# -- provenance ---------------------------------------------------------------
MISSION="$REPO/gazebo_models/config/nav2_params.yaml"
OVERLAY="$REPO/coco_lab_ros/config/nav2_loc_$ARM.yaml"
MERGED="$OUT/nav2_lab_params.yaml"
ros2 run coco_lab_ros lab_params merge --base "$MISSION" --overlay "$OVERLAY" --out "$MERGED" > "$OUT/params_merge.txt" || exit 3
cat "$OUT/params_merge.txt"
"$PY" - "$OUT/meta.json" "$REPO" "$MODE" "$ARM" "$TARGET" "$TO" "$MERGED" <<'EOF'
import hashlib, json, os, subprocess, sys, time
out, repo, mode, arm, target, to, merged = sys.argv[1:8]
def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def git(*a):
    return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True).stdout.strip()
g = 'gazebo_models/'
pkgs = {p: subprocess.run(['dpkg-query', '-W', '-f=${Version}', p], capture_output=True, text=True).stdout
        for p in ('ros-jazzy-nav2-amcl', 'ros-jazzy-robot-localization', 'ros-jazzy-ros-gz-sim')}
meta = {
    'mode': mode, 'arm': arm, 'target': target or None,
    'kidnap_to_map': [float(v) for v in to.split(',')] if to else None,
    'git_commit': git('rev-parse', 'HEAD') or None,
    'git_dirty_paths': len([l for l in git('status', '--porcelain').splitlines() if l.strip()]),
    # an overlay source COPY has no git metadata: the copy step writes
    # LAB_SOURCE.txt ("<commit> <dirty path count>") from the checkout
    'source_copy_of': (open(os.path.join(repo, 'LAB_SOURCE.txt')).read().split()
                       if os.path.exists(os.path.join(repo, 'LAB_SOURCE.txt')) else None),
    'ros_domain_id': os.environ.get('ROS_DOMAIN_ID'),
    'launch': ['gazebo_models full_world_robo.launch.py gui:=false traverse:=true',
               'coco_lab_ros lab_stack.launch.py params_file:=<mission + nav2_loc_%s.yaml>' % arm],
    'sha256': {
        'mission_nav2_params': sha(os.path.join(repo, g + 'config/nav2_params.yaml')),
        'overlay': sha(os.path.join(repo, 'coco_lab_ros/config/nav2_loc_%s.yaml' % arm)),
        'merged': sha(merged),
        'map_yaml': sha(os.path.join(repo, g + 'maps/coco_navigation.yaml')),
        'map_pgm': sha(os.path.join(repo, g + 'maps/coco_navigation.pgm')),
        'world': sha(os.path.join(repo, g + 'worlds/coco_navigation.world')),
        'probe': sha(os.path.join(repo, 'docs/data/lab2/lab2_probe.py')),
        'sketch_py': sha(os.path.join(repo, 'coco_lab/coco_lab/sketch.py')),
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
wait_for "sim publishing /scan" 240 scan_up || { VOID="simulator did not publish /scan"; exit 4; }
setsid ros2 launch coco_lab_ros lab_stack.launch.py params_file:="$MERGED" \
    > "$OUT/stack.log" 2>&1 &
PGIDS+=("$!")
wait_for "all Nav2 lifecycle nodes active" 300 nav_active || { VOID="Nav2 not active"; exit 4; }
sleep 10

CHECK="live AMCL recovery_alpha_* == the merged file"
"$PY" - "$MERGED" "$OUT/params_readback.json" <<'EOF'
import json, subprocess, sys, yaml
merged, out = sys.argv[1:3]
want = yaml.safe_load(open(merged))['amcl']['ros__parameters']
got = {}
for k in ('recovery_alpha_fast', 'recovery_alpha_slow', 'max_particles', 'min_particles',
          'alpha1', 'alpha2', 'alpha3', 'alpha4', 'sigma_hit', 'z_hit', 'z_rand',
          'laser_model_type', 'update_min_d', 'update_min_a', 'max_beams'):
    r = subprocess.run(['ros2', 'param', 'get', '/amcl', k], capture_output=True, text=True, timeout=20)
    txt = r.stdout.strip().split(':', 1)[-1].strip()
    try:
        got[k] = float(txt)
    except ValueError:
        got[k] = txt
bad = {k: (want[k], got[k]) for k in got if isinstance(got[k], float) and abs(float(want[k]) - got[k]) > 1e-12}
json.dump({'want': {k: want[k] for k in got}, 'got': got, 'mismatch': bad}, open(out, 'w'), indent=1, sort_keys=True)
print('amcl readback', got, 'mismatch', bad)
sys.exit(1 if bad else 0)
EOF
[ $? = 0 ] && say "PASS $CHECK" || { say "FAIL $CHECK"; FAIL=1; VOID="live params differ"; exit 5; }

CHECK="wheel topic: exactly one publisher, cmd_vel_arbiter (start)"
check "$PY" -P "$L1C/lab1c_watch.py" once --out "$OUT/checks_start.json"
"$PY" -P "$L1C/lab1c_watch.py" watch --out "$OUT/watch.jsonl" > "$OUT/watch.log" 2>&1 &
WATCH_PID=$!

TOPICS=(/model/coco/odometry /diff_drive_controller/odom /imu /scan /amcl_pose /tf /tf_static /clock
        /cmd_vel_teleop /diff_drive_controller/cmd_vel /cmd_vel_arbiter/status)
setsid ros2 bag record --use-sim-time --include-hidden-topics -s mcap \
    -o "$OUT/bag" "${TOPICS[@]}" > "$OUT/bag.log" 2>&1 &
BAG_PGID=$!
sleep 8

# -- the session ----------------------------------------------------------------------
PROBE=("$PY" -P "$HERE/lab2_probe.py")
if [ "$MODE" = fidelity ]; then
    CHECK="scans at 40 seeded poses (seed ${FIDELITY_SEED:-0})"
    check "${PROBE[@]}" scans --n 40 --seed "${FIDELITY_SEED:-0}" --out "$OUT/scans.jsonl"
    CHECK="drive straight"
    check "${PROBE[@]}" drive --label straight --start=-5.0,0.0,0.0 \
        --route="1.5,0.0" --out "$OUT/drives.jsonl"
    CHECK="drive square (two laps, in-place 90-degree turns)"
    check "${PROBE[@]}" drive --label square --start=-2.5,-1.0,1.5708 \
        --route="-2.5,1.0;-4.5,1.0;-4.5,-1.0;-2.5,-1.0;-2.5,1.0;-4.5,1.0;-4.5,-1.0;-2.5,-1.0" \
        --out "$OUT/drives.jsonl"
    CHECK="drive tour (121 m, coco_lab A* waypoints)"
    check "${PROBE[@]}" drive --label tour --start=-1.0,0.0,0.0 --timeout 900 \
        --route="$(cat "$HERE/tour_route.txt")" --out "$OUT/drives.jsonl"
else
    CHECK="kidnap $TARGET ($TO), arm $ARM"
    check "${PROBE[@]}" kidnap --to="$TO" --rotate-s 180 --out "$OUT/kidnap.jsonl"
fi

CHECK="wheel topic: exactly one publisher, cmd_vel_arbiter (end)"
check "$PY" -P "$L1C/lab1c_watch.py" once --out "$OUT/checks_end.json"
kill -INT "$WATCH_PID" 2>/dev/null; wait "$WATCH_PID" 2>/dev/null; WATCH_PID=""
CHECK="every watch sample: wheel owner cmd_vel_arbiter only"
check "$PY" - "$OUT" <<'EOF'
import json, sys
out = sys.argv[1]
rows = [json.loads(l) for l in open(out + '/watch.jsonl') if l.strip()]
bad = [r['wall'] for r in rows if not r['wheel_ok']]
json.dump({'samples': len(rows), 'wheel_violations': len(bad), 'first': bad[:10]},
          open(out + '/checks.json', 'w'), sort_keys=True, indent=1)
print('watch samples', len(rows), 'wheel violations', len(bad))
sys.exit(1 if bad or not rows else 0)
EOF
say "session finished"
exit "$FAIL"
