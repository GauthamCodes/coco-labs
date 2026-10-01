# Phase 2 · Live — Part A: audit and design (2026-10-02)

Branch `live` (from `lab1` = `main` = 6249e7d). No code changed in this part.
Evidence: `docs/data/live/part_a/` (probe, recorder, logs; see its README).

Everything marked **(measured)** comes from one live run on 2026-10-02: a fresh
simulator, `mission.launch.py rviz:=false platform:=true` from
`~/coco_labs_ws` (main adb7d55; coco_web, coco_mission and custom_teleop are
identical to 6249e7d), headless, `ROS_DOMAIN_ID=62`, on a quiet machine (load
about 2, no other Gazebo). A scripted coco.v1 client did the driving, and a
ROS recorder logged the command path. **One run is not a rate.**

---

## 0. The safety defect, first

**`stop` does not stop a running mission (measured).** While the fetch
mission was driving its first leg (`NAVIGATE_TO_RAMP`, arbiter
`active=nav`), the client sent exactly what the page's STOP button sends:
`stop`, three zero `drive`s at 100 ms, then `set_mode stop`.

| after `stop` left the client | what happened |
|---|---|
| +1.5 ms | first zero on `/diff_drive_controller/cmd_vel` |
| +310 ms | `/mission/mode` = `idle` (the browser's `set_mode stop`) |
| +698 ms | `/mission/mode` = `nav`, the executive's 2 Hz re-assertion |
| **+723 ms** | **first moving wheel command again**: (0.28, −0.28) |
| next 7.7 s | **152 moving wheel commands**, up to 0.30 m/s, until the client sent `mission abort` |
| `abort` +87 ms | last moving wheel command |

The page shows a "Stopped" toast while the robot drives on. The mechanism:

1. The coco.v1 `stop` intent publishes **one** zero on `/cmd_vel_teleop`
   (`platform_server.publish_stop`).
2. The arbiter's teleop source is fresh for 0.3 s (`SOURCE_TIMEOUT`).
3. After that, the mode-selected source drives again.
4. `set_mode stop` writes `idle` to `/mission/mode`, but `mission_executive`
   re-asserts its own mode at 2 Hz (`PUBLISH_HZ`, by design: "the mode MUST
   be re-asserted").

Nothing in the stop path calls `/mission/abort`.

**Proposed fix (needs your decision, see §7 Q1).** The server's `stop`
handler also calls the allowlisted `mission_abort` whenever the mission
reports `active`. Abort was measured to stop the wheels within 87 ms.
- This stays inside coco_web and touches neither the arbiter nor the
  executive.
- Every client gets the fix, the old page included.
- It makes `stop` do what WEB_API already promises ("publishes an explicit
  zero; always honoured" plus the page's "Stopped").
- Tests: a pure test that `stop` with an active mission issues the abort,
  and a live re-measurement in Part B.

---

## 1. How the existing panel does each mode, end to end

The command path (`safety.py`, `cmd_vel_arbiter.py`):

```
browser --coco.v1--> platform_server --allowlist--> ROS
  drive      -> /cmd_vel_teleop  (TwistStamped) ----------------------+
  Nav2: controller_server -> velocity_smoother -> collision_monitor   |
        -> /cmd_vel -> cmd_vel_relay -> /cmd_vel_gated ---------------+-> cmd_vel_arbiter
  ramp_driver -> /cmd_vel_rl ;  approach_server -> /cmd_vel_approach -+     |
  /mission/mode (String) latches which autonomous source is eligible       v
                                     /diff_drive_controller/cmd_vel (sole publisher)
```

Arbiter rule (`select_source`): **teleop wins whenever `/cmd_vel_teleop`
arrived within 0.3 s, in every mode including `idle`**. Otherwise it forwards
the source `/mission/mode` selects (`nav`, `rl`, `approach`) if that source is
fresh. Otherwise it sends zeros for 1 s, then goes silent.

| Mode | Intent(s) | Allowlist entry | ROS effect | What the arbiter forwards |
|---|---|---|---|---|
| Teleop | `set_mode {mode:"teleop"}` | `mode` → `/mission/mode` String | `teleop` | teleop only while fresh; zeros after |
| | `drive {linear, angular}` (10 Hz while held, clamped 0.5 m/s, 1.2 rad/s) | `drive` → `/cmd_vel_teleop` TwistStamped | one TwistStamped per frame | **teleop, in any mode** (measured 3.2 ms from the browser to the wheel topic, no mission) |
| Nav2 | `set_mode {mode:"auto"}` | `mode` → `/mission/mode` | `nav` | `/cmd_vel_gated` (Nav2 after the monitor) |
| | `nav_goal {x, y}` | `nav_goal` → `/goal_pose` PoseStamped (map, yaw 0) | bt_navigator's goal subscription | — |
| Autonomous | `select_target {colour}` | `target_colour` → `/mission/target_colour` | executive's colour | — |
| | `mission {action:"start"\|"abort"}` | `CALL_ALLOWLIST` → `/mission/start`, `/mission/abort` (Trigger, fire-and-forget) | executive runs the 16-state machine; publishes `/mission/mode` at 2 Hz | whatever the executive's mode selects: `nav` → `rl` → `approach` → `idle` for the arm |
| Stop | `stop {}` | `drive` (one zero) | one zero TwistStamped; clears the pilot lock | zero for ≤ 0.3 s, then **the mode's source again** (§0) |
| (page STOP button) | `stop` + 3 × zero `drive` + `set_mode stop` | as above | `/mission/mode idle`, overwritten within 0.5 s if the executive is running | as above |

Who may send what today:
- **`drive`** is gated only by the pilot lock: the first client to drive
  holds it until 0.5 s of silence.
- **`set_mode`, `nav_goal`, `select_target`, `mission`, `set_arm` and
  `set_gripper`** are accepted from **any** connected client.
- **`stop`** is accepted from anyone, by design.

### Second defect, functional, not unsafe: Nav2 mode does not move the robot under `mission.launch.py` (measured)

With the executive running and IDLE (after the abort):

| after `set_mode auto` | |
|---|---|
| +2 ms | `/mission/mode` = `nav` |
| +390 ms, then every 0.5 s | `/mission/mode` = `idle` (the executive's re-assertion; it asserts `idle` while IDLE) |
| `nav_goal (1.0, 0.0)` | `/goal_pose` seen at +1.8 ms; **25 `/plan` messages**, the first at +9.8 ms; **499 moving `/cmd_vel_gated` commands** |
| wheels | **0 moving commands**; arbiter `mode=idle active=none` throughout; pose unchanged |

Nav2 plans and commands, and the arbiter correctly refuses all of it,
because the executive holds the mode at `idle`. The Docker image runs this
same launch file. The panel's Nav2 mode can only have worked with
`executive:=false`. The fix needs a decision (§7 Q2).

---

## 2. Telemetry and map today, and what the Live view lacks

| Frame | Rate | Carries |
|---|---|---|
| `welcome` | once per connection | session, MJPEG descriptors, subscriptions, `world` (map-frame bays, ramp, platform, home), `limits` (velocities, colours, modes, arm, gripper), `commands` |
| `telemetry` | **10 Hz** (measured **10.00 Hz**, 4,597 frames over 459.6 s, one client) | `robot` {`pose` (odometry put through the last AMCL map→odom correction), `frame`, `localised`, `velocity`, `online`}; `mission` (the whole executive line: state, previous, words, step N/16, owner, mode, reason, timing…); `nav` {`online`, `path` (≤120 points of `/plan`), `active_source`}; `sensors` {lidar (JSON or binary), perception, grasp}; `platform` {session, `arbiter` {mode, active, ages}, perf, connection, health, `pilot`} |
| `map` | on connect, then on change | occupancy grid, base64 int8 |
| binary | lidar 10 Hz (with telemetry); camera 10 fps default, 15 max; depth 5 fps default | `COCO` frames (`binary.py`), opt-in for camera and depth |

Sources update at their own rates. The arbiter status is 2 Hz, so
`active_source` has 0.5 s resolution, and the mission line is 2 Hz plus on
change.

| Needed for Live | Today | Gap |
|---|---|---|
| AMCL pose (belief) | folded into `robot.pose`. **`localised` stayed `false` for the whole 400 s the robot sat at spawn (measured)**: AMCL publishes `/amcl_pose` only after a filter update, and that needs motion | **missing** as its own field, with covariance and age; the UI must say "belief not yet updated" until the first one |
| Ground truth | `/model/coco/odometry` is subscribed **raw, never decoded** (liveness only) | **missing** |
| Global plan | `nav.path` | present |
| Local trajectory | — | **missing**. DWB publishes `/local_plan` by default; not yet verified live |
| Nav goal status | — | **missing**: no result or status for a browser goal |
| Mission state | full block, step N/16 | present |
| Arbiter active source | `nav.active_source`, `platform.arbiter` | present (2 Hz) |
| Who holds control | `platform.pilot` = a client id | **partial**: the client is never told its own id, so it can't tell "me" from "someone else" |
| Fallback config | loaders log a warning | **missing** on the wire |

---

## 3. Can the browser take control from a running mission?

**Code path:**
- `drive` is refused only by the pilot lock (`not_in_control`). The server
  has **no mode check**, so `drive` is accepted in `auto` and during a
  mission.
- The arbiter puts teleop ahead of every mode.

**Live (measured):**
- Mission in `NAVIGATE_TO_RAMP`, arbiter `active=nav`, wheels at about
  (0.30, 0.6–0.9).
- The client sent `drive (0, 0.8)` at 10 Hz for 3 s.
- **The first frame reached the wheel topic in 1.6 ms.** All 30 frames were
  acked, none refused. The arbiter reported `active=teleop` throughout, and
  the wheels carried (0.00, 0.80).
- On release, the mission resumed: `active=nav` within 0.5 s, and its Nav2
  leg carried on (state stayed `NAVIGATE_TO_RAMP`).

**Preemption works.** It lasts exactly as long as frames keep coming, which is
why a one-shot `stop` is not a stop (§0). Wheel-topic publishers stayed at
exactly 1 (`cmd_vel_arbiter`) in every 5 s sample.

---

## 4. How lab_web will speak coco.v1

- **Binary frames: reuse `coco_web/web/frame.js` unchanged, not a port.**
  - It is a UMD-style file: `module.exports` under Node, `self.cocoFrame` in
    a browser.
  - In the browser, lab_web loads it as a classic-script asset copied from
    `coco_web/web/` at build time. A test checks the built copy is
    byte-identical to the source.
  - Vitest loads it through `createRequire`, the same path
    `frame_decode.test.js` uses.
- **Shared fixtures.** Today `test_frontend_frame.py` writes its fixtures
  to a temp file. They become a committed JSON file
  (`coco_web/test/fixtures/frames.json`), produced by the Python encoder.
  - A coco_web test asserts the committed file still equals what
    `binary.py` produces now.
  - Both `frame_decode.test.js` and a new lab_web vitest read that file.
  - So one decoder and one fixture set are proved in both packages, and
    lab.yml needs no ROS.
- **JSON frames.** TypeScript *types* for `welcome`, `telemetry` and `map`
  (shape only; JSON.parse does the decoding). They are tested against
  golden frames captured from the live server in Part B, so the types
  can't drift from the wire unnoticed.
- **Transport.** A small TS client: hello with `binary: true`, ping/pong
  RTT, 4 s silence watchdog, reconnect. It ports the behaviour of
  `app.js`'s transport, which a real browser has driven.

---

## 5. Proposed design

### 5.1 The Live view

A **Live** tab in lab_web, labelled "Live — local stack" (or "Live — remote
session").

- **Connection bar**: the platform_server URL, default
  `ws://localhost:8080/ws`, shown and editable; connection, health and RTT.
- **Fallback warning**: shown when `welcome.config.source == "fallback"`
  (§5.2).
- **Map canvas**:
  - the occupancy grid and `world` geometry;
  - the belief pose (AMCL), with its covariance ellipse;
  - a **truth toggle** that draws the ground-truth ghost, labelled
    "simulator ground truth — display only";
  - the global plan, the local trajectory and the goal marker.
- **Camera**: binary `camera` stream, 10 fps default.
- **Status strip**: active mode; **which source the arbiter is forwarding**;
  who holds control ("you", "another browser", "nobody", "the mission").
- **STOP**: always visible and fixed in position, in every mode. It
  releases held keys and the stick, as the old page does.
- **Teleop**: an on-screen joystick using pointer events, so it works on a
  phone (no nipplejs; lab_web depends only on React), plus WASD/arrows.
  - A 10 Hz drive loop sends three explicit zeros on release.
  - Blur or hidden tab stops the robot.
- **Nav2**: click the map → `set_mode auto` + `nav_goal`. Shows the plan,
  the local trajectory and the goal status.
- **Autonomous**: colour picker from `limits.colours`, Start and Abort, and
  a 16-step timeline from `mission.step/steps/state/words`, with `reason`
  on failure.
  - Label: *"The mission is told which lane this colour is in
    (`resolve_lane()` / `lane_for_colour()`); discovering the target
    arrives in Phase 5."*
  - Mode buttons are disabled while a mission is active, and the reason is
    shown.
- **Preemption made visible**: when `arbiter.active == "teleop"` while
  `mission.active`, a banner reads "You are overriding the mission"; on
  release it reads "mission resumed".

### 5.2 Additive protocol and telemetry changes, one by one

`protocol.py` changes only by adding. Every item gets its own tests, and a
test that a P0.1-shaped client sees no change in an existing field.

1. **`welcome.you`**: this connection's client id, so `platform.pilot` /
   `control.driver` can be read as "me".
2. **`welcome.config`**: `{source: "coco_config"|"fallback", fallbacks:
   [...]}`, from the three `_load_*` loaders, which record whether they
   fell back.
3. **`robot.belief`**: the raw AMCL pose `{x, y, yaw, cov_xx, cov_yy,
   cov_yawyaw, age_s}`, or null before the first one. `robot.pose` is
   unchanged.
4. **`robot.truth`**: `{x, y, yaw}` in the **map** frame (world →
   map shift `-SPAWN_XY`, the same derivation `world_geometry` uses), from
   a decoded `/model/coco/odometry` throttled to 10 Hz. Null without a
   simulator. The server can turn it off with `truth:=false`.
5. **`nav.local_path`**: from DWB `/local_plan`, through the same
   `path_payload`.
6. **`nav.goal`**: `{x, y, status}` for the browser's last goal. The status
   comes from a read-only subscription to the NavigateToPose action status
   topic.
7. **`nav.path_rx`**: the server's wall-clock time when the current `/plan`
   arrived, for the goal→plan latency measurement.
8. **`platform.control`** (Part C): `{access: "open"|"code", driver,
   spectators, idle_release_s, session_ends_at}`.
9. **New client intents** (Part C): `claim {code}` and `release {}`.
   **New refusal codes**: `spectator`, `bad_code`, `rate_limited`,
   `session_over`.
10. *(Should-have)* an optional `yaw` on `nav_goal`; when absent the
    behaviour is exactly today's.
11. **`stop`** also aborts an active mission (§0). This changes behaviour,
    not schema, so it is listed separately for your decision.

Server-only (not on the wire):
- `remote:=true` builds an app with **only `/ws` and `/healthz`**: no
  static files, `/api/*` or `/video/*`. Camera rides `/ws` as binary
  frames anyway.
- An `origins` allowlist in `check_origin`.

### 5.3 Driver / spectator session model

This sits on the existing sole `Session`. A new pure module,
`coco_web/control.py`, has no rclpy, takes an injected clock, and is fully
unit-tested.

- **`access:=open`** (default, local): today's behaviour, exactly. The
  pilot lock on `drive`; everything else from anyone.
- **`access:=code`** (remote sessions):
  - The host generates a control code per session and prints it in the
    host terminal. It never goes into a URL: Tailscale issue #18651 says
    Funnel strips WebSocket query strings, and URLs end up in logs.
  - `claim {code}` makes that client **the driver**. There is one driver;
    a second claim with the code is refused while the driver is active.
  - Every command intent (`drive`, `set_mode`, `nav_goal`,
    `select_target`, `mission`, `set_arm`, `set_gripper`) from anyone
    else → `spectator`.
  - Spectators keep telemetry, map, camera and lidar.
  - **Idle timeout**: no command intent from the driver for N s (proposed
    60 s) → release control, `stop`, abort an active mission.
  - **Session cap**: proposed 20 min → the same stop, then every client
    gets `session_over` and new connections are refused.
  - **Rate limits** per client: token buckets, proposed drive ≤ 20/s, other
    commands ≤ 2/s, all frames ≤ 60/s → `rate_limited`; sustained abuse
    closes the socket.
  - **Kill switch**: a ROS service on the platform node
    (`/coco_web/kill`, Trigger), called on the host with `docker exec …
    ros2 service call`. It does stop + abort + `idle`, closes every socket
    and refuses new ones. It is **not reachable from the web** at all.
  - **STOP from spectators** in code mode needs your call (§7 Q3).

### 5.4 Ground truth, display only

- The truth reaches **one place**: the telemetry builder (`refresh`).
- Tests:
  1. An AST test over `platform_server.py`: the truth snapshot key is
     written only by its subscription callback and read only by
     `refresh`. No `publish_*` or `call_mission` reads it.
  2. `PUBLISH_ALLOWLIST` and `CALL_ALLOWLIST` are pinned. Adding truth
     adds no channel.
  3. No client frame type can carry a pose except `nav_goal`, which is user
     input.
  4. Live (Part B): the set of topics platform_server publishes equals the
     allowlist.
- **Honest scope.** The mission executive **already subscribes to
  `/model/coco/odometry` itself** for its ground-truth arrival gates
  (C2-NAV.44/45). So the provable invariant is "the web layer adds no path
  from truth to the mission", not "the mission never sees truth". The Live
  view will not claim the stronger statement.

### 5.5 Local mode: the public site and localhost (from vendor docs, to verify in Part B)

- An HTTPS Pages page may open `ws://localhost`: loopback is a
  potentially-trustworthy origin, so this is not mixed content.
- Chromium's **Local Network Access** now covers WebSockets (Chrome 147+),
  so the first connection triggers a "loopback network" permission prompt.
- A **LAN IP** (`ws://192.168…`) from the HTTPS site is blocked as mixed
  content. A phone on the LAN therefore goes through the tunnel, or through
  a locally served lab_web.

---

## 6. Remote-session options (vendor docs read 2026-10-02)

| | Tailscale Funnel | Cloudflare quick tunnel (trycloudflare) | Cloudflare named tunnel |
|---|---|---|---|
| URL | `https://<device>.<tailnet>.ts.net`, stable while the device name is (docs don't promise it). DNS can take up to 10 min the first time | **new random `*.trycloudflare.com` every run** | your own hostname, stable |
| Account | Tailscale account (free plan); visitors need none | **none** | Cloudflare account **and a domain whose DNS is on Cloudflare** |
| WebSocket | works over TLS; known open issue **#18651: query string stripped on WS upgrade** (irrelevant if the code rides inside a frame) | not mentioned in the quick-tunnel docs; Cloudflare says Tunnel "has full support for WebSockets" and drops them when the connector stops; idle WS closed after a period with no data (our 10 s ping keeps it busy) | same |
| Limits | **beta**; ports 443/8443/10000 only; "non-configurable bandwidth limits" (unspecified) | "for testing and development", no uptime guarantee, 200 in-flight requests, no SSE | production service |
| What is exposed | only the target you name (`tailscale funnel <port>`); it shows your tailnet and device name. HTTPS certs for those names are publicly issued, so expect them in CT logs (the docs don't say) | everything at the one `--url` (the whole of :8080) | ingress rules by hostname **and path regex**, mandatory catch-all (`http_status:404`), so `/ws` + `/healthz` only |
| Prereqs here | MagicDNS + HTTPS certs + a `funnel` node attribute in the policy file (admin); client ≥ 1.38.3. **No passwordless sudo on this machine**, so either you install `tailscaled`, or it runs as the official Docker image (you are in the `docker` group) | one static binary or the `cloudflare/cloudflared` image; no root | the same, plus the tunnel token |
| Public-site "is it live?" | fixed URL in the repo works | URL must be published per session | fixed URL works |

**Recommendation: Cloudflare named tunnel if you have, or will add, a domain
on Cloudflare; otherwise Tailscale Funnel.**
- **Named tunnel.** Stable URL. Path-level ingress means the tunnel itself
  exposes only `/ws` and `/healthz`, on top of `remote:=true`. Not beta.
  cloudflared runs as a sidecar container on the compose network, so
  nothing on the host is published.
- **Funnel.** Free, stable URL, no domain. Beta, unspecified bandwidth
  limits, and the hostname shows your tailnet name. It runs as a
  `tailscale/tailscale` sidecar.
- **Not quick tunnels** for the scheduled sessions: the URL changes every
  run, so the site's "is it live?" check would need a commit per session.
  They're fine for a one-off rehearsal.

Either way, the sidecar reaches only the `coco` service's port 8080. The
container already publishes nothing but 8080, the platform runs
`remote:=true`, and Part C verifies from outside (phone on mobile data) that
other ports and paths are unreachable.

---

## 7. Decisions needed before Part B

- **Q1 (safety, §0).** Should the server's `stop` also call
  `/mission/abort` when a mission is active? Recommended. The alternative
  is a new `estop` intent, which leaves the old page's STOP still unsafe.
- **Q2 (Nav2 mode, §1).** Recommended: make the executive assert
  `/mission/mode` only while a mission runs, publishing `idle` once on
  entering IDLE, COMPLETE or ABORT, and then falling silent, so the
  browser's mode holds. This changes `coco_mission`.
  - Alternatives: run Live with `executive:=false` (breaks autonomous
    mode); or have the platform re-assert the browser's mode (two 2 Hz
    publishers fighting over a latched topic, rejected).
- **Q3 (code mode).** May spectators press STOP? Today anyone may, by
  design ("the person who can see the robot…"). On the public internet that
  hands every viewer a grief button. Recommended: in `access:=code`, STOP
  from the driver and from loopback (the host) only; spectators get
  `spectator`.
- **Q4.** Which tunnel (§6).
