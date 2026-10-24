#!/usr/bin/env bash
# G2.6: record Race Nav2's ghosts -- one Gazebo + Nav2 run per distinct Fetch Rush rules-4 phone
# round (seeds drawing the same round share it), each on a fresh simulator, then convert them
# (tools/g2/make_ghost.py) into lab_web/public/stack/ghosts/ and write the index
# (tools/g2/ghost_index.py). STACK evidence; raw runs stay in RUNS (outside git).
#
#   COCO_WS=<overlay> GEN=<gen d2>/coco_depot_v1 WORLD=<.../worlds/coco_depot_v1.sdf> \
#     tools/g2/record_ghosts.sh RUNS_DIR
set -u
RUNS="$(mkdir -p "$1" && cd "$1" && pwd)"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$REPO/lab_web/public/stack/ghosts"
mkdir -p "$OUT"
seeds=$(PYTHONPATH="$REPO/coco_lab" python3 -c "
import json
from coco_lab import games
doc = games.load_rounds(rules=4)
seen = {}
for s, r in sorted(doc['rounds']['phone'].items(), key=lambda kv: int(kv[0])):
    k = json.dumps([r['region'], r['orders']])
    seen.setdefault(k, s)
print(' '.join(seen.values()))")
echo "distinct phone rounds, first seed of each: $seeds"
for s in $seeds; do
  g="$RUNS/goals_r4_phone_seed$s.json"
  PYTHONPATH="$REPO/coco_lab" python3 "$REPO/tools/m6/m6f8_goals.py" ghost "$g" --rules 4 --mode phone --seed "$s" > /dev/null
  run="$RUNS/ghost_r4_phone_seed$s"
  "$REPO/tools/m6/m6f8_run.sh" "$g" "$run" --initial-pose > "$run.log" 2>&1
  echo "seed $s: runner rc=$?"
  ( set +u; source /opt/ros/jazzy/setup.bash > /dev/null 2>&1; python3 "$REPO/tools/g2/make_ghost.py" "$run" "$g" "$OUT/r4_phone_seed$s.json" )
done
PYTHONPATH="$REPO/coco_lab" python3 "$REPO/tools/g2/ghost_index.py"
