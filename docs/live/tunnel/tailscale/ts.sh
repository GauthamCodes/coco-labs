#!/usr/bin/env bash
# ts.sh login|wait|caps|stop -- log the coco-live Tailscale node in ONCE,
# without a tunnel and without COCO running, and inspect what the tailnet
# grants it. State persists in $COCO_TS_STATE (default
# ~/coco_tailscale_state), which the compose sidecar then reuses.
#
#   login  start a throwaway tailscaled (userspace, shields-up, no serve
#          config, so nothing is served) and print the login URL
#   wait   wait for the login to complete; print the node's DNS name
#   caps   the node's MagicDNS name, tags and capabilities (funnel, https)
#   stop   remove the throwaway container (state is kept)
set -o pipefail
IMG="tailscale/tailscale:${COCO_TAILSCALE_TAG:-v1.102.5}"
STATE="${COCO_TS_STATE:-$HOME/coco_tailscale_state}"
NAME=coco-ts-login
ts() { docker exec "$NAME" tailscale --socket=/tmp/tailscaled.sock "$@"; }
case "${1:-}" in
  login)
    # tailscaled directly, not the image's containerboot: containerboot
    # gives an interactive login 60 s and then exits (measured), which no
    # human clicking a link can rely on. `tailscale login` here waits.
    mkdir -p "$STATE" && chmod 0700 "$STATE"
    docker rm -f "$NAME" >/dev/null 2>&1
    docker run -d --name "$NAME" --user "$(id -u):$(id -g)" --cap-drop ALL \
      --security-opt no-new-privileges:true -v "$STATE:/var/lib/tailscale" \
      --entrypoint tailscaled "$IMG" --tun=userspace-networking \
      --statedir=/var/lib/tailscale --socket=/tmp/tailscaled.sock >/dev/null || exit 1
    sleep 3
    if ts status --json 2>/dev/null | grep '"BackendState": "Running"' >/dev/null; then
      echo "already logged in"; exit 0
    fi
    # The same settings the compose sidecar's containerboot will assert.
    docker exec -d "$NAME" sh -c 'tailscale --socket=/tmp/tailscaled.sock login \
      --hostname=coco-live --advertise-tags=tag:coco-live --shields-up \
      --accept-dns=false > /tmp/login.log 2>&1'
    for _ in $(seq 1 30); do
      url=$(docker exec "$NAME" cat /tmp/login.log 2>/dev/null | grep -o 'https://login.tailscale.com/[^ ]*' | tail -1)
      [ -n "$url" ] && { echo "LOGIN URL: $url"; exit 0; }
      sleep 1
    done
    docker exec "$NAME" cat /tmp/login.log; docker logs --tail 20 "$NAME"; exit 1 ;;
  wait)
    for _ in $(seq 1 "${2:-600}"); do
      ts status --json 2>/dev/null | grep '"BackendState": "Running"' >/dev/null && break
      sleep 1
    done
    ts status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["BackendState"], d["Self"].get("DNSName"))' ;;
  caps)
    ts status --json | python3 -c '
import json, sys
d = json.load(sys.stdin); s = d["Self"]
print("backend  ", d["BackendState"])
print("dns name ", s.get("DNSName"))
print("tailnet  ", (d.get("CurrentTailnet") or {}).get("Name"), "magicdns", (d.get("CurrentTailnet") or {}).get("MagicDNSEnabled"))
print("tags     ", s.get("Tags"))
print("cert dom ", d.get("CertDomains"))
caps = sorted((s.get("CapMap") or {}).keys())
print("funnel   ", any(c.endswith("/funnel") or c == "funnel" for c in caps))
print("https    ", any(c == "https" for c in caps))
print("caps     ", caps)' ;;
  stop) docker rm -f "$NAME" >/dev/null 2>&1; echo removed ;;
  *) sed -n '2,12p' "$0"; exit 2 ;;
esac
