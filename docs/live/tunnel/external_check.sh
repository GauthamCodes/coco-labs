#!/usr/bin/env bash
# external_check.sh HOST [HOME_IP] -- what the public internet can reach.
#
# RUN IT FROM OUTSIDE: a machine on another network (a cloud shell, a
# phone hotspot on mobile data), never from the COCO host -- localhost
# reaching localhost proves nothing. Needs bash, curl, nc (OpenBSD or
# ncat); prints every command's result, and exits non-zero if anything
# expected closed is open or anything expected open is not.
#
#   HOST     the tunnel hostname (e.g. coco.example.org, or
#            coco-live.<tailnet>.ts.net)
#   HOME_IP  optional: the COCO host's own public egress address
#            (`curl -s https://ifconfig.me` ON the host). Scanned for SSH,
#            Docker, ROS/DDS, Gazebo and the platform ports, which must
#            all be closed: the tunnel dials out, nothing dials in.
#
# Expected: /healthz 200 or 503 with "protocol": "coco.v1"; /ws 101 for
# the Pages origin; 403 for a foreign or null origin; every other path
# 404; every non-443 TCP port closed or filtered.
set -u
HOST="${1:?usage: external_check.sh HOST [HOME_IP]}"
HOME_IP="${2:-}"
PAGES="https://gauthamcodes.github.io"
FAIL=0
bad() { echo "  !! $*"; FAIL=1; }

echo "== vantage (must NOT be the COCO host's network)"
echo "  egress ip: $(curl -s --max-time 10 https://ifconfig.me || echo unknown)"
echo "  resolve:   $(getent hosts "$HOST" | awk '{print $1}' | tr '\n' ' ')"
date -u +"  at:        %Y-%m-%dT%H:%M:%SZ"

echo "== /healthz"
code=$(curl -s -o /tmp/coco_hz.$$ -w '%{http_code}' --max-time 15 "https://$HOST/healthz")
echo "  GET /healthz -> $code; $(head -c 300 /tmp/coco_hz.$$ | tr '\n' ' ')"
grep '"coco.v1"' /tmp/coco_hz.$$ >/dev/null || bad "healthz is not coco.v1"
[ "$code" = 200 ] || [ "$code" = 503 ] || bad "healthz status $code"
for o in "$PAGES" "https://evil.example" "null"; do
  acao=$(curl -s -D - -o /dev/null --max-time 15 -H "Origin: $o" "https://$HOST/healthz" \
         | tr -d '\r' | grep -i '^access-control-allow-origin:' | cut -d' ' -f2-)
  echo "  Origin $o -> ACAO '${acao}'"
  if [ "$o" = "$PAGES" ]; then [ "$acao" = "$PAGES" ] || bad "Pages origin not allowed"
  else [ -z "$acao" ] || bad "origin $o allowed"; fi
done
srv=$(curl -s -D - -o /dev/null --max-time 15 "https://$HOST/healthz" | tr -d '\r' | grep -i '^server:')
echo "  Server header: '${srv}' (the edge's own, if any; never TornadoServer)"
echo "$srv" | grep -i tornado >/dev/null && bad "tornado banner visible"
rm -f /tmp/coco_hz.$$

echo "== /ws upgrade by Origin (101 admitted, 403 refused)"
ws() {
  curl -s -o /dev/null -w '%{http_code}' --http1.1 --max-time 10 \
    -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
    -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    "$@" "https://$HOST/ws"
}
for o in "$PAGES" "http://localhost:4173" "https://evil.example" \
         "https://gauthamcodes.github.io.evil.example" "null"; do
  c=$(ws -H "Origin: $o"); echo "  Origin $o -> $c"
  case "$o" in
    "$PAGES"|http://localhost:*) [ "$c" = 101 ] || bad "$o not admitted ($c)" ;;
    *) [ "$c" = 403 ] || bad "$o not refused ($c)" ;;
  esac
done
echo "  (no Origin header -> $(ws); a non-browser client: the control code, not the origin, is the credential)"

echo "== paths that must not exist (404)"
for p in / /index.html /app.js /frame.js /legacy.html /api/session /api/metrics \
         /video/camera /video/annotated /ws/ /wsx /healthz/x /.git/config \
         /etc/passwd /docker.sock /v1.43/containers/json /_ping /metrics; do
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOST$p")
  echo "  GET $p -> $c"; [ "$c" = 404 ] || bad "$p answered $c"
done
c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST "https://$HOST/healthz")
echo "  POST /healthz -> $c"
c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://$HOST/healthz")
echo "  plain http:// /healthz -> $c (a redirect or refusal; never COCO over cleartext)"

PORTS="22 80 2375 2376 7400 7401 7410 7411 7412 8080 8081 8443 9090 10000 11311 11345 11346 20241"
scan() {
  local target="$1" open=""
  for port in $PORTS; do
    if nc -z -w 4 "$target" "$port" 2>/dev/null; then open="$open $port"; fi
  done
  echo "  $target open TCP:${open:- none}" >&2
  echo "$open"
}
echo "== TCP ports on the tunnel hostname"
# These are the VENDOR's edge, not this machine: Cloudflare answers its
# proxied HTTP(S) ports (80, 8080, 8443, ...) for every proxied hostname
# and routes them through the same ingress rules. So an open edge port is
# not itself an exposure; what it SERVES is. Each open port must give
# nothing but the two intended paths: /api/session and / never 200.
o=$(scan "$HOST")
for port in $o; do
  for scheme in https http; do
    for p in /api/session / /video/camera; do
      c=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 "$scheme://$HOST:$port$p")
      echo "  $scheme://$HOST:$port$p -> $c"
      [ "$c" = 200 ] && bad "$scheme port $port serves $p"
    done
  done
done
if [ -n "$HOME_IP" ]; then
  echo "== TCP ports on the COCO host's own public address (all must be closed)"
  o=$(scan "$HOME_IP")
  for port in $o; do bad "port $port open on $HOME_IP"; done
  echo "  (UDP 7400+/DDS and gz-transport multicast cannot be proven closed with nc;"
  echo "   inside the container DDS is loopback-only and no UDP port is published)"
fi

echo "== verdict: $([ $FAIL = 0 ] && echo PASS || echo FAIL)"
exit $FAIL
