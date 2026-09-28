#!/usr/bin/env bash
set -e

RUNS=(
    "fixed 0 red /home/gautham/coco_runs_p03c/run_fixed_red"
    "fixed 0 green /home/gautham/coco_runs_p03c/run_fixed_green"
    "fixed 0 yellow /home/gautham/coco_runs_p03c/run_fixed_yellow"
    "colours 2 green /home/gautham/coco_runs_p03c/run_colours_s2_green"
    "colours 3 blue /home/gautham/coco_runs_p03c/run_colours_s3_blue"
    "colours 4 yellow /home/gautham/coco_runs_p03c/run_colours_s4_yellow"
    "positions 20 green /home/gautham/coco_runs_p03c/run_positions_s20_green"
    "positions 30 blue /home/gautham/coco_runs_p03c/run_positions_s30_blue"
    "positions 40 yellow /home/gautham/coco_runs_p03c/run_positions_s40_yellow"
)

SCRIPT="/home/gautham/coco-p03c-consolidation/scripts/consolidation_run.sh"
REPORT="/home/gautham/coco-p03c-consolidation/docs/data/navigation_world_report.py"

for line in "${RUNS[@]}"; do
    read -r LEVEL SEED COLOUR OUT <<< "$line"
    echo "=========================================================="
    echo "Starting matrix run: LEVEL=$LEVEL SEED=$SEED COLOUR=$COLOUR"
    echo "Output: $OUT"
    echo "=========================================================="
    rm -rf "$OUT"
    bash "$SCRIPT" "$OUT" "$COLOUR" "$LEVEL" "$SEED" || true
    if [ -f "$OUT/visual_topics.json" ]; then
        python3 "$REPORT" "$OUT" --out "$OUT/report.json" || true
    fi
    sleep 3
done

echo "All remaining matrix runs finished!"
