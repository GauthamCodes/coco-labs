# COCO Live — the real robot in the browser (Phase 2)

The Live tab of COCO Lab drives the simulated COCO robot running the real
ROS 2 / Nav2 stack, in three modes: **teleop**, **Nav2 goal**, and the
**autonomous fetch**. It works against a stack on your own machine, or,
during a scheduled public session, against the owner's machine through a
tunnel.

- Public page: <https://gauthamcodes.github.io/coco-labs/?view=live>
- Public endpoint (only while a session is on):
  `wss://coco-live.taile7cb60.ts.net/ws`
- Evidence: [`PART_A_AUDIT.md`](PART_A_AUDIT.md), [`SAFETY_FIXES.md`](SAFETY_FIXES.md),
  [`PART_B.md`](PART_B.md), [`PART_C_REPORT.md`](PART_C_REPORT.md); the wire
  contract is [`../WEB_API.md`](../WEB_API.md); the tunnel runbook is
  [`tunnel/README.md`](tunnel/README.md).

Every number here is **(measured)** with its source, **(derived)**,
**(owner-reported)**, or marked unverified. n is 1 unless stated; one run is
not a rate.

---

## 1. Architecture

```
phone / laptop browser                       the owner's machine (Docker)
┌──────────────────────────┐               ┌────────────────────────────────────────────────┐
│ lab_web (GitHub Pages)   │  wss / https  │ coco-tunnel  tailscale (userspace, uid 1000,   │
│  Live tab: coco.v1 only, ├──── Funnel ──▶│   caps dropped) serves /ws + /healthz ONLY     │
│  never a topic name      │  (relayed)    │        │ compose network                       │
└──────────────────────────┘               │        ▼                                       │
                                           │ coco-platform  platform_server (coco.v1)       │
                                           │   remote:=true · access:=code · origins        │
                                           │   │ publishes ONLY safety.PUBLISH_ALLOWLIST    │
                                           │   ▼                                            │
                                           │ /cmd_vel_teleop · /mission/* · /goal_pose      │
                                           │   ▼                                            │
                                           │ cmd_vel_arbiter ── the ONLY wheel publisher ─▶ │
                                           │   Gazebo (headless), Nav2, mission executive   │
                                           └────────────────────────────────────────────────┘
```

- **The browser speaks coco.v1 and names intents, never topics.** The
  server maps each intent to its allowlisted publisher.
- **One wheel publisher**: `cmd_vel_arbiter`, which already lets teleop
  preempt autonomy. Nothing in Live publishes to the wheels.
- **Ground truth is display-only.** It reaches the telemetry builder and
  nothing that commands (AST test).
- **The tunnel dials out.** Nothing on the host listens on a non-loopback
  address, and Docker publishes only `127.0.0.1:8080`.

## 2. Security boundaries

| boundary | what enforces it | evidence |
|---|---|---|
| Only `/ws` and `/healthz` are public | Funnel `serve.json` (two handlers), and `remote:=true` (everything else is a bare 404 with no server banner) | `test_tunnel_config.py`; `test_live_session.py`; external nodes and WebFetch (C4) |
| Browser origins | `origins` allowlist: the Pages origin and `http://localhost:*` / `127.0.0.1:*`; `remote:=true` refuses to start without one | 403 for foreign and `null` origins through Funnel (C4) |
| Who may command | `access:=code`: one driver per host-issued 8-character code; spectators are refused **every** command, STOP included | `test_control.py`; live C2 20/20, C1b |
| Abuse | per-client token buckets (60 frames/s, `drive` 20/s, other commands 2/s burst 6); 5 bad codes or 100 refusals in a row close the socket; 25 clients | C1b: burst 20/20 ack/limited; flood closed, 0 of 300 admitted |
| Host controls | `session_new` / `session_code` / `session_kill` are ROS services inside the container (loopback DDS), reached by `docker exec`; no frame maps to them | `scripts/live_session.sh` |
| Network | no SSH, no Docker API on the network, no ROS/DDS or Gazebo ports published; the Funnel node runs no Tailscale SSH, no routes, no exit node | `host_listeners.sh` (C4) |
| The credential | the control code only (≈ 39.6 bits (derived), never in a URL). The Origin check is a browser boundary, not authentication | — |

## 3. Safety behaviour

| event | what happens | measured |
|---|---|---|
| driver presses STOP | latched STOP: wheels zeroed and held, mission aborted, arbiter idle until a mode is picked | through Funnel (host client): STOP → wheel zero 148.4 ms; local: 1.4–5.8 ms (SAFETY_FIXES) |
| spectator presses STOP or any command | refused `spectator` (owner decision 3) | C2, C1b (mid-CLIMB: mission unaffected) |
| driver disconnects | control ends → latched STOP, mission aborted | **phone session: 0.3 m/s → rest in 0.54 s, mission ABORT `OPERATOR_ABORT`, 0 moving commands after**; C2: wheels zero +16.8 ms |
| driver idle 60 s | control released → latched STOP | C1b: 59.91 s after the lease returned |
| a mission or a browser Nav2 goal is running | **autonomy holds the idle lease**: the idle clock is suspended, not reset; `last_input_s` keeps counting; a full 60 s window when autonomy ends | C1b: driver kept for 528 s with no input |
| session cap (20 min) | session over → latched STOP, every socket closed (4403), old code void | C2: 0 moving commands to +10 s while driving |
| host kill switch | same as the cap, at once | C2: wheel zero +318.4 ms (includes `docker exec`) |
| commands stop arriving | the wheel watchdog stops the robot in 0.5 s | design (P0.1) |
| the server exits | publishes a stop on the way out | design |

