# Phase 2 · Part C — driver, spectators, remote sessions (2026-10-02, IN PROGRESS)

Branch `live`. Evidence: `docs/data/live/part_c/` (gunzip `*.gz` first).
Harness: `docs/data/live/part_c/scripts/`.

Every number is **(measured)** unless marked. One run is not a rate.

## Status by subsection

| part | status |
|---|---|
| precondition | holds: Part A, safety fixes on main (`labs/main` = 54133fe), Part B, its invariants; CI **and** Lab green on 74ab139 (GitHub, pull_request runs; the Part B log entry did not record this) |
| C1 Docker fetch | **done: 1/1 COMPLETE** |
| C2 session model | in progress |
| C3 tunnel | **blocked: tunnel choice still open** (Part A §7 Q4 never answered; SESSION_LOG says the reply left a placeholder) |
| C4 exposure check | not started |
| C5 public status | not started |
| C6 remote session | not started (needs the owner, on a phone, on mobile data) |
| C7 final verification | not started |

## C1 — Docker autonomous fetch (measured)

| item | value |
|---|---|
| image | `coco-platform:jazzy` 48544a3ddbf3, built from `live` 74ab139 (`docker_build.sh`), tornado 6.5.7, navigation2 1.3.13-1noble.20260905 |
| base | `osrf/ros:jazzy-desktop` **by tag, not digest** (no local tag/digest resolvable after the build) |
| container | fresh: `docker compose up -d`, no container existed before, no Gazebo running, load ≈ 1.1 |
| healthy | 15.6 s after `up` (wall, 5 s poll) |
| colour | **red** (`select_target red` over coco.v1; executive: "starting the fetch for red", ramp_driver datum lane −6.00) |
| outcome | **COMPLETE, `result=fetch`**, all 16 states in order |
| Start → terminal | 259.5 s wall (the executive's `elapsed` is per state; a total sim-time duration is not instrumented) |
| localised after connect | 0.11 s |
| recoveries / relocalisations | 0 / 0 |
| collision monitor | 0 PolygonStop actions (PolygonLimit / PolygonSlow only) |
| wheel publishers | 1 (`cmd_vel_arbiter`) in every 5 s sample |
| teardown | `docker compose down`: 0 containers, 0 Gazebo |

Reproduce (from this worktree; Docker group; nothing else simulating):

```bash
git archive -o /tmp/head.tar HEAD && mkdir -p /tmp/head && tar -xf /tmp/head.tar -C /tmp/head
bash docs/data/live/part_c/scripts/docker_build.sh /tmp/head
bash docs/data/live/part_c/scripts/docker_run.sh docs/data/live/part_c/c1_fetch_red fetch red
python3 docs/data/live/part_c/scripts/an_fetch.py docs/data/live/part_c/c1_fetch_red   # after gunzip
```
