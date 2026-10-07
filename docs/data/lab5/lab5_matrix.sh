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
# lab5_matrix.sh -- Phase 6's measured matrix, one fresh simulator per run.
#
#   lab5_matrix.sh OUT_ROOT [REPEATS]
#
# For each scenario (static_room, crossing, oncoming: REPEATS runs per
# controller, default 5; mislocalised: 3), the controllers are INTERLEAVED
# (DWB, MPPI, RPP, DWB, ...) so a slow drift in machine load lands on all
# three alike. Each run is lab5_run.sh, then lab5_extract.py (run.json),
# then, for actor scenarios, lab5_actor_seen.py; the heavy bag is then
# hashed into run.json and deleted (KEEP_HEAVY=1 keeps it).
#
# Resumable: a run directory with run.json is done and skipped; one without
# (an interrupted or VOID run) is renamed NAME.void-K and run again, at most
# twice. A refusal (exit 3: something else is running) stops the matrix.
set -o pipefail
ROOT="${1:?usage: lab5_matrix.sh OUT_ROOT [REPEATS]}"
REPEATS="${2:-5}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${COCO_WS:?set COCO_WS}"
mkdir -p "$ROOT"
LOG="$ROOT/matrix_driver.log"
say() { echo "matrix: $* ($(date -u +%H:%M:%S) UTC)" | tee -a "$LOG"; }

plan() {
    local sc n k c
    for sc in static_room crossing oncoming mislocalised; do
        n="$REPEATS"; [ "$sc" = mislocalised ] && n=3
        for k in $(seq 1 "$n"); do
            for c in DWB MPPI RPP; do echo "$sc $c $k"; done
        done
    done
}

plan | while read -r SC C K; do
    NAME="${SC}_${C}_${K}"
    DIR="$ROOT/$NAME"
    [ -f "$DIR/run.json" ] && continue
    for attempt in 1 2 3; do
        if [ -d "$DIR" ]; then
            v=1; while [ -e "$DIR.void-$v" ]; do v=$((v + 1)); done
            mv "$DIR" "$DIR.void-$v"; say "$NAME: earlier attempt set aside as .void-$v"
        fi
        say "$NAME: run (attempt $attempt)"
        "$HERE/lab5_run.sh" run "$DIR" "$SC" "$C" "lab5-$NAME" > /dev/null 2>&1 < /dev/null
        code=$?
        say "$NAME: runner exit $code"
        [ "$code" = 3 ] && { say "REFUSED: stopping the matrix"; exit 3; }
        [ "$code" = 4 ] || [ "$code" = 5 ] && continue
        python3 -P "$HERE/lab5_extract.py" "$DIR" >> "$LOG" 2>&1 || { say "$NAME: extract FAILED"; continue; }
        if [ "$SC" = crossing ] || [ "$SC" = oncoming ]; then
            python3 -P "$HERE/lab5_actor_seen.py" "$DIR" >> "$LOG" 2>&1
        fi
        if [ "${KEEP_HEAVY:-0}" != 1 ] && [ -f "$DIR/run.json" ]; then
            du -sb "$DIR/heavy" >> "$DIR/heavy_deleted.txt" 2>&1
            rm -rf "$DIR/heavy"
        fi
        break
    done
done
say "matrix finished"
