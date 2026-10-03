# The remote-session tunnel (Phase 2 Part C3)

**The owner chose Tailscale Funnel (2026-10-03).** No paid domain, VPS or
tunnel. Option A (Cloudflare) below is kept only as the record of what was
compared and verified offline. It is not used.

Either way the shape is the same:

```
phone ──https/wss──▶ vendor edge ──(connector dials OUT)──▶ tunnel sidecar
                                                            │ compose network only
                                                            ▼
                                             coco:8080  platform_server, remote:=true
                                             (/ws + /healthz; also 127.0.0.1:8080 on the host)
```

- The connector is a **sidecar container on the compose network**: no host
  network, no published ports, no Docker socket, read-only config.
- It routes **only `/ws` and `/healthz`**, and the platform (`remote:=true`)
  serves only those two as well. That's two independent layers.
- Origins are restricted by the platform (`docker-compose.remote.yml`:
  the Pages site, `http://localhost:*`, `http://127.0.0.1:*`). Since
  89e0239 `remote:=true` refuses to start without an allowlist.
- No SSH, no Docker API, no ROS/DDS (loopback-only inside the container),
  no Gazebo, and no other host port is involved. `external_check.sh`
  verifies all of this from outside after activation.

## Vendor facts (docs re-read 2026-10-03)

