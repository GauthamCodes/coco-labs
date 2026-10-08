# CLAUDE.md — rules and sections retired at COCO Lab v2 (2026-10-08)

Moved here verbatim from `CLAUDE.md` at `coco-lab-v1-final` (`3571169`)
during M0.4, when `README.md` (the v2 master plan) became the authority.
Kept as history: each was true when written. Why each was retired:

| Retired | Why | Replaced by |
|---|---|---|
| "State first — START HERE" | `PROJECT_STATE.md` is no longer the first authority | `CLAUDE.md` "Authority — START HERE": `README.md`, then `docs/STATUS.md` |
| "Read first" (the v1 reading list) | the read order is set by README §9 | same section of `CLAUDE.md` |
| Rule 8's per-branch test counts and breakdowns (829 … 1877) | stale numbers from branches that are not `main`; the rule itself is kept | "Current counts" under rule 8, and `docs/STATUS.md` |
| "COCO Lab direction": the plan/prompt pointers, platform rule 8, platform rule 9 | the v1 roadmap and prompts are archived; rule 8 is replaced by the trace-equivalence invariant (README §3); rule 9 is replaced by v2's milestones (README §7) | `CLAUDE.md` "COCO Lab platform rules" and "The replaced invariant" |

---

## From the top of CLAUDE.md

## State first — START HERE

**`PROJECT_STATE.md`** (repo root) is the authoritative snapshot: what is
done, what is broken, what was measured, and the known limitations.

**COCO 2.0 is frozen.** Everything is on `main` — one branch, complete.
The development-era split, where implementation lived on a feature branch
and the state files on the trunk, is over; `docs/STATE_PROTOCOL.md`
records how that worked and is kept as history, not as a live rule. A
fresh clone of `main` is sufficient. **A missing package now means a
build problem, not an unmerged branch.**


## Read first

`README.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN_DECISIONS.md`,
`docs/RESULTS.md`, `docs/FUTURE_WORK.md`, `docs/M7_DESIGN.md`,
`docs/SESSION_LOG.md`.

They are long. Read them anyway. Most of what you need to avoid is already
written down, usually with the cost of learning it attached.


## From rule 8, "Tests are green or the phase is not done"

**On `p03c-episode-gazebo` it is 1877, 0 failing, 0 skipped**, against
**1740** measured on its base `b3c6598` in the same session: coco_config
70 → 92, coco_rl 218 → 229, gazebo_models 206 → 219, coco_sim 128 → 199,
coco_mission 317 → 337; custom_teleop 75, coco_perception 139,
coco_moveit_config 12, coco_web 575 unchanged.

**Release baseline: 829 passing, 0 failing, 0 skipped.** On
`p02-release-candidate` it is **1667** (breakdowns below). On
`p02-browser-experience` it was **1334** (C2-NAV.49's 1004, plus 135 from P0.1, plus 195 from
P0.2). `gazebo_models` carried most of the earlier growth — 41 on the
release tree, **181** here — and `coco_web` carries all of the latest:
**297**, from nothing two releases ago. Measured on the
release tree, per package, **with cwd set to the package directory**, on
a clean ROS graph:

| package | tests |
|---|---|
| `coco_config` | 70 |
| `custom_teleop` | 67 |
| `coco_rl` | 164 |
| `coco_perception` | 139 |
| `gazebo_models` | 41 |
| `coco_moveit_config` | 12 |
| `coco_sim` | 55 |
| `coco_mission` | 281 |
| **total** | **829** |

`coco_web` used to have no `test/` directory — pytest exited 4 there,
which was recorded here as "not a failure". **That is no longer true.**
P0.1 gave it 116 tests and, for the first time, the flake8/pep257/
copyright linters: expect **116** from `coco_web`, and note that adding
the linters is what surfaced the pre-existing docstring failures in
`web.launch.py`.

**1607 -> 1667 breakdown (P0.2 release pass, `p02-release-candidate`).**
`coco_web` 517 -> 575 (stored lifecycle + server-level lifecycle walk,
slow-client/flood/per-client-drop/close-path/padded-row tests on real
sockets, the MJPEG proxy and parser, timing provenance, keepalive, the
leak test's harvested needles, the Node decoder test, the loopback bind),
`coco_rl` 216 -> 218 (8080-only compose and `EXPOSE`, `frame.js` ships).
Nothing else moved. Measured per package on `~/coco_ws_build`, 0 failed,
0 skipped, **on a quiet machine**.


**1564 -> 1607 breakdown (`coco-clean-runtime`).** `gazebo_models`
181 -> 206 (`test_no_turtlebot_dependency.py`: no TurtleBot edge in any
package.xml, launch file, build file or YAML value; every launch lookup
declared; the dangling-marker mechanism against the real ros_gz_sim),
`coco_rl` 198 -> 216 (`test_setup_env.py`: `setup_env.sh` in a clean
bash). Measured on `~/coco_ws_build`, 0 failed, 0 skipped. Nothing else
moved.

**1334 -> 1564 breakdown (P0.2, second pass).** `coco_web` 297 -> 517
(health axis, real-socket server tests, map-frame pose, launch/asset
checks, and Codex's integrated hardening: protocol, streams, binary,
imaging, mission, lifecycle, transport), `coco_rl` 190 -> 198 (Docker
static checks, the entrypoint-children test), `coco_mission` 315 -> 317
(`expected_components` evaluated for `executive:=true/false`). Nothing
else moved.

**1139 -> 1334 breakdown (P0.2).** `coco_web` 116 -> 297 (mission
translation, subscriptions, binary frames, imaging, metrics, web
assets), `coco_rl` 179 -> 190 (the bring-up scripts, beside the Docker
context checks), `gazebo_models` 178 -> 181 (the `platform_serve[r]`
sweep pattern). Nothing else moved.

**1004 -> 1139 breakdown (P0.1).** `coco_web` 0 -> 116, `coco_mission`
311 -> 315 (the `platform:=` web-layer selection), `coco_rl` 164 -> 179
(the Docker build-context guards). Nothing else moved.


## The COCO Lab direction section, as it stood

## COCO Lab direction (added 2026-09-28)

COCO is becoming COCO Lab (working title): an interactive, browser-based
robotics curriculum running on this ROS 2 stack. Plan: docs/ROADMAP.md.
Session prompts: docs/LAB_PHASES.md. The master context lives outside
this repository (no copy is checked in); its §45 priority order is
superseded, and everything else in it still holds.

Platform rules, in addition to everything above:
1. coco_lab never imports rclpy. A test enforces it.
2. The browser never names a topic, and never commands the robot except
   through coco.v1 intents added additively.
3. No new wheel publisher. Lab planners move the robot only via Nav2
   FollowPath, through the existing command chain into cmd_vel_arbiter.
4. Every mode is labelled on screen: Replay (recorded real run,
   provenance shown), Sketch (browser model, measured fidelity shown),
   Live (local stack).
5. Every claim shown to a learner is backed by a property test or a
   (measured) result, and cites it. Theorems are tested as properties,
   not asserted.
6. Comparisons hold inputs fixed: map, start, goal, recording, seed.
7. Trace and bundle schemas are versioned; breaking changes bump the
   major version.
8. The TypeScript UI never re-implements an algorithm. It renders traces
   and asks coco_lab.
9. No new lab starts until the previous one has a public URL, a video and
   a write-up. A lab's first version ships at most five algorithms.
10. Live control is exclusive and interruptible: one driver holds control
    at a time; teleop preempts autonomy, as the arbiter already
    guarantees; stop is always one tap away; remote sessions expose only
    the coco.v1 endpoint.
