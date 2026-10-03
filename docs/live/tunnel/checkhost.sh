#!/usr/bin/env bash
# checkhost.sh HOST [URL...] -- HTTP status of the owner's OWN Funnel URLs,
# as seen from check-host.net's probe nodes (other countries, other
# networks): a genuinely external vantage for reachability and routing.
# Requests go only to HOST; no port or address scanning.
#
# What it cannot do (external_check.sh does it, from the host, through
# Funnel): custom Origin headers and the WebSocket upgrade. Those verdicts
# are made by platform_server itself and do not depend on the client's
# network. Reachability and routing do, and they are what this measures.
#
# check-host.net rate-limits; a refused request prints "not checked".
set -u
HOST="${1:?usage: checkhost.sh HOST [URL...]}"; shift
NODES="${CHECKHOST_NODES:-4}"
if [ $# -eq 0 ]; then
  set -- "https://$HOST/healthz" "https://$HOST/" "https://$HOST/api/session" \
         "https://$HOST/video/camera" "https://$HOST/.git/config" \
         "https://$HOST:8443/healthz" "https://$HOST:10000/healthz"
fi
date -u +"at %Y-%m-%dT%H:%M:%SZ"
for url in "$@"; do
  id=$(curl -s --max-time 20 -H 'Accept: application/json' \
       "https://check-host.net/check-http?host=$url&max_nodes=$NODES" \
       | python3 -c 'import json,sys
try: print(json.load(sys.stdin)["request_id"])
except Exception: print("")')
  if [ -z "$id" ]; then echo "$url  not checked (check-host.net refused the request)"; sleep 20; continue; fi
  sleep 12
  curl -s --max-time 20 -H 'Accept: application/json' "https://check-host.net/check-result/$id" \
    | python3 -c '
import json, sys
url = sys.argv[1]
try:
    res = json.load(sys.stdin)
except Exception:
    print(f"{url}  no result"); sys.exit()
for node, r in sorted(res.items()):
    first = r[0] if isinstance(r, list) and r else None
    if not first:
        print(f"{url:52s} {node:28s} no result yet / node error: {r}"); continue
    ok, t, msg, code = (list(first) + [None] * 4)[:4]
    print(f"{url:52s} {node:28s} code={code} msg={msg} t={t}")' "$url"
  sleep 5
done
