# Phase 2 · Part C — driver, spectators, remote sessions (2026-10-04: deployed; at the phone-test gate)

Branch `live`. Evidence: `docs/data/live/part_c/` (gunzip `*.gz` first).
Harness: `docs/data/live/part_c/scripts/`. Every number is **(measured)**
unless marked; n = 1 per row. One run is not a rate.

## Status

| part | status |
|---|---|
| precondition | holds: Part A; safety fixes on main (`labs/main` = 54133fe); Part B and its invariants; CI **and** Lab green on 74ab139 (GitHub pull_request runs; the Part B log entry had not recorded this) |
| C1 Docker fetch | **done: 1/1 COMPLETE** (open access); **C1b: 1/1 COMPLETE in the remote session configuration** |
| C2 session model | **done**: pure module + server wiring + live in Docker |
| C3 tunnel | **done: Tailscale Funnel** (owner's choice) at `https://coco-live.taile7cb60.ts.net`, `/ws` + `/healthz` only, sidecar container. Down between sessions |
| C4 exposure | **done**: host side (no non-loopback TCP listener at all) + external (check-host.net nodes, WebFetch) + through Funnel (origins, paths) |
| C5 public status | **done**; `LIVE_REMOTE` = the Funnel endpoint; "Live now" seen on the real page through the real endpoint |
| C6 remote session | tunnel measured with the shipped page (this host as the client); **the phone session has not happened**. Gate: the Pages deploy (needs a push: owner) |
| C7 / C8 | full local suite 2691/0; **CI and Lab green on a61150c** (PR #8 and `main`); `main` fast-forwarded 54133fe..a61150c (owner-approved); **Pages deployed** with the Live tab |

## Implementation

| commit | what |
|---|---|
| 213f9bd | C1 evidence and harness |
| e1fbe4e | `coco_web/control.py`: the policy, pure, injected clock; `protocol.py` +`claim`/`release`, +7 refusal codes (additive only: 38 insertions, 0 deletions) |
| cf39de0 | server wiring: gate before dispatch (and charge on undecodable frames), every ending → latched STOP, cap/kill close sockets; host Trigger services `session_kill/new/code`; `remote:=true` = `/ws` + `/healthz` only; `origins` allowlist; `/healthz` gains `live` + CORS for allowlisted origins only |
| c921ec4 | launch args through `mission.launch.py` → `platform.launch.py`; entrypoint env; `docker-compose.remote.yml` (code, remote, origins, **127.0.0.1:8080** via `!override`); `scripts/live_session.sh code\|new\|kill\|status` |
| c942310 | lab_web: claim box / release / countdowns / spectator STOP shown "driver only"; `status.ts` probe + `schedule.json` + Replay / Docker fallback; `LIVE_REMOTE` in `site.config.ts` (adds exactly its `wss:`+`https:` to the CSP; `check_dist` verifies, exercised with a throwaway value and reverted) |
| 5494bf9 | C2 live evidence, `docs/WEB_API.md` |
| 89e0239 | the idle exemption made explicit as an **autonomy-held lease** (below); `remote:=true` refuses an empty/`*` origins list; no `Server: TornadoServer` banner and a bare JSON 404 on the remote surface; status wording |
| fbc0f77 | C3 prepared: `docs/live/tunnel/` (both options, offline ingress check) |
| 40b5b5d | C1b (remote-config fetch); flood close-code fix; Tailscale sidecar non-root, caps dropped |
| 6a30783 | `ts.sh` login that waits; `external_check.sh` scoped to our own hostname; `test_tunnel_config.py` |
| 5b58960 | Funnel live; no `--shields-up` (incompatible), `--reset`; `LIVE_REMOTE`; **remote stream budget**; harness claim step |

Defaults (proposals from Part A §5.3, **not measured**): idle 60 s, cap
20 min, 25 clients, 60 frames/s, `drive` 20/s, other commands 2/s burst 6,
5 bad codes or 100 refusals in a row close the socket. The driver's STOP
is never rate-limited. `access:=open` (the default) is P0.1's behaviour:
the whole pre-existing suite passes unchanged.

**The inactivity lease (owner decision, confirmed in the 2026-10-03
brief).** While the executive reports a mission running, or the browser's
Nav2 goal is `accepted`/`executing`, **autonomy holds the lease** and the
idle clock is suspended. This is not counted as driver activity: until
89e0239 the code wrote the driver's last-activity time, and now it doesn't.
Telemetry says `lease: autonomy`, `idle_left_s: null`, and `last_input_s`
keeps growing; the driver's banner says "Idle release paused: autonomy is
running (the session cap still applies)". When autonomy ends, the lease
returns to the driver with a full `idle_s` window from that moment. An
unknown mission state is not autonomy (fail closed). The cap is never
suspended. Without the lease a 60 s idle would abort every remote fetch
(≈ 260 s, C1).

## Tests

`run_all_package_tests.sh`, all 11 packages, domain 74, on 5b58960
(2026-10-03): **2691 passed, 0 failed** (2665 on cbc1e26; Part B 2512).
lab_web: vitest **238** passed, typecheck, build and `check_dist` clean.
CI: **not run** (it needs a push; owner).

| package | Part B | now | what |
|---|---|---|---|
| coco_web | 688 | 857 | `test_control.py` (pure, fake clock; lease), `test_live_session.py` (real sockets: origins refusals, no banner, flood close code, remote telemetry rate and camera budget), `test_streams.py` (remote budget) |
| coco_rl | 231 | 241 | remote compose; `test_tunnel_config.py` (Funnel serves exactly /ws + /healthz to coco:8080; sidecar publishes nothing, non-root, caps dropped, no SSH, pinned) |
| others | | unchanged | coco_config 93, coco_sim 280, coco_mission 344, gazebo_models 229, coco_perception 139, coco_moveit_config 12, custom_teleop 75, coco_lab 352, coco_lab_ros 69 |

Covered: driver acquire, spectator refusal (every command, STOP
included), duplicate driver, idle timeout, session cap, rate limit, host
kill, invalid/expired/killed code, stop on every ending, no implicit
transfer, ownership loss fails closed, origins, remote routes, unsafe
configuration refused (`remote` without `code`, a typo in `access`).

## C1 — Docker autonomous fetch

| item | value |
|---|---|
| image | `coco-platform:jazzy` 48544a3ddbf3, from 74ab139; tornado 6.5.7; navigation2 1.3.13-1noble.20260905 |
| base | `osrf/ros:jazzy-desktop` **by tag, not digest** |
| run | fresh `docker compose up -d`; healthy after 15.6 s (5 s poll) |
| colour / outcome | **red: COMPLETE, `result=fetch`**, all 16 states |
| Start → terminal | 259.5 s wall (no total sim-time duration is instrumented) |
| recoveries / relocalisations | 0 / 0; 0 PolygonStop actions |
| wheel publishers | 1 (`cmd_vel_arbiter`) every 5 s |

## C2 — the session policy, live (Docker, remote compose)

Image 90385a150777 (c942310), `docker-compose.yml` + `docker-compose.remote.yml`,
idle 20 s, cap 150 s for the run. Driven over coco.v1 from the host with
`Origin: http://localhost:4173`; codes from `live_session.sh` (the host's
path); wheels recorded inside the container.

**20/20 checks pass** (`c2_session_docker/checks.txt`). Wheels:

| event | robot at the time | first wheel zero | moving cmds after |
|---|---|---|---|
| spectator drive / stop / set_mode stop / nav_goal / mission start | at rest | — | **0** during the whole spectator phase |
| idle release | at rest (driver had stopped) | +199.5 ms from the telemetry that reported it; STOP latched | 0 (0.08 s until the scripted reclaim) |
| driver disconnect | driving, 0.188 m/s | **+16.8 ms** | 0 in 4.98 s |
| session cap | at rest | latched, socket 4403 `session_over` | 0 in 3.48 s |
| host kill (`live_session.sh kill`, incl. `docker exec` + `ros2 service call` start-up) | driving | **+318.4 ms** | 0 |
| **cap while driving** (`c2_expiry_driving`, cap 90 s) | driving 10 Hz, −0.200 m/s | at the close (last moving 51.0 ms before it) | **0 to +10 s**; truth 0.000 m/s by +0.31 s |

After the cap and after the kill: a new connection got `error session_over`
then close 4403; `session_code` said `session over (expired|killed); call
session_new`; `session_new` issued a new code; the old code was `bad_code`
in the new session. Wheel publishers 1 throughout both runs.

## C1b — autonomous fetch in the REMOTE session configuration (2026-10-03)

Image `coco-platform:jazzy` 0a325ed08650 (fbc0f77). `docker-compose.yml`
plus `docker-compose.remote.yml`, the real defaults (idle 60 s, cap
1200 s), fresh container, driven over coco.v1 from the host by
`probe_remote_fetch.py` (driver A, spectator B, flooder R). n = 1.
Evidence: `c7_remote_fetch_red/` (`analysis.txt`; gunzip `*.gz`).

| item | value (measured) |
|---|---|
| outcome | **red COMPLETE, `result=fetch`**, all 16 states in nominal order |
| `mission start` → COMPLETE | 468.3 s wall (C1, open access: 259.5 s; one run each, not a comparison) |
| RECOVERY / RELOCALIZE | 0 / 0 |
| wheel publishers | 1 (`cmd_vel_arbiter`) in 111/111 samples (5 s) |
| who serves :8080 in the container | `/opt/coco_ws/install/coco_web/lib/coco_web/platform_server` (0.0.0.0:8080); every other listener 127.0.0.1 |
| lease during the fetch | `autonomy` in 4756 telemetry rows; driver held control, **`last_input_s` peaked at 528.1 s** (idle 60 s): no faked activity |
| mission end → lease back to driver | 0.05 s; then a fresh window of 59.999 s |
| lease back → idle release | **59.91 s** (10 Hz telemetry); STOP latched; 0 moving wheel commands |
| Nav2 goal | lease `autonomy` while executing, `idle_left_s` null; back to `driver` after; `nav_goal` → first `/plan` 5.2 ms |
| spectator STOP / abort mid-mission (CLIMB) | `spectator`, both; mission unaffected (CLIMB → CLIMB) |
| driver burst of 40 `drive` | 20 ack, 20 `rate_limited`; the driver's STOP right after: ack |
| spectator flood, 300 `drive` | 0 admitted (21 `spectator`, 75 `rate_limited`), socket closed, **but with no close code**: a defect, below |
| reclaim, then host kill | 4403 close; 0 moving wheel commands after |

**28/30 checks.** The two failures:
- `invalid code` got `driver_present`. That was the probe's ordering: a
  claim while a driver holds control is `driver_present` whatever its
  code (by design; C2 measured `bad_code` with no driver). The probe now
  checks the code with no driver present.
- **Defect, fixed:** once the abuse limit closed the flooder's socket,
  frames already buffered still reached `on_message`. `refuse()` wrote
  to the closing socket and raised `WebSocketClosedError`. Tornado then
  aborted the stream with unread data, the kernel sent RST, and the client
  lost the 4403/4429 close code and its last 4 refusals. Robot safety was
  not affected (0 of 300 admitted). Fix: `on_message` ignores frames once
  the connection is closing. Regression test
  `test_a_flooding_spectator_is_closed_with_a_code_and_moves_nothing`
  failed first (uncaught exception logged), then passed.

## C4 — exposure, host half (`c2_session_docker/exposure_local.txt`)

| check | result |
|---|---|
| host listeners on the platform port | only `127.0.0.1:8080` (`docker port`: `8080/tcp -> 127.0.0.1:8080`) |
| this host's LAN addresses `:8080` | no connection |
| paths | `/healthz` 200; `/`, `/index.html`, `/app.js`, `/frame.js`, `/legacy.html`, `/api/session`, `/api/metrics`, `/video/camera`, `/video/annotated`, `/ws/../api/session`, `/.git/config`, `/etc/passwd`: **404** |
| `/ws` Origin | Pages site, `http://localhost:4173`, `http://127.0.0.1:5173`: 101; `https://evil.example`, `https://gauthamcodes.github.io.evil.example`, `null`: **403** |
| `/healthz` CORS | header only for the Pages site and localhost |
| container ports published | 8080 only; ROS/DDS (loopback-only CycloneDDS), gz-transport, web_video_server 8081 are not published |

Other listeners on this host (all 127.0.0.1/::1: 631 CUPS, 53 resolver,
and several ephemeral ports) are outside Docker and are not what any
tunnel would point at. **"Nothing else is exposed" is not claimed until
the external check (C4, after C3).**

## C3 — the tunnel: Tailscale Funnel

`docs/live/tunnel/README.md` is the runbook. The node is the
`tailscale/tailscale:v1.102.5` container (no Tailscale on the host, no
sudo), on the compose network, as uid 1000 with every capability dropped,
userspace networking, no Tailscale SSH, tagged `tag:coco-live`. It
publishes no port, has no host network and no Docker socket.

| check (measured) | result |
|---|---|
| node, read from the machine | `coco-live.taile7cb60.ts.net`, tag `tag:coco-live`, MagicDNS on; caps include `funnel` and `https` (ports 443/8443/10000) **before** Funnel was turned on |
| `tailscale funnel status` | `https://coco-live.taile7cb60.ts.net (Funnel on)`; `/ws` → `http://coco:8080/ws`; `/healthz` → `http://coco:8080/healthz`; nothing else |
| prefs | ShieldsUp false, RunSSH false, RunWebClient false, no routes, no exit node |
| sidecar's own listeners | Docker's DNS 127.0.0.11, and tailscaled's peer API on 0.0.0.0:49091 inside the sidecar's namespace (not published: compose network and the owner's own tailnet only) |
| `--shields-up` | **incompatible**: "Unable to turn on Funnel while shields-up is enabled". Dropped; it only governs the owner's own tailnet devices |
| containerboot | gives an interactive login 60 s, then exits; `ts.sh login` runs tailscaled directly so the login waits |
| stale prefs | a state with `--shields-up` made `tailscale up` refuse: `--reset` added, so each start asserts the committed settings |
| first request | TLS reset until the certificate was issued (16:58:21Z, 20 s after the first request) |

Activation checks from the prepared runbook, now answered: a proxy to the
non-loopback `coco:8080` works; `/ws` and `/healthz` are proxied to the
same paths (no mount-path stripping); `cap_drop: ALL` works in userspace
mode. Cloudflare was compared and verified offline only; not used.

## C4 — exposure

**Host side** (`c4_exposure/host_listeners_idle.txt`, idle): **no TCP
listener on any non-loopback address**, no sshd, nothing on 22/2375/2376,
Docker API only the root:docker unix socket. Non-loopback UDP: mDNS 5353
(the desktop's browsers) and two ephemeral ports. With the stack up the
only Docker publication is `127.0.0.1:8080` (C2/C1b `exposure_local.txt`).
Nothing on this host can be reached from any network except through the
tunnel's outbound connection.

**External** (genuinely different networks):

| vantage | check | result |
|---|---|---|
| check-host.net nodes (CH, ES, ID, IR, SE, TR, BR, IN, RU, US, FI, … ; `external_checkhost_run2/3.txt`) | `/healthz` | 200 on 4/4 |
| same | `/`, `/api/session`, `/video/camera` | 404 on 12/12 |
| same | `:8443/healthz`, `:10000/healthz` | no HTTP (connection broken) on 8/8 |
| WebFetch (Anthropic's fetchers) | `/healthz`; `/api/session` | coco.v1 `ready`, code session, no ids or code; 404 |

**Through Funnel, from this host's network** (`tunnel_check_from_host.txt`,
`COCO_CHECK_IP=-4`; this host has no working IPv6): Pages origin 101,
`localhost` 101, `evil.example` / look-alike / `null` 403; 18 other
paths 404; POST `/healthz` 405; cleartext → 302; no `Server` banner;
CORS only for the Pages origin. PASS. These Origin verdicts are made by
platform_server and do not depend on the client's network.

**Not done, deliberately:** no address was port-scanned. This host sits
behind a shared NAT (10.40.1.125/21 → 43.224.159.233) that belongs to the
network's operator, and an agent asked to scan it refused for lack of
authorization; Funnel's ingress servers belong to Tailscale. Two "remote"
agents turned out to run on this machine (same egress), so their results
are counted as host-side only.

## C6 — through the tunnel (this host as the client; NOT the phone session)

**A defect, measured, then fixed.** The shipped page driven through
Funnel lost its WebSocket **17 times in ~15 min** (attempt 2); each loss
correctly ended control and stopped COCO. Cause:

| soak (`tunnel_soak.py`, spectator) | result |
|---|---|
| no camera, 10 Hz, 120 s | 0 closes, 10.12 Hz, **58.0 KiB/s** delivered |
| camera at the local defaults | closed at **44.6 s, "ping timed out"** (server keepalive 10 s); 37.8 KiB/s delivered |
| this host's uplink (Cloudflare speed test, 2 × 4 MB) | **1.83 MB/s**: the ceiling is the tunnel's |
| Funnel path | active ingress peer (home DERP Tokyo) has **no direct address: relayed** |

The backlog grows in buffers beyond the server (kernel, tailscaled, the
relay) where the per-client in-flight bound cannot see it. **Fix
(5b58960, `remote:=true` only):** telemetry every 2nd tick (5 Hz), camera
3 fps (max 5) at half scale, depth likewise. Derived ~31 KiB/s.

After the fix (image 3f8e34da16eb):

| measurement (n) | value |
|---|---|
| app ping RTT, no camera (55) | p50 **564 ms**, p95 3997, p99 4614, max 4614 |
| app ping RTT, camera (89) | p50 **1460 ms**, p95 7198, p99 8307, max 8307; 0 closes in 180 s |
| camera soak 300 s | 1 close ("ping timed out" at 128.4 s), 4.70 Hz |
| shipped page, `c6_tunnel_page_teleop_nav`: drive frame → wheel (170) | p50 **45.2 ms**, p90 151.5, p99 249.3, max 367.7 |
| key press → first wheel (41) | p50 149.8, p99 317.0, max 367.7 ms |
| STOP frame → wheel zero (1) | **148.4 ms**; 0 moving commands 0.2–3.3 s; latched banner shown |
| Nav2 goal → first plan (4) | p50 153.3, max 156.8 ms; goals 5/5 succeeded |
| telemetry received | 4.65 Hz; gaps p50 185, p99 1001, **max 15452 ms** |
| reconnects | **2 in 407 s** |
| claim through the page | "holder: you (the driver)" 0.31 s after pressing Take control |
| public status line | "**Live now**, 18 min left. Nobody is driving yet; the host has the control code." (real page, real endpoint) |
| wheel publishers | 1 (`cmd_vel_arbiter`) throughout |

So the **command path** (phone → robot) is fast; the **view** (robot →
phone) lags by seconds and the 10 s keepalive still drops a connection
every few minutes. A drop stops COCO and the driver must claim again.
Options for the owner (not taken): a longer keepalive for remote
sessions (slower detection of a vanished driver; the 0.5 s wheel
watchdog still stops motion); a direct path (a published UDP port for
WireGuard: new exposure); end-to-end flow control (protocol addition).

## Deployment (2026-10-03/04, owner-approved)

| step | result (measured) |
|---|---|
| push `live` 74ab139..a61150c (fast-forward) | PR #8: CI run 37144071122 **success**, Lab run 37144071114 **success** |
| fast-forward `main` 54133fe..a61150c (only after both green) | CI run 37144441639 **success**; Lab run 37144441651 **success**, including "deploy to GitHub Pages (main only)" |
| deployed bundle `assets/index-DwMTg_hp.js` (332,655 B) | Live tab present (claim box, status line, idle-pause wording); `coco-live.taile7cb60.ts.net` present; **0** ROS topic names |
| deployed CSP `connect-src` | `'self'`, Pyodide CDN, `ws://localhost:*`, `ws://127.0.0.1:*`, `wss://` and `https://coco-live.taile7cb60.ts.net`, nothing else |
| public Live URL rendered (headless Firefox), stack down | "No live session right now. No session is scheduled."; Replay + Docker quickstart links shown; connection `closed` (`c5_public_status_offline/`) |

No release, no tag, no branch deleted, no force-push. The keepalive is
unchanged (10 s / 10 s; owner: keep it until further notice).

## C6 — the phone session: NOT YET RUN

Nothing below this line is measured. The public page is now deployed
(above); the stack and the tunnel are down until the owner says "start".

## C5 — public Live status

`LIVE_REMOTE = { ws: 'wss://coco-live.taile7cb60.ts.net/ws' }` (5b58960);
the CSP gains exactly its `wss:` and `https:` origins (`check_dist`).
`lab_web/src/live/status.ts`: "Live now" only when the configured
endpoint's `/healthz` answers coco.v1 with an open code session; starting
(503), ended, an open server, non-JSON, another protocol, unreachable,
timed out and a malformed endpoint all read "not live". `schedule.json`
is empty (no session invented). Not live → links to Replay and the
Docker quickstart. The probe is the site's one cross-origin request,
`credentials: 'omit'`, pinned by `site.test.ts`.

## Known limitations

- Spectators cannot STOP (owner decision 3); if the driver leaves, the
  disconnect stops COCO; otherwise the host's kill switch is the backstop.
- The Origin allowlist is a browser boundary only; the control code is the
  only credential (8 chars from 31 symbols, ≈ 39.6 bits, 5 tries per
  socket, rate-limited).
- The image base is pinned by tag, not digest.
- The kill latency above includes `docker exec` start-up; it is a host
  action, not a browser one.
- **Funnel is DERP-relayed here**: ~58 KiB/s, view lag of seconds (app
  RTT p50 0.56–1.46 s, max 8.3 s), and a keepalive drop every few
  minutes, each of which stops COCO and needs a re-claim.
- The Pages origin allowlist admits every page under
  `https://gauthamcodes.github.io` (an Origin has no path).
- Spectators cannot STOP, so a spectator who sees trouble cannot help;
  the host's kill switch is the backstop.
- The tailnet (23 peers, the owner's) can reach the sidecar's peer API and
  its :443; shields-up was impossible with Funnel.

## Unverified

- **The phone session** (mobile data, the real Live tab on Pages): not run.
- An autonomous fetch through the tunnel (C1b ran on loopback).
- WebSocket Origin checks from an external network (done through Funnel
  from this host's network; external nodes checked reachability/paths).
- The policy defaults under real use (idle 60 s, cap 20 min, rate limits).
- A real phone driving the Live tab (Part B ran headless Firefox only).
- The arm stopping mid-grasp on STOP (carried from the safety fixes).

## Reproduce

```bash
# C1 (fresh container per run; Docker group; nothing else simulating)
git archive -o /tmp/head.tar HEAD && mkdir -p /tmp/head && tar -xf /tmp/head.tar -C /tmp/head
bash docs/data/live/part_c/scripts/docker_build.sh /tmp/head
bash docs/data/live/part_c/scripts/docker_run.sh docs/data/live/part_c/c1_fetch_red fetch red
# C1b: fetch in the remote configuration (fresh container)
PROBE=probe_remote_fetch PROBE_ARG=red COCO_SESSION_IDLE_S=60 COCO_SESSION_CAP_S=1200 \
  bash docs/data/live/part_c/scripts/docker_remote_run.sh docs/data/live/part_c/c7_remote_fetch_red
python3 docs/data/live/part_c/scripts/an_remote_fetch.py docs/data/live/part_c/c7_remote_fetch_red  # after gunzip
# C3: tunnel up (owner logged the node in once: docs/live/tunnel/tailscale/ts.sh login)
COCO_TS_STATE=$HOME/coco_tailscale_state docker compose -f docker-compose.yml -f docker-compose.remote.yml \
  -f docs/live/tunnel/tailscale/docker-compose.tunnel-tailscale.yml up -d
# C4
bash docs/data/live/part_c/scripts/host_listeners.sh
COCO_CHECK_IP=-4 bash docs/live/tunnel/external_check.sh coco-live.taile7cb60.ts.net
bash docs/live/tunnel/checkhost.sh coco-live.taile7cb60.ts.net
# C6 (this host as client)
python3 docs/data/live/part_c/scripts/tunnel_soak.py OUT.jsonl wss://coco-live.taile7cb60.ts.net/ws 180 camera
bash docs/data/live/part_c/scripts/tunnel_browser_run.sh docs/data/live/part_c/c6_tunnel_page_teleop_nav teleop_nav
python3 scripts/live_check/analyse_b.py docs/data/live/part_c/c6_tunnel_page_teleop_nav
# C2 + C4 host half (remote compose)
bash docs/data/live/part_c/scripts/docker_remote_run.sh docs/data/live/part_c/c2_session_docker
PROBE=probe_expiry COCO_SESSION_CAP_S=90 \
  bash docs/data/live/part_c/scripts/docker_remote_run.sh docs/data/live/part_c/c2_expiry_driving
python3 docs/data/live/part_c/scripts/an_session.py docs/data/live/part_c/c2_session_docker   # after gunzip
python3 docs/data/live/part_c/scripts/an_expiry.py docs/data/live/part_c/c2_expiry_driving
# tests (workspace overlay ~/coco_live_ws, synced with sync_ws.sh)
ROS_DOMAIN_ID=74 bash ~/coco_live_ws/src/coco-labs/scripts/run_all_package_tests.sh
(cd lab_web && npx tsc --noEmit -p . && npx vitest run && npm run build && npm run check:dist)
```
