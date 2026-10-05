#!/bin/bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# Phase 4: every backend x arm on every recorded drive, one at a time, 1.0x.
#
#   lab3_batch.sh RUNS_DIR
#
# MODE=sync in the environment runs slam_toolbox's synchronous node (see
# slam_replay.sh); Cartographer is the same in both.
#
# Writes RUNS_DIR/backends/<drive>_<backend>_<arm>/ (slam_replay.sh) and
# RUNS_DIR/backends/<...>/score.json (an_backend.py). A run directory that
# already exists is skipped (re-running resumes; nothing is overwritten).
set -u
RUNS="${1:?usage: lab3_batch.sh RUNS_DIR}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$RUNS/backends"
for drive in s1_tour 1_tour; do
    for backend in ${BACKENDS:-slam_toolbox cartographer}; do
        for arm in loop noloop; do
            out="$RUNS/backends/${drive}_${backend}_${arm}"
            if [ -e "$out" ]; then echo "skip $out"; continue; fi
            "$HERE/slam_replay.sh" "$backend" "$arm" "$RUNS/drives/$drive" "$out"
            (cd "$HERE" && python3 an_backend.py "$RUNS/drives/$drive" "$out" \
                --out "$out/score.json") || echo "SCORE FAILED $out"
        done
    done
done
echo "batch done $(date -u +%H:%M:%S) UTC"
