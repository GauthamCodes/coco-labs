#!/usr/bin/env bash
# run.sh RUNDIR SCENARIO ARGS...: fresh stack, recorder, probe, teardown.
D="$(cd "$(dirname "$0")" && pwd)"
RUN="$1"; shift
mkdir -p "$RUN"
"$D/up.sh" "$RUN" || exit 1
"$D/ros.sh" python3 "$D/recorder.py" "$RUN/ros.jsonl" &
REC=$!
sleep 2
cd "$RUN" && "$D/ros.sh" python3 "$D/probe.py" "$RUN/ws.jsonl" "$@"
echo "probe exit $?"
sleep 1
kill -INT "$REC"; wait "$REC" 2>/dev/null
bash "$HOME/coco_live_ws/src/coco-labs/gazebo_models/scripts/ros_clean.sh" 2>&1 | tail -1
sleep 3
echo "gz left: $(pgrep -f 'g[z] sim' | wc -l)"
