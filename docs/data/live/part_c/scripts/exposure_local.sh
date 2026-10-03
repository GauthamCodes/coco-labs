#!/usr/bin/env bash
# exposure_local.sh: what a REMOTE compose stack exposes, checked from THIS
# host (the tunnel-independent half of Part C4). Needs the remote stack up:
#   docker compose -f docker-compose.yml -f docker-compose.remote.yml up -d
PORT="${COCO_HTTP_PORT:-8080}"
PAGES='https://gauthamcodes.github.io'
echo "== listening sockets on this host (ss -ltn), and who holds :$PORT"
ss -ltn | sort -u
echo "-- :$PORT bound by:"; ss -ltnp 2>/dev/null | grep ":$PORT " || ss -ltn | grep ":$PORT "
echo "== docker port coco-platform"; docker port coco-platform
echo "== paths on 127.0.0.1:$PORT (remote:=true serves /ws and /healthz only)"
for p in /healthz / /index.html /app.js /frame.js /legacy.html /api/session /api/metrics \
         /video/camera /video/annotated /ws/../api/session /.git/config /etc/passwd; do
  printf '%-22s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' --path-as-is "http://127.0.0.1:$PORT$p")"
done
echo "== /ws handshake by Origin (101 = upgraded, 403 = refused)"
for o in "$PAGES" http://localhost:4173 http://127.0.0.1:5173 https://evil.example \
         https://gauthamcodes.github.io.evil.example null; do
  printf '%-45s %s\n' "$o" "$(curl -s -o /dev/null -w '%{http_code}' -m 3 \
    -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Version: 13' \
    -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' -H "Origin: $o" "http://127.0.0.1:$PORT/ws")"
done
echo "== /healthz CORS by Origin"
for o in "$PAGES" http://localhost:5173 https://evil.example; do
  printf '%-30s %s\n' "$o" "$(curl -s -D - -o /dev/null -H "Origin: $o" "http://127.0.0.1:$PORT/healthz" \
    | grep -i '^access-control-allow-origin' | tr -d '\r' || true)"
done
echo "== /healthz body"; curl -s "http://127.0.0.1:$PORT/healthz"; echo
echo "== the LAN cannot reach :$PORT (host port bound to 127.0.0.1)"
for ip in $(hostname -I); do
  printf '%-40s %s\n' "$ip:$PORT" "$(curl -s -o /dev/null -w '%{http_code}' -m 3 "http://$ip:$PORT/healthz" 2>&1 || true) (000 = no connection)"
done
echo "== ROS / DDS / Gazebo inside the container are not published"
docker inspect -f '{{json .NetworkSettings.Ports}}' coco-platform
