#!/usr/bin/env bash
# docker_run.sh RUNDIR SCENARIO ARGS...: compose up the `live` image, record
# inside the container, drive from the host over :8080, copy out, compose down.
D="$(cd "$(dirname "$0")" && pwd)"
RUN="$1"; shift
mkdir -p "$RUN"
REPO="$HOME/coco_live_ws/src/coco-labs"
if pgrep -f 'g[z] sim' >/dev/null 2>&1; then echo "GAZEBO ALREADY RUNNING"; exit 1; fi
cd "$REPO" || exit 1
docker compose up -d 2>&1 | tail -2
for _ in $(seq 1 90); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' coco-platform 2>/dev/null)" = healthy ] && break
  sleep 5
done
echo "[docker] health: $(docker inspect -f '{{.State.Health.Status}}' coco-platform)"
docker cp "$D/recorder.py" coco-platform:/tmp/recorder.py
docker exec coco-platform find /opt/coco_ws/install -name stop_latch.py | head -1
docker exec coco-platform grep -c _mission_running /opt/coco_ws/src/coco-labs/coco_mission/scripts/mission_executive.py
docker exec -d coco-platform bash -c \
  'source /opt/ros/jazzy/setup.bash; source /opt/coco_ws/install/setup.bash; exec python3 /tmp/recorder.py /tmp/ros.jsonl'
sleep 3
( cd "$RUN" && python3 "$D/probe.py" "$RUN/ws.jsonl" "$@" )
echo "probe exit $?"
docker exec coco-platform pkill -INT -f 'recorder.p[y]'
sleep 1
docker cp coco-platform:/tmp/ros.jsonl "$RUN/ros.jsonl"
docker logs coco-platform > "$RUN/container.log" 2>&1
docker compose down 2>&1 | tail -1
sleep 3
echo "containers: $(docker ps -q | wc -l)  gz: $(pgrep -f 'g[z] sim' | wc -l)"