| | Cloudflare named tunnel | Tailscale Funnel |
|---|---|---|
| status | production | **beta**, all plans |
| needs | Cloudflare account **and a domain on Cloudflare DNS** | Tailscale account; MagicDNS + HTTPS certs on; `funnel` node attribute |
| URL | `https://<your hostname>` | `https://coco-live.<tailnet>.ts.net` (shows the tailnet name) |
| WebSocket | "full support", no extra configuration | not stated in the Funnel/Serve docs; open issue **#18651** strips the query string on the upgrade (we send the code inside a frame, so it doesn't matter) |
| path restriction | ingress `path` (Go regex) + mandatory catch-all, **verified offline** below | Serve handlers per path (Go ServeMux), **not verified** |
| ports | 443 (and Cloudflare's other proxied ports, same ingress) | 443 / 8443 / 10000 only |
| limits | none for this use | "non-configurable bandwidth limits" |
| config in repo | yes (locally managed `config.yml`) | yes (`serve.json`); the policy file lives in the admin console |

Sources: developers.cloudflare.com (Tunnel configuration file; Tunnels
FAQ), tailscale.com/kb/1223/funnel, /kb/1311/tailscale-funnel,
/kb/1242/tailscale-serve, docs/features/containers/docker/docker-params,
github.com/tailscale/tailscale/issues/18651.

## Option A: Cloudflare named tunnel (`cloudflare/`)

Verified **offline** (measured, cloudflared 2026.9.3, `--network none`):
`ingress validate` OK; `/ws` and `/healthz` match rules 0/1 →
`http://coco:8080`; `/`, `/index.html`, `/api/*`, `/video/camera`, `/ws/`,
`/wsx`, `/healthz/x`, `/.git/config`, traversal and any other hostname →
catch-all 404. Evidence:
`docs/data/live/part_c/c3_tunnel_prep/cloudflare_ingress_offline.txt`.

Owner, once (needs your browser; `C=$HOME/coco_cloudflared`, mode 0700):

```bash
IMG=cloudflare/cloudflared:2026.9.3
docker run --rm -it -v $C:/home/nonroot/.cloudflared $IMG tunnel login        # browser auth -> cert.pem
docker run --rm -v $C:/home/nonroot/.cloudflared $IMG tunnel create coco-live  # prints the UUID, writes <UUID>.json
docker run --rm -v $C:/home/nonroot/.cloudflared $IMG tunnel route dns coco-live HOSTNAME
```

Then (Claude can do this part):

```bash
UUID=...; HOST=...
mkdir -p $C/run && cp $C/$UUID.json $C/run/
sed -e "s/COCO_TUNNEL_UUID/$UUID/g" -e "s/COCO_TUNNEL_HOSTNAME/$HOST/g" \
  docs/live/tunnel/cloudflare/config.yml.template > $C/run/config.yml
bash docs/live/tunnel/cloudflare/ingress_check.sh $HOST
COCO_TUNNEL_DIR=$C/run docker compose -f docker-compose.yml -f docker-compose.remote.yml \
  -f docs/live/tunnel/cloudflare/docker-compose.tunnel-cloudflare.yml up -d
```

To check at activation (not yet verified): the image's `nonroot` user can
read the mounted credentials; the first `tunnel run` logs four connections.

## Option B: Tailscale Funnel (`tailscale/`) — CHOSEN

There's no Tailscale on the host and no sudo, so the node is the
`tailscale/tailscale:v1.102.5` container. It runs as the host uid with
every capability dropped (this works: measured, the node reached its login
step). It is userspace-only and tagged `tag:coco-live`. It is **not**
`--shields-up`: Funnel refuses to start with it (measured).

Owner, once (browser; **in this order**, because the login asks for the tag):
1. Admin console → **Access controls**: merge into the policy file
   ```json
   "tagOwners": { "tag:coco-live": ["autogroup:admin"] },
   "nodeAttrs": [ { "target": ["tag:coco-live"], "attr": ["funnel"] } ]
   ```
   and grant `tag:coco-live` nothing in `acls`/`grants`.
2. Admin console → **DNS**: MagicDNS on; HTTPS Certificates → Enable.
3. Open the login URL printed by `docs/live/tunnel/tailscale/ts.sh login`.

Then (Claude):

```bash
bash docs/live/tunnel/tailscale/ts.sh wait && bash docs/live/tunnel/tailscale/ts.sh caps   # funnel True, https True, tag
bash docs/live/tunnel/tailscale/ts.sh stop
COCO_TS_STATE=$HOME/coco_tailscale_state \
docker compose -f docker-compose.yml -f docker-compose.remote.yml \
  -f docs/live/tunnel/tailscale/docker-compose.tunnel-tailscale.yml up -d
docker exec coco-tunnel tailscale --socket=/tmp/tailscaled.sock funnel status
```

To check at activation (**not verified; none of this could be tested
without an account**):
1. The Serve docs say "only http://127.0.0.1 is supported for proxies"
   (for the CLI). If `serve.json`'s `http://coco:8080` is refused, the
   fallback is `network_mode: service:coco` with proxies to
   `http://127.0.0.1:8080/...`. Since that shares COCO's network
   namespace, `--shields-up` then becomes load-bearing.
2. That a handler at `/ws` proxies the upgrade to `/ws` (and doesn't strip
   the mount path), and that `/` and `/api/session` are 404 at the node.
3. ~~That `--shields-up` does not also block Funnel~~: it does (measured,
   2026-10-03); dropped. And that `cap_drop: ALL`
   is compatible with userspace networking.

## After either: the external check, and the site

```bash
# from a DIFFERENT network (phone on mobile data, cloud shell):
bash docs/live/tunnel/external_check.sh coco-live.<tailnet>.ts.net
# host side: no non-loopback listener at all, Docker publishes 127.0.0.1:8080 only
bash docs/data/live/part_c/scripts/exposure_local.sh
```

Scope: the check talks only to the owner's own Funnel hostname. It does
**not** port-scan the host's public address. That address is a shared NAT
(host 10.40.1.125/21) belonging to the network's operator, and scanning
it was refused (2026-10-03) for lack of authorization. "SSH / Docker API
/ ROS / Gazebo unreachable" therefore rests on the host-side fact that
none of them listens on any non-loopback address, and on Funnel being the
only ingress.

Then set `LIVE_REMOTE = { ws: 'wss://HOSTNAME/ws' }` in
`lab_web/site.config.ts`. `check_dist` verifies that the CSP gains exactly
that `wss:` and `https:` origin. The site shows "Live now" only when that
endpoint's `/healthz` reports an open code session.

Teardown: `docker compose ... stop tunnel` ends exposure at once (the
sidecar is the only way in); `scripts/live_session.sh kill` ends the
session and stops COCO.
