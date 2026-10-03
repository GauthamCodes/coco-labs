#!/usr/bin/env bash
# external_check.sh HOST -- what the public internet gets from the tunnel.
#
# RUN IT FROM OUTSIDE: a machine on another network (a phone on mobile
# data, a cloud shell). From the COCO host itself it still crosses the
# internet to Tailscale's Funnel ingress and back, but that is the same
# network, so it does not count as the external check.
#
# It talks ONLY to HOST, the owner's own Funnel hostname, and only on the
# three ports Funnel can ever listen on (443, 8443, 10000). It does not
# scan anyone's IP address: the COCO host sits behind a shared NAT whose
# public address belongs to the network's operator, and Funnel's ingress
# servers belong to Tailscale. That nothing ELSE on the host is reachable is
# shown host-side instead: it has no non-loopback listener at all
# (docs/data/live/part_c/scripts/host_listeners.sh, exposure_local.sh).
#
# Expected: /healthz 200 or 503 with "protocol": "coco.v1"; /ws 101 for
# the Pages origin and localhost; 403 for foreign or null origins; every
# other path 404; 8443 and 10000 not served; no tornado banner.
set -u
HOST="${1:?usage: external_check.sh HOST}"
# COCO_CHECK_IP=-4 (or -6) pins the IP family, for a vantage where one is
# broken (the COCO host has no working IPv6: measured).
curl() { command curl ${COCO_CHECK_IP:-} "$@"; }
PAGES="https://gauthamcodes.github.io"
FAIL=0
bad() { echo "  !! $*"; FAIL=1; }
TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT

echo "== vantage"
echo "  egress ip: $(curl -s --max-time 10 https://ifconfig.me || echo unknown)"
echo "  resolve:   $(getent hosts "$HOST" | awk '{print $1}' | tr '\n' ' ')"
date -u +"  at:        %Y-%m-%dT%H:%M:%SZ"

echo "== /healthz"
code=$(curl -s -o "$TMP" -w '%{http_code}' --max-time 15 "https://$HOST/healthz")
echo "  GET /healthz -> $code; $(head -c 300 "$TMP" | tr '\n' ' ')"
grep '"coco.v1"' "$TMP" >/dev/null || bad "healthz is not coco.v1"
[ "$code" = 200 ] || [ "$code" = 503 ] || bad "healthz status $code"
for o in "$PAGES" "https://evil.example" "null"; do
  acao=$(curl -s -D - -o /dev/null --max-time 15 -H "Origin: $o" "https://$HOST/healthz" \
         | tr -d '\r' | grep -i '^access-control-allow-origin:' | cut -d' ' -f2-)
  echo "  Origin $o -> ACAO '${acao}'"
  if [ "$o" = "$PAGES" ]; then [ "$acao" = "$PAGES" ] || bad "Pages origin not allowed"
  else [ -z "$acao" ] || bad "origin $o allowed"; fi
done
hdrs=$(curl -s -D - -o /dev/null --max-time 15 "https://$HOST/healthz" | tr -d '\r')
echo "  Server header: '$(echo "$hdrs" | grep -i '^server:')'"
echo "$hdrs" | grep -i '^server:.*tornado' >/dev/null && bad "tornado banner visible"

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
[ "$c" = 200 ] && bad "POST /healthz answered 200"

echo "== Funnel's other ports on this hostname (only 443 is configured)"
for port in 8443 10000; do
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOST:$port/healthz")
  echo "  https://$HOST:$port/healthz -> $c"
  [ "$c" = 200 ] || [ "$c" = 503 ] && bad "port $port serves COCO"
done
c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://$HOST/healthz")
echo "  http://$HOST/healthz (cleartext) -> $c"
[ "$c" = 200 ] || [ "$c" = 503 ] && bad "COCO served over cleartext"

echo "== verdict: $([ $FAIL = 0 ] && echo PASS || echo FAIL)"
exit $FAIL
