# Phase 2 · Part B — the Live view, local only (2026-10-02)

**What it is.** lab_web's **Live** tab (`?view=live`), speaking coco.v1 to a
`platform_server` URL. The default is `ws://localhost:8080/ws`; the URL is
shown and editable, and `?live=` presets it.

**Code:**
- server additions: 4c24765;
- the tab: 2fef55b;
- safety fixes, on `main` since 54133fe: `docs/live/SAFETY_FIXES.md`.

**Evidence:** `docs/data/live/part_b/` (gunzip `*.gz` first).

**How the runs were driven.** Headless Firefox 157 drove the shipped build
over WebDriver BiDi (`scripts/live_check/`), with real key presses and
pointer clicks. A ROS recorder ran alongside, and each run used a fresh
simulator (`mission.launch.py`, headless, domain 62, quiet machine).

**Latency clock.** The page stamps each frame as it leaves
(`performance.timeOrigin + now`); the recorder stamps arrival on the
wheel topic with `time.time()`. Same machine; the browser's two clocks
agreed within 2 ms.

Every number is **(measured)**. Three fetches are not a rate.

## Measured

| measure | result | run |
|---|---|---|
| `drive` frame leaving the browser → arbiter output on `/diff_drive_controller/cmd_vel` | **n = 170: min 0.7, p50 4.6, p90 6.2, p99 7.7, max 9.7 ms** | `b_teleop_nav` |
| key press (first frame) → first wheel command | n = 41: min 2.8, p50 4.4, p90 6.1, max 7.2 ms | `b_teleop_nav` |
| STOP clicked with W held → wheel zero | 6.2 ms; 0 moving commands from +0.2 s to +3.3 s; latched banner shown | `b_teleop_nav` |
| `nav_goal` leaving the browser → first `/plan` | n = 7: min 6.2, p50 8.6, p90 13.2, max 15.8 ms | `b_teleop_nav` |
| Nav2 goals clicked on the map | **7 / 7 `succeeded`** (Nav2's status); ground-truth end error 0.052–0.296 m | `b_teleop_nav` |
| telemetry received by the page | 10.0 Hz in all 4 runs; gaps p50 100, p99 107, max 131 ms (n = 1876) | all |
| teleop preempts a running mission (blue, Nav2 leg, A held 2.5 s) | first turn frame → wheels 3.5 ms; 50 wheel commands carried it; override banner after 0.52 s; on release Nav2 drove again, still `NAVIGATE_TO_RAMP` | `b_fetch_blue` |
| wheel-topic publishers | 1 (`cmd_vel_arbiter`) in every 5 s sample of every run | all |

### Autonomous fetches from the page

Colour pick, then Start, from the page.

| colour | outcome | Start → terminal (wall) | recoveries | relocalisations |
|---|---|---|---|---|
| blue (preempted) | **COMPLETE**, `result=fetch` | 221.8 s | 1 (RETURN_HOME) | 1 |
| green | **COMPLETE**, `result=fetch` | 204.6 s | 1 (RETURN_HOME) | 1 |
| yellow | **COMPLETE**, `result=fetch` | 215.0 s | 0 | 0 |

Both recoveries were `LOCALIZATION_DEGRADED` on the return leg, recovered
by RELOCALIZE. The two RELOCALIZE runs completed; that is not attributed.

### Notes on the numbers

- **Goal → plan includes the walk to the planner.** It runs from the frame
  leaving the browser, through the server, `/goal_pose` and bt_navigator,
  to planner_server's `/plan`. The goals' shortest plans dominate.
- **Goal 1's 0.296 m truth error is outside Nav2's 0.25 m tolerance.**
  Nav2 measures that tolerance on AMCL's pose, not on truth. The 0.30 m is
  reported, not explained.

## Invariants

| invariant | how it is checked | result |
|---|---|---|
| exactly one wheel publisher | live, every run (recorder, 5 s samples) | 1 throughout |
| the platform publishes only the allowlist | live `ros2 node info /coco_web_platform` | 6 allowlist topics + `/rosout`, `/parameter_events`; clients = the 3 `CALL_ALLOWLIST` services |
| the browser never names a topic | `lab_web/test/live.test.ts`: every quoted ROS name in `platform_server.py` / `safety.py` is a needle, and no Live source contains one; coco_web's frame-leak test (existing); intents checked against coco.v1's own schema | pass |
| protocol changes additive only | `coco_web/test/test_additive.py` freezes coco.v1 at 54133fe (types, fields, modes, refusal codes, welcome and telemetry keys) | pass |
| ground truth never reaches the mission through the web layer | `coco_web/test/test_truth_display_only.py`: one writer (`_on_truth`), one reader (`refresh`), no command path names it, allowlists exclude it | pass. **Scope:** the executive reads `/model/coco/odometry` itself (pre-existing, C2-NAV.44/45) |
| one decoder | lab_web loads `coco_web/web/frame.js` itself; `check_dist.mjs` checks `dist/coco/frame.js` is byte-identical; both suites decode `coco_web/test/fixtures/frames.json` | pass |

**Phone layout** (390 × 844, `fakestack.py`, no simulator):
- STOP is full-width at the bottom and is the topmost element at its own
  centre;
- no horizontal scroll (378 ≤ 390);
- the joystick is reachable.

## Honest labels, as rendered (end of each fetch)

- **Badge:** `Live — local stack`.
- **Autonomous:** "the mission is told which lane this colour is in
  (resolve_lane() / lane_for_colour()). It does not search for the
  target; discovering it arrives in Phase 5."
- **Fallback banner:** absent in every run, because `welcome.config` said
  `coco_config`. Its wording is pinned in a test.
- **"Not localised yet: the pose is odometry only":** shown only while
  `localised` is false. That was 0.0 s in these runs (startup pose plus
  the no-motion update).

## Tests

All 11 packages pass via `run_all_package_tests.sh` (test venv), **2512**
in total. lab_web vitest: 194.

| package | before | after |
|---|---|---|
| coco_web | 582 | 688 |
| coco_mission | 338 | 344 |
| coco_rl | 231 | 231 (one mapping: `action_msgs` comes with rclpy) |

## Not done / unverified

- **Docker.** Part B ran natively; the image has the Part B server code
  only from Part C's rebuild.
- **The camera stream's on-page frame rate** was not measured.
- **A physical touchscreen joystick drag** has not been done; only
  pointer and keyboard input in Firefox headless. Part C's phone session
  is the first.
- **The public site.** It cannot reach a local stack except from the same
  machine: Chromium's Local Network Access prompt and `ws://` mixed-content
  rules, per vendor docs, not verified here.

---

**Note added 2026-10-08 (COCO Lab v2, M0 fix A.2; the text above is
unchanged).** The tab no longer connects to its default endpoint on load.
It contacts a stack only when asked (Connect, Watch, or a `?live=` link),
asks that host's `/healthz` first, and opens the WebSocket only after an
answer. `scripts/live_check/run_b.sh` now passes
`&live=ws://localhost:8080/ws` for that reason. See
`docs/v2/data/m0/exit/console_after_fix.json`.
