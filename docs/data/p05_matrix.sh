#!/usr/bin/env bash
# The Phase 5 matrix: 16 searching missions, each on a fresh simulator, in a
# fixed order. Resumable: a run with result.json is done and skipped; a run
# directory WITHOUT one (a reboot, a crash of the runner itself) is renamed
# NAME.void-N -- kept as evidence -- and run again.
#
#   matrix.sh            run what is left
#   matrix.sh --list     print the plan
#
# Groups (policy order at d = 0.9: bay_3, bay_4, bay_2, bay_1; FIXED layout
# red=bay_1 green=bay_2 blue=bay_3 yellow=bay_4):
#   A fixed      FIXED, each colour, the robot's policy
#   B colours    COLOURS, red; the first seed (from 1) that puts red in each
#                bay: bay_1 5, bay_2 1, bay_3 7, bay_4 2 (placement only)
#   D negative   POSITIONS, red, seeds 1-4 (red in bay_2, bay_4, bay_2,
#                bay_2: never the first bay searched)
#   C orders     FIXED green (identical placement to A's green), given
#                orders: stop after bay_3; nearest-first; most-likely-first;
#                bay_4,bay_1,bay_2,bay_3
PLAN=(
  "A1_fixed_red fixed 0 red"
  "A2_fixed_green fixed 0 green"
  "A3_fixed_blue fixed 0 blue"
  "A4_fixed_yellow fixed 0 yellow"
  "B1_colours_s5_red colours 5 red"
  "B2_colours_s1_red colours 1 red"
  "B3_colours_s7_red colours 7 red"
  "B4_colours_s2_red colours 2 red"
  "D1_positions_s1_red positions 1 red"
  "D2_positions_s2_red positions 2 red"
  "D3_positions_s3_red positions 3 red"
  "D4_positions_s4_red positions 4 red"
  "C1_green_stop_after_bay3 fixed 0 green bay_3"
  "C2_green_nearest fixed 0 green bay_3,bay_2,bay_1,bay_4"
  "C3_green_most_likely fixed 0 green bay_1,bay_2,bay_3,bay_4"
  "C4_green_reverse fixed 0 green bay_4,bay_1,bay_2,bay_3"
)
ROOT="$HOME/coco_lab_runs/lab4/matrix"
mkdir -p "$ROOT"
if [ "${1:-}" = "--list" ]; then printf '%s\n' "${PLAN[@]}"; exit 0; fi
for row in "${PLAN[@]}"; do
  read -r name level seed colour order <<< "$row"
  out="$ROOT/$name"
  if [ -f "$out/result.json" ]; then echo "[matrix] $name done"; continue; fi
  if [ -d "$out" ]; then
    n=1; while [ -d "$out.void-$n" ]; do n=$((n + 1)); done
    mv "$out" "$out.void-$n"; echo "[matrix] $name incomplete -> $name.void-$n"
  fi
  echo "[matrix] $name start $(date -u +%H:%M:%S)"
  "$(dirname "${BASH_SOURCE[0]}")/p05_run_one.sh" "matrix/$name" "$level" "$seed" "$colour" $order
  echo "[matrix] $name exit=$? $(date -u +%H:%M:%S)"
done
echo "[matrix] all done $(date -u +%H:%M:%S)"
