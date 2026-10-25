#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# G2 per-round gate (owner, 2026-10-25): every distinct Fetch Rush phone round and every Fetch by
# colour round must succeed N of N times in Gazebo + Nav2 (STACK; headless, never --fast, one
# simulator at a time, a fresh simulator per run: tools/m6/m6f8_run.sh --initial-pose, as G2.6).
#
#   COCO_WS=<overlay> tools/g2/round_gate.sh RUNS_DIR N ROUND...
#
# ROUND is phone:<seed> (Fetch Rush rules 5, level coco_depot_v1) or colour:<colour> (Fetch by
# colour, level coco_depot_colours_v1). Per level the generated files and world come from
#   GEN_DEPOT / WORLD_DEPOT, GEN_COLOURS / WORLD_COLOURS (defaults below: derivation 2 at the gate's
#   resolutions, tools/m6/gen_level.py --derivation 2 --nav-res 0.05 --arena-res 0.1 --arena-res 0.05).
# Before each run it waits until no simulator or launch has been up for QUIET_S seconds (another
# agent's Gazebo must never share the laptop). A run the runner refuses (exit 3: something was up)
# or voids (exit 4: the stack never came up) is retried and logged, not counted; at most MAX_VOID
# per round. Prints one line per run and "ROUND <id> <pass>/<N>"; writes RUNS_DIR/gate_rounds.jsonl.
set -u
RUNS="$(mkdir -p "$1" && cd "$1" && pwd)"; N="$2"; shift 2
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
: "${COCO_WS:?set COCO_WS to the overlay built from this repo}"
R="$HOME/coco_lab_runs/g2"
GEN_DEPOT="${GEN_DEPOT:-$R/gen_d2v2/coco_depot_v1}"
WORLD_DEPOT="${WORLD_DEPOT:-$R/gazebo_models/worlds/coco_depot_v1.sdf}"
GEN_COLOURS="${GEN_COLOURS:-$R/gen_colours_d2_gate/coco_depot_colours_v1}"
WORLD_COLOURS="${WORLD_COLOURS:-$R/colours/gazebo_models/worlds/coco_depot_colours_v1.sdf}"
QUIET_S="${QUIET_S:-60}"
MAX_VOID="${MAX_VOID:-3}"
PY="$HOME/coco_labs_ws/test_venv/bin/python"
SIMS='g[z] sim|full_world_rob[o].launch.py|nav[.]launch.py|mission[.]launch.py|gzserve[r]|isaac-si[m]'

quiet() {
    local q=0
    while [ "$q" -lt "$QUIET_S" ]; do
        if pgrep -f "$SIMS" > /dev/null; then
            [ "$q" -gt 0 ] || echo "  waiting: a simulator is up ($(pgrep -af "$SIMS" | head -1 | cut -c1-80))"
            q=0; sleep 30
        else
            q=$((q + 5)); sleep 5
        fi
    done
}

legs() {
    "$PY" -c "
import json, sys
r = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
print(int(bool(r) and all(x['status'] == 'SUCCEEDED' for x in r)), ' '.join(f\"{x['id']}:{x['status']}\" for x in r))
" "$1" 2>/dev/null || echo "0 no-results"
}

for round in "$@"; do
    kind="${round%%:*}"; arg="${round#*:}"
    case "$kind" in
        phone) level=coco_depot_v1; gen="$GEN_DEPOT"; world="$WORLD_DEPOT"; id="r5_phone_seed$arg"
               goalargs=(ghost --rules 5 --mode phone --seed "$arg") ;;
        colour) level=coco_depot_colours_v1; gen="$GEN_COLOURS"; world="$WORLD_COLOURS"; id="colour_$arg"
                goalargs=(colour --colour "$arg") ;;
        *) echo "unknown round $round"; exit 2 ;;
    esac
    goals="$RUNS/goals_$id.json"
    PYTHONPATH="$REPO/coco_schemas:$REPO/coco_schemas/coco_schemas/gen:$REPO/coco_lab:$REPO/coco_config" "$PY" -P "$REPO/tools/m6/m6f8_goals.py" "${goalargs[@]}" "$goals" > /dev/null || exit 2
    pass=0; k=0; voids=0
    while [ "$k" -lt "$N" ]; do
        quiet
        out="$RUNS/${id}_run$((k + 1))"
        [ -e "$out" ] && out="${out}_retry$voids"
        LEVEL="$level" GEN="$gen" WORLD="$world" "$REPO/tools/m6/m6f8_run.sh" "$goals" "$out" --initial-pose \
            > "$out.log" 2>&1
        rc=$?
        if [ "$rc" -eq 3 ] || [ "$rc" -eq 4 ]; then
            voids=$((voids + 1))
            echo "  $id run $((k + 1)): VOID (runner rc $rc), retry $voids/$MAX_VOID"
            printf '{"round": "%s", "run": %d, "dir": "%s", "rc": %d, "void": true}\n' "$id" $((k + 1)) "$out" "$rc" >> "$RUNS/gate_rounds.jsonl"
            [ "$voids" -ge "$MAX_VOID" ] && { echo "ROUND $id ABORTED: $voids void runs"; continue 2; }
            continue
        fi
        read -r ok detail < <(legs "$out/results.jsonl")
        k=$((k + 1)); pass=$((pass + ok))
        echo "  $id run $k/$N rc=$rc pass=$ok $detail"
        printf '{"round": "%s", "run": %d, "dir": "%s", "rc": %d, "void": false, "pass": %d}\n' "$id" "$k" "$out" "$rc" "$ok" >> "$RUNS/gate_rounds.jsonl"
    done
    echo "ROUND $id $pass/$N"
done
