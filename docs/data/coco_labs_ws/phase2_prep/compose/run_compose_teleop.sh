#!/bin/bash
# COCO via `docker compose up` (coco-labs lab1), browser teleop on :8080: one W/S drive, one STOP.
D=/home/gautham/.claude/jobs/eb997671/tmp/dock
OUT=$D/out_compose
REPO=/home/gautham/coco_labs_ws/src/coco-labs
rm -rf "$OUT"; mkdir -p "$OUT"
log() { echo "[compose $(date +%H:%M:%S)] $*" | tee -a "$OUT/run.log"; }
dc() { sg docker -c "cd $REPO && docker compose $*"; }

if pgrep -f 'g[z] sim' >/dev/null; then log "REFUSING: a Gazebo is running"; exit 3; fi
if ss -ltn '( sport = :8080 )' | tail -n +2 | grep . >/dev/null; then log "REFUSING: :8080 in use"; exit 3; fi

log "repo $(git -C "$REPO" rev-parse --short HEAD); image $(sg docker -c "docker image inspect coco-platform:jazzy --format '{{.Id}}'")"
dc "up -d" >> "$OUT/run.log" 2>&1 || { log "compose up failed"; exit 1; }
start=$(date +%s)
code=000
for _ in $(seq 1 150); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/healthz)
  [ "$code" = 200 ] && break
  sleep 4
done
log "healthz $code after $(( $(date +%s) - start )) s"
curl -s http://127.0.0.1:8080/healthz > "$OUT/healthz_ready.json"
log "in-container: ulimit -c = $(dc "exec -T coco sh -c 'ulimit -c'"), hard = $(dc "exec -T coco sh -c 'ulimit -H -c'")"
log "in-container: tornado $(dc "exec -T coco python3 -c 'import tornado; print(tornado.version, tornado.__file__)'")"

if [ "$code" = 200 ]; then
  dc "exec -d coco coco-entrypoint python3 /opt/coco_ws/src/coco-labs/scripts/browser_check/wheel_recorder.py /tmp/recorder.jsonl"
  sleep 5
  log "browser scenario"
  ( cd "$D" && python3 "$D/docker_teleop.py" http://127.0.0.1:8080/ "$OUT" > "$OUT/teleop.log" 2>&1 )
  log "browser scenario exit $?"
  dc "exec -T coco coco-entrypoint ros2 topic info /diff_drive_controller/cmd_vel -v" > "$OUT/wheel_topic.txt" 2>&1
  sg docker -c "docker cp coco-platform:/tmp/recorder.jsonl $OUT/recorder.jsonl" >> "$OUT/run.log" 2>&1
fi
dc "logs --no-color" > "$OUT/container.log" 2>&1
log "compose down"
dc "down" >> "$OUT/run.log" 2>&1
sleep 3
log "after teardown: gz processes on host = $(pgrep -f 'g[z] sim' | wc -l); containers = $(sg docker -c "docker ps -a --filter name=coco-platform -q" | wc -l)"
