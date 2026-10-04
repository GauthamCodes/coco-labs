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
# lab2_batch.sh ROOT SESSION...  -- run lab2_run.sh sessions one after the
# other, each on its own fresh simulator, into ROOT/<name>.
#
#   SESSION is  fidelity:<seed>  or  kidnap:<arm>:<target>
#
# Before each session it waits until no Gazebo has run for 60 s (another
# project shares this machine; CLAUDE.md §5: one Gazebo at a time, and we
# never kill what is not ours). A session the runner REFUSES (exit 3,
# something came up in between) is retried after the next quiet minute, up
# to 5 times. A session that ran is never re-run here: its exit code -- a
# result or a VOID -- is recorded in ROOT/batch.tsv.
set -o pipefail
ROOT="${1:?usage: lab2_batch.sh ROOT SESSION...}"
shift
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$ROOT"
quiet_gz() {
    local quiet=0
    while [ "$quiet" -lt 60 ]; do
        if pgrep -f 'g[z] sim' > /dev/null; then quiet=0; else quiet=$((quiet + 10)); fi
        sleep 10
    done
}
for s in "$@"; do
    IFS=: read -r mode a b <<< "$s"
    case "$mode" in
      fidelity) name="fidelity_s$a"; args=(fidelity "$ROOT/$name") ;;
      kidnap) name="kidnap_${a}_$b"; args=(kidnap "$ROOT/$name" "$a" "$b") ;;
      *) echo "bad session $s"; exit 2 ;;
    esac
    for attempt in 1 2 3 4 5; do
        quiet_gz
        echo "batch: $name attempt $attempt $(date -u +%H:%M:%S)"
        if [ "$mode" = fidelity ]; then
            FIDELITY_SEED="$a" "$HERE/lab2_run.sh" "${args[@]}" > "$ROOT/$name.out" 2>&1
        else
            "$HERE/lab2_run.sh" "${args[@]}" > "$ROOT/$name.out" 2>&1
        fi
        rc=$?
        [ "$rc" = 3 ] && { mv "$ROOT/$name" "$ROOT/$name.refused$attempt" 2>/dev/null; continue; }
        break
    done
    printf '%s\t%s\t%s\n' "$name" "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ROOT/batch.tsv"
    echo "batch: $name exit $rc"
done
echo "batch: done"
