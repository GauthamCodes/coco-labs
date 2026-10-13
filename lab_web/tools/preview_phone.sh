#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# M4.1: a TEMPORARY phone preview of this branch's build over Tailscale Funnel, so Gautham can
# open the 3D Arena on mobile data (owner's permission 4, 2026-10-11; docs/v2/PHONE_GATE_M4.md).
#
#   lab_web/tools/preview_phone.sh start [HOURS=2] [--no-build]   build, serve, funnel; prints the URL
#                                   (--no-build: serve lab_web/dist as it is)
#   lab_web/tools/preview_phone.sh status
#   lab_web/tools/preview_phone.sh stop
#
# - STATIC FILES ONLY: the production build (npm run build), served by tools/perf/serve_dist.mjs
#   on 127.0.0.1:4260 with gzip, the way GitHub Pages serves it; nothing else is reachable.
# - ONE PATH: the Funnel serves /coco-labs/ and nothing else. Live's /ws and /healthz are not
#   handled, so the preview cannot collide with them; and it refuses to start while Live's own
#   tunnel (container coco-tunnel) or its login helper is running, because both use the one
#   Tailscale node the tailnet grants Funnel (coco-live, ~/coco_tailscale_state).
# - IT TURNS ITSELF OFF after HOURS (default 2): a detached timer removes the Tailscale
#   container and stops the server. `stop` does it now.
# - The tailscale container runs as this user, every capability dropped, userspace networking,
#   on the host network only so it can reach 127.0.0.1:4260; no Docker socket, no published port.
set -o pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WEB="$(cd "$HERE/.." && pwd)"
STATE="${COCO_TS_STATE:-$HOME/coco_tailscale_state}"
IMG="tailscale/tailscale:${COCO_TAILSCALE_TAG:-v1.102.5}"
NAME=coco-preview-ts
PORT=4260
RUN="${XDG_RUNTIME_DIR:-/tmp}/coco_preview_phone"
NODE="${COCO_NODE:-node}"

stop() {
  docker rm -f "$NAME" >/dev/null 2>&1
  [ -f "$RUN/server.pid" ] && kill "$(cat "$RUN/server.pid")" 2>/dev/null
  [ -f "$RUN/timer.pid" ] && kill "$(cat "$RUN/timer.pid")" 2>/dev/null
  rm -f "$RUN/server.pid" "$RUN/timer.pid"
  echo "preview stopped $(date -Is)"
}

case "${1:-}" in
  start)
    HOURS="${2:-2}"
    for c in coco-tunnel coco-ts-login; do
      if docker ps --format '{{.Names}}' | grep -x "$c" >/dev/null; then
        echo "refusing: $c is running (Live uses the same Tailscale node)"; exit 2
      fi
    done
    [ -d "$STATE" ] || { echo "no Tailscale state at $STATE (docs/live/tunnel/tailscale/ts.sh login)"; exit 2; }
    mkdir -p "$RUN"
    stop >/dev/null
    if [ "${3:-}" != "--no-build" ]; then
      (cd "$WEB" && npm run build >"$RUN/build.log" 2>&1) || { echo "build failed: $RUN/build.log"; exit 1; }
    fi
    [ -f "$WEB/dist/index.html" ] || { echo "no build in $WEB/dist"; exit 1; }
    # setsid -f: the server in its own session, the script never waits on it (a backgrounded
    # subshell here became the server itself and the script waited for it: measured, M4.1)
    (cd "$WEB" && setsid -f "$NODE" tools/perf/serve_dist.mjs --port "$PORT" --host 127.0.0.1 \
      >"$RUN/server.log" 2>&1 </dev/null)
    sleep 1
    pgrep -f "serve_dist[.]mjs --port $PORT" | head -1 >"$RUN/server.pid"
    sleep 1
    curl -sf "http://127.0.0.1:$PORT/coco-labs/" >/dev/null || { echo "static server did not start: $RUN/server.log"; stop; exit 1; }
    cat >"$RUN/serve.json" <<EOF
{
  "TCP": { "443": { "HTTPS": true } },
  "Web": { "\${TS_CERT_DOMAIN}:443": { "Handlers": {
    "/coco-labs/": { "Proxy": "http://127.0.0.1:$PORT/coco-labs/" }
  } } },
  "AllowFunnel": { "\${TS_CERT_DOMAIN}:443": true }
}
EOF
    docker run -d --name "$NAME" --network host --user "$(id -u):$(id -g)" --cap-drop ALL \
      --security-opt no-new-privileges:true -v "$STATE:/var/lib/tailscale" -v "$RUN/serve.json:/config/serve.json:ro" \
      -e TS_STATE_DIR=/var/lib/tailscale -e TS_SOCKET=/tmp/tailscaled.sock -e TS_USERSPACE=true \
      -e TS_SERVE_CONFIG=/config/serve.json -e TS_HOSTNAME=coco-live \
      -e TS_EXTRA_ARGS="--reset --advertise-tags=tag:coco-live" "$IMG" >/dev/null || { stop; exit 1; }
    dns=""
    for _ in $(seq 1 60); do
      dns=$(docker exec "$NAME" tailscale --socket=/tmp/tailscaled.sock status --json 2>/dev/null \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["Self"]["DNSName"].rstrip(".") if d.get("BackendState")=="Running" else "")' 2>/dev/null)
      [ -n "$dns" ] && break
      sleep 2
    done
    [ -n "$dns" ] || { echo "Tailscale did not come up"; docker logs --tail 20 "$NAME"; stop; exit 1; }
    setsid -f bash -c "sleep $((HOURS * 3600)); '$HERE/preview_phone.sh' stop >>'$RUN/timer.log' 2>&1" >/dev/null 2>&1 </dev/null
    pgrep -f "preview_phone[.]sh. stop" | head -1 >"$RUN/timer.pid"
    echo "preview on until $(date -d "+$HOURS hours" -Is)"
    echo "URL: https://$dns/coco-labs/?view=arena&camera=follow&perf"
    ;;
  status)
    docker ps --filter "name=^$NAME\$" --format '{{.Names}} {{.Status}}'
    [ -f "$RUN/server.pid" ] && echo "server pid $(cat "$RUN/server.pid")"
    docker exec "$NAME" tailscale --socket=/tmp/tailscaled.sock funnel status 2>/dev/null ;;
  stop) stop ;;
  *) sed -n '6,21p' "$0"; exit 2 ;;
esac
