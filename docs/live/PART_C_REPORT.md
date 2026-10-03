# Phase 2 · Part C — driver, spectators, remote sessions (IN PROGRESS, 2026-10-03: at the tunnel gate)

Branch `live`. Evidence: `docs/data/live/part_c/` (gunzip `*.gz` first).
Harness: `docs/data/live/part_c/scripts/`. Every number is **(measured)**
unless marked; n = 1 per row. One run is not a rate.

## Status

| part | status |
|---|---|
| precondition | holds: Part A; safety fixes on main (`labs/main` = 54133fe); Part B and its invariants; CI **and** Lab green on 74ab139 (GitHub pull_request runs; the Part B log entry had not recorded this) |
| C1 Docker fetch | **done: 1/1 COMPLETE** |
| C2 session model | **done**: pure module + server wiring + live in Docker |
| C3 tunnel | **PREPARED, NOT ACTIVE; waiting on the owner's choice.** Both options built as compose sidecars in `docs/live/tunnel/` (README there). Cloudflare ingress verified offline; Tailscale untested without an account. Nothing exposed |
| C4 exposure | **host half done** (below); the external half needs the tunnel |
| C5 public status | **done**; `LIVE_REMOTE` is `null` until a tunnel exists, so the site truthfully says no session is configured. 89e0239: a 503 no longer claims only "starting"; negative counts/times are dropped |
| C6 remote session | not started: needs C3, then the owner on a phone on mobile data |
| C7 / C8 | not started (final CI after C6) |

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
| (this commit) | C3 prepared: `docs/live/tunnel/` (both options, offline ingress check, `external_check.sh`) |

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

`run_all_package_tests.sh`, all 11 packages, domain 74, quiet machine:
**2665 passed, 0 failed** (Part B: 2512) on cbc1e26. After 89e0239,
affected packages only: coco_web **850** (836), coco_rl **236**; lab_web
vitest **238** (234), typecheck, build and `check_dist` clean. The full
run is owed at the end of Part C.

| package | Part B | now | what |
|---|---|---|---|
| coco_web | 688 | 850 | `test_control.py` (pure, fake clock, no sleeps; +7 lease tests replacing 1), `test_live_session.py` (real sockets; +3 origins refusals, +5 no-banner) |
| coco_rl | 231 | 236 | remote compose: loopback-only port, code/remote/origins, entrypoint + launch forwarding |
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

## C3 — tunnel: PREPARED, NOT ACTIVE (owner choice open)

`docs/live/tunnel/README.md` has the vendor facts (re-read 2026-10-03),
both runbooks, and what remains to be checked at activation. Both
connectors are a sidecar on the compose network that reaches `coco:8080`
(the platform_server that the host publishes on `127.0.0.1:8080`) and
routes only `/ws` and `/healthz`. No host network, no published port, no
Docker socket.

| | prepared | verified |
|---|---|---|
| Cloudflare named tunnel | `config.yml.template`, compose sidecar (cloudflared 2026.9.3, read-only, caps dropped), `ingress_check.sh` | **offline (measured):** `ingress validate` OK; `/ws`, `/healthz` → coco; 13 other paths and hosts → 404 (`c3_tunnel_prep/cloudflare_ingress_offline.txt`) |
| Tailscale Funnel | `serve.json` (`/ws`, `/healthz` only, AllowFunnel 443), compose sidecar (userspace, `--shields-up`, `tag:coco-live`), policy-file snippet | **not verified**: needs an account. Three activation checks are listed in the README (proxy to a non-loopback host; mount-path semantics; shields-up vs Funnel) |
| both | `docker compose config` parses; the only published port is `127.0.0.1:8080` | `external_check.sh HOST [HOME_IP]`: syntax-checked only, **not yet run** |

The one missing input is the owner's: which tunnel, and its hostname
(Cloudflare: a hostname on a domain on Cloudflare DNS; Tailscale: the
tailnet name, which appears in the public URL). Each also needs a
one-time account action that only the owner can do (browser login, or
the policy file and an auth key).

## C5 — public Live status

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

## Unverified

- Everything through a tunnel (C4 external, C6). The Tailscale
  configuration as a whole; `external_check.sh` has never run.
- The lease change (89e0239) is unit- and socket-tested, not yet driven
  live: C2's idle-release row predates it, but no autonomy ran there, so
  the path it measured has not changed.
- The policy defaults under real use (idle 60 s, cap 20 min, rate limits).
- A real phone driving the Live tab (Part B ran headless Firefox only).
- The arm stopping mid-grasp on STOP (carried from the safety fixes).

## Reproduce

```bash
# C1 (fresh container per run; Docker group; nothing else simulating)
git archive -o /tmp/head.tar HEAD && mkdir -p /tmp/head && tar -xf /tmp/head.tar -C /tmp/head
bash docs/data/live/part_c/scripts/docker_build.sh /tmp/head
bash docs/data/live/part_c/scripts/docker_run.sh docs/data/live/part_c/c1_fetch_red fetch red
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
