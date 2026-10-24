# Fetch Rush rules 5 — the actors stop for COCO, AUTO reacts (evidence)

Evidence class: **MODEL** (the Python reference model and the browser running it). Branch
`v2/g2-actor-yield`, from `c695cd5`. The **Gazebo stack's actors still never yield**: Race Nav2's
recorded ghosts (STACK) ran with the Gazebo actors parked, and Gazebo's actors are scripted
schedules. Any model-vs-STACK comparison under rules 5 compares a yielding model with a stack
whose actors do not yield.

## The report

Gautham, 2026-10-24: "there is no dynamic path or the fixed path in auto mode is not changing
when the forklift arrives; the robot just stays still and the forklift moves forward phasing
through the robot."

## The mechanism (rules 1–4, found in the code and reproduced)

- AUTO sends one `goal`; the Arena plans **once** on the static inflated grid
  (`arena.py` `_plan_begin`/`_plan_finish`; the grid has no actors), and the waypoint follower
  (`sketch.drive_command`) drives it. Nothing re-plans when the way is blocked.
- An actor's pose is a **pure function of time** (`worldspec_v3.actor_pose`). The Arena refuses a
  robot step that would enter an actor's covering discs (`arena.py` `finish_step`), but nothing
  ever checks an actor moving onto the robot. Once a disc covers COCO, every step is refused
  (COCO "stays still", `v = w = 0`) and the forklift drives on through it.
- Reproduced (`scenarios.json`, rules 4 rows): COCO parked in the east–west lane is overrun
  (38 overlap ticks in 40 s, clearance −0.22 m: the box over COCO's centre); AUTO head-on in the
  lane, along a walker's path and across it: 19, 38 and 6 overlap ticks.

## What changed (rules 5; rules 1–4 untouched)

1. **`actors.yield=1`** (`games.DepotActors`): each actor keeps its own clock — the ticks it has
   held (`lag`) — and in `world_step` holds while its box at the next pose would be within
   COCO's radius + **`ACTOR_STOP_MARGIN` = 0.3 m** of COCO's centre *and* closer than now (COCO
   ahead of it, in its direction of travel). Sideways or away, it goes on. 0.3 m: a forklift's
   protective field, just over the 0.25 m its discs over-cover its ends. By induction no actor can
   overlap COCO: COCO's own steps are refused at the discs (which cover the box), and an actor
   never takes a step that brings it closer inside the field. The discs, the LiDAR, the clearance,
   the HUD's actor poses (the glue's game block) and the predictors (`_conflict`,
   `_crossing_delay`) read the actual poses. The state (`lag`, `held`) exists only when configured.
2. **`avoid.on=1`** (`games.ActorAvoid`, a new lazily created subsystem; the Arena gains no
   attribute): while a goal is driven, before the waypoint follower —
   - a **moving** actor within the path's 4 s look-ahead (2 × radius margin, the reference bots'
     rule): AUTO **holds** and waits; after 3 s it re-plans once around the actor's box and takes
     the route only if it is clear; after 10 s it **goes on** (the actors stop for it) with a 1 s,
     0.1 m check;
   - an actor **stopped for COCO** (held now or in the last 1 s) gives COCO the **right of way**:
     AUTO drives on; if the path's next 1.5 m would run into it, it re-plans around its box at once
     (or backs away at 0.15 m/s for at most 2 s if there is no detour). This is what breaks the
     "actor waits for COCO, COCO waits for the actor" deadlock deterministically.
   - a re-plan is **one search** (the Arena's planner) on a copy of the plan grid with the actor's
     discs blocked (radius + disc + 0.1 m); it sets the Arena's waypoints (the plan grid is never
     replaced), at most once per 20 ticks.
