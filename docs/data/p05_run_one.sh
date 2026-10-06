#!/usr/bin/env bash
# One Phase 5 Gazebo run from the copy overlay. Usage:
#   run.sh NAME LEVEL SEED COLOUR [SEARCH_ORDER]
# Output: ~/coco_lab_runs/lab4/NAME (runner.log, logs, streams, result.json)
export COCO_WS="$HOME/coco_search_ws"
export COCO_WT="$COCO_WS/src/coco-labs"
NAME="${1:?name}"; shift
OUT="$HOME/coco_lab_runs/lab4/$NAME"
mkdir -p "$HOME/coco_lab_runs/lab4"
"$COCO_WT/docs/data/p05_search_run.sh" "$OUT" "$@" > /dev/null 2>&1
code=$?
echo "exit=$code"
tail -4 "$OUT/runner.log"
exit $code
