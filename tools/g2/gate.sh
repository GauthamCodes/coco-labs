#!/usr/bin/env bash
# G2.6: the reliability gate -- N fresh simulators in a row, each driving a goal file through
# Gazebo + Nav2 (tools/m6/m6f8_run.sh: headless, never --fast, one simulator at a time, cleaned up
# after each run), on a generated level (GEN) and its world (WORLD).
#
#   COCO_WS=<overlay> GEN=<gen>/coco_depot_v1 WORLD=<.../gazebo_models/worlds/coco_depot_v1.sdf> \
#     tools/g2/gate.sh GOALS.json OUT_PREFIX N [m6f8_nav.py flags...]
#
# Writes OUT_PREFIX_1 .. OUT_PREFIX_N (the runner's raw output) and prints one line per run: the
# legs' status. A run passes when every leg SUCCEEDED.
set -u
GOALS="$1"; PREFIX="$2"; N="$3"; shift 3
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pass=0
for k in $(seq 1 "$N"); do
  out="${PREFIX}_$k"
  "$HERE/../m6/m6f8_run.sh" "$GOALS" "$out" "$@" > "$out.log" 2>&1
  rc=$?
  legs=$(python3 -c "import json,sys; r=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]; print(' '.join(f\"{x['id']}:{x['status']}\" for x in r))" "$out/results.jsonl" 2>/dev/null)
  ok=$(python3 -c "import json,sys; r=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]; print(int(bool(r) and all(x['status']=='SUCCEEDED' for x in r)))" "$out/results.jsonl" 2>/dev/null || echo 0)
  pass=$((pass + ok))
  echo "gate run $k/$N rc=$rc pass=$ok $legs"
done
echo "GATE $pass/$N"
