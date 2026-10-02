#!/usr/bin/env bash
# docker_run.sh RUNDIR SCENARIO ARGS...: `docker compose up` the image from a
# FRESH container, record inside the container, drive it from the host over
# :8080 with probe.py (coco.v1 only), copy the evidence out, compose down.
#
#   docker_run.sh docs/data/live/part_c/c1_fetch_red fetch red
#
# Refuses if any Gazebo or any coco-platform container is already running.
D="$(cd "$(dirname "$0")" && pwd)"
RUN="$(realpath -m "$1")"; shift
mkdir -p "$RUN"
REPO="$HOME/coco_live_ws/src/coco-labs"
if pgrep -f 'g[z] sim' >/dev/null 2>&1; then echo "GAZEBO ALREADY RUNNING"; exit 1; fi
if [ -n "$(docker ps -aq --filter name=coco-platform)" ]; then
  echo "a coco-platform container already exists; not starting another"; exit 1
fi
cd "$REPO" || exit 1
docker image inspect coco-platform:jazzy --format 'image {{.Id}}' | tee "$RUN/image.txt"
t_up=$(date +%s.%N)
docker compose up -d 2>&1 | tail -2
for _ in $(seq 1 90); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' coco-platform 2>/dev/null)" = healthy ] && break
  sleep 5
done
t_ok=$(date +%s.%N)
echo "[docker] health: $(docker inspect -f '{{.State.Health.Status}}' coco-platform)" \
     "after $(python3 -c "print(round($t_ok-$t_up,1))") s (wall, 5 s poll)" | tee -a "$RUN/image.txt"
docker cp "$D/recorder.py" coco-platform:/tmp/recorder.py
docker exec -d coco-platform bash -c \
  'source /opt/ros/jazzy/setup.bash; source /opt/coco_ws/install/setup.bash; exec python3 /tmp/recorder.py /tmp/ros.jsonl'
sleep 3
( cd "$RUN" && python3 "$D/probe.py" "$RUN/ws.jsonl" "$@" )
echo "probe exit $?"
docker exec coco-platform pkill -INT -f 'recorder.p[y]'
sleep 1
docker cp coco-platform:/tmp/ros.jsonl "$RUN/ros.jsonl"
docker cp coco-platform:/tmp/coco_stack.log "$RUN/stack.log"
docker cp coco-platform:/tmp/coco_sim.log "$RUN/sim.log"
docker logs coco-platform > "$RUN/container.log" 2>&1
docker compose down 2>&1 | tail -1
sleep 3
echo "containers: $(docker ps -q | wc -l)  gz: $(pgrep -f 'g[z] sim' | wc -l)"
