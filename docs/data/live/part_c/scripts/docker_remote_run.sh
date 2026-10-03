#!/usr/bin/env bash
# docker_remote_run.sh RUNDIR  (PROBE=probe_expiry for the cap-while-driving case): the REMOTE compose stack (code access,
# remote, origins, loopback port), fresh container, with a short idle and
# cap so both happen in one run; exposure checks from the host; the session
# probe; the wheel topic recorded inside the container; compose down.
D="$(cd "$(dirname "$0")" && pwd)"
RUN="$(realpath -m "$1")"
mkdir -p "$RUN"
REPO="$HOME/coco_live_ws/src/coco-labs"
if pgrep -f 'g[z] sim' >/dev/null 2>&1; then echo "GAZEBO ALREADY RUNNING"; exit 1; fi
if [ -n "$(docker ps -aq --filter name=coco-platform)" ]; then echo "container exists"; exit 1; fi
cd "$REPO" || exit 1
export COCO_SESSION_IDLE_S="${COCO_SESSION_IDLE_S:-20}" COCO_SESSION_CAP_S="${COCO_SESSION_CAP_S:-150}"
docker image inspect coco-platform:jazzy --format 'image {{.Id}}' | tee "$RUN/image.txt"
echo "idle ${COCO_SESSION_IDLE_S} s, cap ${COCO_SESSION_CAP_S} s" | tee -a "$RUN/image.txt"
docker compose -f docker-compose.yml -f docker-compose.remote.yml config > "$RUN/compose_config.yml"
docker compose -f docker-compose.yml -f docker-compose.remote.yml up -d 2>&1 | tail -2
for _ in $(seq 1 90); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' coco-platform 2>/dev/null)" = healthy ] && break
  sleep 5
done
echo "[docker] health: $(docker inspect -f '{{.State.Health.Status}}' coco-platform)" | tee -a "$RUN/image.txt"
docker cp "$D/recorder.py" coco-platform:/tmp/recorder.py
docker exec -d coco-platform bash -c \
  'source /opt/ros/jazzy/setup.bash; source /opt/coco_ws/install/setup.bash; exec python3 /tmp/recorder.py /tmp/ros.jsonl'
bash "$D/exposure_local.sh" > "$RUN/exposure_local.txt" 2>&1
# Which process owns :8080 inside the container: the real platform_server.
docker exec coco-platform bash -c 'for p in /proc/[0-9]*; do
  for f in $p/fd/*; do l=$(readlink "$f" 2>/dev/null); case "$l" in socket:*) echo "${p#/proc/} ${l#socket:}";; esac; done
done > /tmp/socks; echo "listeners (local:port inode):"; awk "NR>1 && \$4==\"0A\" {print \$2, \$10}" /proc/net/tcp /proc/net/tcp6;
for ino in $(awk "NR>1 && \$4==\"0A\" && \$2 ~ /:1F90$/ {print \$10}" /proc/net/tcp /proc/net/tcp6); do
  pid=$(grep -w "\[$ino\]" /tmp/socks | head -1 | cut -d" " -f1); echo ":8080 pid $pid: $(tr "\0" " " < /proc/$pid/cmdline)"; done' \
  > "$RUN/listeners_in_container.txt" 2>&1
sleep 2
python3 "$D/${PROBE:-probe_session}.py" "$RUN/ws.jsonl" "${PROBE_URL:-ws://127.0.0.1:${COCO_HTTP_PORT:-8080}/ws}" \
  "${PROBE_ORIGIN:-http://localhost:4173}" "${PROBE_ARG:-$COCO_SESSION_IDLE_S}" | tee "$RUN/checks.txt"
echo "probe exit $?"
docker exec coco-platform pkill -INT -f 'recorder.p[y]'
sleep 1
docker cp coco-platform:/tmp/ros.jsonl "$RUN/ros.jsonl"
docker cp coco-platform:/tmp/coco_stack.log "$RUN/stack.log"
docker logs coco-platform > "$RUN/container.log" 2>&1
docker compose -f docker-compose.yml -f docker-compose.remote.yml down 2>&1 | tail -1
sleep 3
echo "containers: $(docker ps -q | wc -l)  gz: $(pgrep -f 'g[z] sim' | wc -l)"
