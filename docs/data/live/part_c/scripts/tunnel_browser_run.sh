#!/usr/bin/env bash
# tunnel_browser_run.sh OUT [SCENARIO ARGS...]  (default teleop_nav)
#
# The SHIPPED Live tab, in headless Firefox, driving COCO through the
# PUBLIC Funnel URL: page (served on localhost:4173, an allowed origin) ->
# internet -> Tailscale Funnel -> sidecar -> platform_server in Docker.
# Needs the remote stack + tunnel already up (docs/live/tunnel/README.md).
# A new host session (new code) first; the page claims it like a remote
# driver. The wheel recorder runs inside the container; the page and the
# container share this machine's clock, so latencies are one clock.
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
OUT="$(realpath -m "$1")"; shift
[ $# -eq 0 ] && set -- teleop_nav
WSURL="${COCO_PUBLIC_WS:-wss://coco-live.taile7cb60.ts.net/ws}"
mkdir -p "$OUT"
[ "$(docker inspect -f '{{.State.Health.Status}}' coco-platform 2>/dev/null)" = healthy ] \
  || { echo "coco-platform not healthy"; exit 1; }
[ "$(docker inspect -f '{{.State.Running}}' coco-tunnel 2>/dev/null)" = true ] \
  || { echo "coco-tunnel not running"; exit 1; }
docker image inspect coco-platform:jazzy --format 'image {{.Id}}' > "$OUT/image.txt"
docker exec coco-tunnel tailscale --socket=/tmp/tailscaled.sock funnel status > "$OUT/funnel_status.txt" 2>&1
bash "$REPO/scripts/live_session.sh" new | tee "$OUT/session_new.txt"
CODE=$(bash "$REPO/scripts/live_session.sh" code | grep -o 'control code [A-Z0-9]\{8\}' | awk '{print $3}')
[ -n "$CODE" ] || { echo "no code"; exit 1; }
docker cp "$HERE/recorder.py" coco-platform:/tmp/recorder.py
docker exec coco-platform rm -f /tmp/ros.jsonl
docker exec -d coco-platform bash -c \
  'source /opt/ros/jazzy/setup.bash; source /opt/coco_ws/install/setup.bash; exec python3 /tmp/recorder.py /tmp/ros.jsonl'
( cd "$REPO/lab_web" && exec setsid npx vite preview --port 4173 --strictPort ) > "$OUT/preview.log" 2>&1 &
PREVIEW=$!
for _ in $(seq 1 30); do curl -fsS http://localhost:4173/coco-labs/ >/dev/null 2>&1 && break; sleep 1; done
COCO_CODE="$CODE" COCO_BIDI_PORT=9227 python3 "$REPO/scripts/live_check/live_b.py" "$OUT" \
  "http://localhost:4173/coco-labs/?view=live&live=$WSURL" "$@"
echo "live_b exit $?"
docker exec coco-platform pkill -INT -f 'recorder.p[y]'
sleep 1
docker cp coco-platform:/tmp/ros.jsonl "$OUT/ros.jsonl"
kill -TERM -- "-$PREVIEW" 2>/dev/null
sleep 1
echo "preview left: $(pgrep -f 'vite previe[w]' | wc -l)"
