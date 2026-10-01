#!/bin/bash
# COCO in Docker (coco-platform:jazzy, built from coco-labs main), browser teleop on :8080.
# Mirrors docker-compose.yml (port 8080, shm 2g, env), plus --ulimit core=0 (host apport trap).
D=/home/gautham/.claude/jobs/eb997671/tmp/dock
OUT=$D/out
NAME=coco-labs-teleop
rm -rf "$OUT"; mkdir -p "$OUT"; chmod 777 "$OUT"
log() { echo "[docker $(date +%H:%M:%S)] $*" | tee -a "$OUT/run.log"; }
dk() { sg docker -c "$*"; }

if pgrep -f 'g[z] sim' >/dev/null; then log "REFUSING: a Gazebo is running"; pgrep -af 'g[z] sim'; exit 3; fi
if ss -ltn '( sport = :8080 )' | tail -n +2 | grep . >/dev/null; then log "REFUSING: :8080 in use"; exit 3; fi

log "image: $(dk "docker image inspect coco-platform:jazzy --format '{{.Id}} {{.Created}}'")"
dk "docker run -d --name $NAME --ulimit core=0 --shm-size 2g -p 8080:8080 \
    -e COCO_TARGET_COLOUR=green -v $OUT:/out coco-platform:jazzy" >> "$OUT/run.log" 2>&1 || { log "docker run failed"; exit 1; }
start=$(date +%s)
code=000
for _ in $(seq 1 150); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/healthz)
  [ "$code" = 200 ] && break
  sleep 4
done
log "healthz $code after $(( $(date +%s) - start )) s"
curl -s http://127.0.0.1:8080/healthz > "$OUT/healthz_ready.json"
log "container health: $(dk "docker inspect $NAME --format '{{.State.Health.Status}}'")"
log "in-image tornado: $(dk "docker exec $NAME python3 -c 'import tornado; print(tornado.version)'")"

if [ "$code" = 200 ]; then
  dk "docker exec -d $NAME coco-entrypoint python3 /opt/coco_ws/src/coco-labs/scripts/browser_check/wheel_recorder.py /out/recorder.jsonl"
  sleep 5
  log "browser scenario"
  ( cd "$D" && python3 "$D/docker_teleop.py" http://127.0.0.1:8080/ "$OUT" > "$OUT/teleop.log" 2>&1 )
  log "browser scenario exit $?"
  dk "docker exec $NAME coco-entrypoint ros2 topic info /diff_drive_controller/cmd_vel -v" > "$OUT/wheel_topic.txt" 2>&1
fi

dk "docker logs $NAME" > "$OUT/container.log" 2>&1
log "stopping container"
dk "docker stop -t 30 $NAME" >/dev/null 2>&1
dk "docker rm $NAME" >/dev/null 2>&1
sleep 3
log "after teardown: gz processes on host = $(pgrep -f 'g[z] sim' | wc -l); containers named $NAME = $(dk "docker ps -a --filter name=$NAME -q" | wc -l)"