3. **Versioning:** `games.setup_inputs` appends `actors.yield=1`, `avoid.on=1` only for Fetch Rush
   rules ≥ 5 (and for Free Drive on a v3 level, which goes through the same setup);
   `FETCH_RUSH_RULES = 5` (Python and TS); bests key `…r5-{mode}…`; the browser draws the model's
   actual actor poses (it already drew the glue's poses, never its own schedule) and AUTO's re-planned
   route; /rosout lines and toasts for "holding", "re-planned", "stopped for COCO".

## Numbers

**Old rules unchanged.** `tools/g1/make_v3_goldens.py --check`: both files identical.
`tools/m6/make_game_references.py --check`: all four (rules 1 and Rush Hour) reproduce. Every
committed reference record replays to its committed card and hash chain: rules 2 (4 of 4 with a
record), rules 3 (12 of 12), rules 4 (12 of 12) — `tools/g2/replay_references.py`,
[`replay_references_r2_r3_r4.log`](replay_references_r2_r3_r4.log); the rules-5 references:
[`replay_references_r5.log`](replay_references_r5.log).

**Scenarios** ([`scenarios.json`](scenarios.json), `tools/g2/rules5_scenarios.py`, CPython 3.12,
hash v3; step times are wall clock on the shared laptop):

| Scenario | Rules 4: overlap ticks / refused ticks / min clearance | Rules 5: overlap / refused / min clearance | Rules 5: arrived (rules 4) |
|---|---|---|---|
| COCO parked in the lane, 40 s | 38 / 44 / −0.22 m | 0 / 0 / 0.43 m (forklift held 320 ticks) | — |
| AUTO across the lane, start t = 0 | 0 / 17 / 0.06 m | 0 / 0 / 0.47 m | 23.7 s (22.4 s) |
| AUTO across the lane, t = 4, 10, 15 s | 0 / 0 | 0 / 0 (no actor in the way) | 20.7 s (20.7 s) |
| AUTO head-on in the lane | 19 / 22 / −0.22 m | 0 / 0 / 0.195 m (1 re-plan) | 31.5 s (21.9 s) |
| AUTO along a walker's path | 38 / 48 / −0.22 m | 0 / 0 / 0.216 m (1 re-plan) | 31.9 s (27.3 s) |
| AUTO across a walker's path | 6 / 6 / −0.04 m | 0 / 0 / 0.41 m | 21.5 s (15.3 s) |

Worst step under rules 5 in these runs: **87.4 ms** (rules 4: 84.3 ms); the re-plans (one search
each) took 16.3–41.9 ms. A re-plan's cost grows with the route's length (one search, as AUTO's own).

**Browser** ([`forklift_check_after.json`](forklift_check_after.json),
[`forklift_check_before.json`](forklift_check_before.json); `lab_web/tools/g2/forklift_check.mjs`,
headless Chromium on the RTX 4050, Fetch Rush Full shift seed 2: cross the lane by the dock
walker, park in the lane, drive on past the forklift; overlap = box distance from COCO's centre
< 0.22 m):

| Build | Ticks | Overlap ticks | Blocked ticks | Min clearance | Actor held for COCO |
|---|---|---|---|---|---|
| before (`c695cd5`, rules 4) | 1457 | **114** | 133 | −0.22 m | — |
| after (rules 5) | 1233 | **0** | 0 | 0.105 m | 380 ticks; every leg arrived |

Screenshots (desktop): [`../../screens/rules5/`](../../screens/rules5/) — the first tick the
forklift stops for COCO (chase and tactical cameras).

**Rounds** (`coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r5.json`,
`tools/g2/make_fetch_rush_rounds_r4.py --rules 5`, 3660 s): rules 4's draw, budgets and crossing
rule; every round (start zone, orders, attempt) equals rules 4's, with the same draws rejected. The
reference bot plays under rules 5 and sends no STOPs of its own (the model yields). Reference times
equal rules 4's except Full shifts 2 and 4: 388.3 s (timer 582.5 s) against 387.8 s (581.7 s).
**Phone timers are unchanged**: 4 distinct rounds, 275.9–349.1 s (4:35.9–5:49.1) — the ≤ 6:00
rule holds at 26 m; no budget meets ≤ 5:00, as under rules 4. Every reference: 0 contacts. Race
Nav2's index lists the rules-5 seeds for the same recordings (same rounds).

**AUTO-only player** ([`auto_player_phone.jsonl`](auto_player_phone.jsonl),
`tools/g2/auto_player_r5.py`: AUTO, GRAB, DROP through the browser's glue), phone seeds 1, 2, 3 and
6 (the four distinct rounds), rules 4 and rules 5: the same result under both — 2 deliveries,
0 contacts, 198.0–244.4 s used, closest actor 1.82–2.25 m: AUTO's own routes in the phone rounds
do not meet an actor (the encounters come when COCO is driven or sent into or across a lane).

## Open

- The actors yield only in the model; Gazebo's actors (STACK) do not.
- With no detour and no room to back off, AUTO holds and the actor stays held (COCO is in its
  field); the player can drive away. Not met in any run here.
- COCO parked in a lane by the player keeps the forklift stopped as long as it stays (a safety stop).