The STOP button is visible in every mode. A remote STOP is the driver's
alone, so the host keeps the kill switch at hand during a public session.

## 4. Running a public session (host)

One-time: the Funnel node is logged in (`tunnel/tailscale/ts.sh login`,
owner's browser; state in `~/coco_tailscale_state`). Then, per session:

```bash
cd ~/coco_live_ws/src/coco-labs            # or any checkout with the image built
# 0. nothing else simulating (one Gazebo at a time)
pgrep -af 'g[z] sim'; docker ps
# 1. the stack and the tunnel (a fresh simulator every time)
COCO_TS_STATE=$HOME/coco_tailscale_state docker compose -f docker-compose.yml \
  -f docker-compose.remote.yml -f docs/live/tunnel/tailscale/docker-compose.tunnel-tailscale.yml up -d
docker exec coco-tunnel tailscale --socket=/tmp/tailscaled.sock funnel status   # /ws + /healthz only
# 2. a fresh session (20 min from now) and its code, for the driver
bash scripts/live_session.sh new
bash scripts/live_session.sh code
# 3. during the session
bash scripts/live_session.sh status      # health + the public `live` summary
bash scripts/live_session.sh kill        # the kill switch: stop, end, void the code
# 4. after it: exposure ends the moment the sidecar stops
COCO_TS_STATE=$HOME/coco_tailscale_state docker compose -f docker-compose.yml \
  -f docker-compose.remote.yml -f docs/live/tunnel/tailscale/docker-compose.tunnel-tailscale.yml down
```

The driver opens the public page on any device, waits for **Live now**,
types the code under **Control code** and presses **Take control**.
Everyone else who opens the page watches.

To announce a session, add it to `lab_web/src/live/schedule.json`
(`start` in ISO 8601 **with an offset**, `minutes`) and deploy. The page
never says "Live now" because of the schedule; only the endpoint's
`/healthz` reporting an open code session does.

## 5. Running it yourself (local)

The Docker quickstart is [`../DOCKER.md`](../DOCKER.md):
`docker compose up -d`, then open `http://localhost:8080/` (verified,
DOCKER.md), or serve the Lab yourself (`cd lab_web && npm run build &&
npx vite preview`) and open its Live tab, whose default endpoint is
`ws://localhost:8080/ws` (verified, PART_B). Opening the *public* Pages
site against a local stack is **unverified**: browsers may prompt for, or
block, an https page reaching `ws://localhost` (PART_A_AUDIT §5.5). Local
(`access:=open`) is the single-user appliance: no code, and anyone
connected may STOP.

## 6. Recovery

| symptom | cause | do |
|---|---|---|
| "STOPPED (latched)" banner | a STOP, a release, an idle release or a disconnect | the driver picks a mode, or starts a mission |
| page says "session has ended" / socket closed 4403 | cap or kill | host: `live_session.sh new`, give out the new code |
| "Live now" missing while the stack is up | `/healthz` 503 (a component down), or the tunnel is down | `live_session.sh status`; `docker logs coco-tunnel`; `funnel status` |
| tunnel container exits at start | stale prefs; `--shields-up` (cannot combine with Funnel) | the compose file passes `--reset`; never add `--shields-up` |
| Funnel login gone | state dir lost | `ts.sh login` (owner's browser), then `ts.sh caps` must show `funnel True` |
| first HTTPS request reset | certificate being issued (≈ 20 s, measured) | wait, retry |
| the page reconnects every few minutes | Funnel relay lag past the 10 s keepalive (§8) | the driver claims again; COCO was stopped by the drop |
| anything wrong with the robot | — | `live_session.sh kill`, then `compose down`; a fresh stack every time |

## 7. Measured results (summary)

| what | value | source |
|---|---|---|
| local: drive frame → wheel | p50 4.6 ms, max 9.7 (n = 170) | PART_B |
| local: STOP → wheel zero; fetches from the page | 6.2 ms; 3/3 COMPLETE | PART_B |
| Docker remote configuration: fetch | red COMPLETE, 16 states, 0 recoveries | PART_C C1b |
| through Funnel (host as client): drive → wheel; STOP → zero; goal → plan | p50 45.2 ms (n = 170); 148.4 ms; p50 153.3 ms, goals 5/5 | PART_C C6 |
| through Funnel: delivered throughput; app RTT | ≈ 58 KiB/s ceiling (uplink 1.83 MB/s); p50 0.56–1.46 s, max 8.3 s | PART_C C6 |
| phone on mobile data: claim, teleop, Nav2, mission start, disconnect → stop | instrumented; goal → plan 13.1 ms; disconnect: rest in 0.54 s, mission aborted | PART_C C6 |
| phone page readouts | RTT ≈ 282–293 ms, telemetry 5 Hz (**owner-reported**) | PART_C C6 |
| exposure | no non-loopback TCP listener; external: only `/ws`, `/healthz` | PART_C C4 |
| tests (2026-10-04, on the Part D tree) | `run_all_package_tests.sh` **2691 passed, 0 failed** (11 packages; coco_web 857, coco_rl 241); lab_web vitest **238**, tsc, build, `check_dist` clean; CI and Lab green on a61150c | this session |

## 8. Known limitations

- **Funnel is DERP-relayed here.** About 58 KiB/s, a view that lags by
  seconds, and a 10 s keepalive that drops a connection every few minutes
  (2 in 407 s, measured). Each drop stops COCO and needs a re-claim. The
  remote stream budget (telemetry 5 Hz, camera 3 fps at half scale) is
  why it works at all. The keepalive stays 10 s (owner, 2026-10-04).
- **Phone-test evidence gaps** (PART_C C6): STOP from the phone, a
  second-device spectator, preemption from the phone, a completed mission
  from the phone, and the cause of the phone's disconnect are not in the
  record.
- The browser goal's status did not show its preemption by a mission's
  goal (34 s of `executing`).
- Spectators cannot STOP; the host's kill switch is the backstop.
- The Pages origin admits every page under `https://gauthamcodes.github.io`
  (an Origin has no path).
- The owner's tailnet devices can reach the Funnel node's peer API and
  :443 (shields-up is impossible with Funnel).
- The image base is pinned by tag, not digest.
- Not built from ROADMAP §3.5: the planner choice in Nav2 mode (lab hook),
  an optional heading on `nav_goal`, the 3D view (should-have).
- **Since Phase 5 (2026-10-06) the autonomous mode DISCOVERS the target**
  (`mission.launch.py search:=true`, the default): told only the colour, it
  searches the bays in the order `coco_lab.regionsearch` chooses
  (`docs/labs/LAB4_SEARCH.md`). The page's label is chosen from what the
  RUNNING mission reports on `/mission/search` (coco_web's additive
  `mission.search` block): "discovers" only for `mode=discover`; a stack
  launched `search:=false` is labelled told (`resolve_lane()`), and one that
  reports nothing gets no claim. *(Until 2026-10-06 this line read: "The
  autonomous mode is **told** the lane (`resolve_lane()`); discovery is
  Phase 5. The page says so.")*

## 9. Backlog (from the phone test), in priority order

Each item has an acceptance test; none weakens STOP, the watchdog,
control ownership, origins, session limits or network isolation.

1. **Remote session stability.** End-to-end flow control (an additive
   client acknowledgement, so the server stops queueing past what the
   phone has received), and an owner decision on the keepalive or a direct
   (non-relayed) path. *Accept:* a 15-minute session from a phone on mobile
   data through the public URL with **0 involuntary disconnects**, and the
   app RTT p95 < 1 s, measured by the page's exported log (item 3).
2. **Telemetry rate and size.** Send the slow-changing blocks (session,
   perf, components ≈ 1.9 KB of a 4.4 KB frame, measured) only on change,
   as an additive stream, so pose and status can return to 10 Hz remotely
   within budget. *Accept:* remote telemetry ≥ 10 Hz at ≤ 50 % of the
   measured ceiling; protocol additive (`test_additive.py`).
3. **Page-side session log export.** A "download session log" control
   that saves the page's send log and telemetry arrivals, so phone-side
   latency can be measured rather than read off the screen. *Accept:* the
   exported file joins with the recorder (`analyse_b.py`) for a phone run.
4. **Mobile layout.** *Accept:* at 360 × 800 CSS px, STOP, the joystick
   and the map are visible without scrolling; no horizontal scroll; touch
   targets ≥ 44 px; a headless-viewport test pins it.
5. **Visualisation quality.** The robot's footprint and heading, the plan
   and local trajectory legible on a phone, pinch-zoom and pan on the map.
   *Accept:* a visual check at 360 px and 1400 px against recorded
   telemetry (Replay), with screenshots in the report.
6. **Truthful preemption.** When a mission replaces a browser Nav2 goal,
   the page says so within one telemetry frame. *Accept:* a socket test
   and a live run.
7. **Close the phone-test gaps.** One owner session, scripted: STOP from
   the phone, a second device as spectator (Drive and STOP refused),
   teleop preemption of a running mission, a mission to COMPLETE, a
   deliberate airplane-mode disconnect. *Accept:* every row instrumented
   in a C6-style table.
8. **Pin the image base by digest.** *Accept:* `docker build` from a
   digest; `test_docker_context.py` asserts it.
9. **ROADMAP §3.5 not yet built:** planner choice in Nav2 mode, `nav_goal`
   heading, the 3D view.
