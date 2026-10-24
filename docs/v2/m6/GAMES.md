# Fetch Rush and Rush Hour — the rules, model side (M6F.6)

README §5.9, integrity rule 4, invariant 13. Code `coco_lab/coco_lab/games.py`; tests
`coco_lab/test/test_games.py`; reference results `docs/v2/m6/data/games_reference.json`
(made by `tools/m6/make_game_references.py`, which `--check` replays). Evidence class
MODEL. No UI: HUDs, the ghosts drawn in 3D and the browser's `coco verify` wiring are M6
UI-phase work.

## What a game is

A game is a pure function of **the World Spec, the seed and the input log**
(`games.play`). The rules observe the Arena's ticks; they add nothing to the model's
state, so the per-tick hash chain of a game is the Arena's own (tested). Every session
starts with the same tick-0 inputs (`games.setup_inputs`): `actors.on=1` (the Depot's
forklifts and walkers as collision bodies), `assist.target=any` (Grasp Assist), and
for Rush Hour a `kidnap` to the objective's start. `games.verify(spec, record, claim)`
validates the input log with M5's link limits (`coco_lab.link_bounds`: at most 1,960
inputs, ticks ordered, the first by tick 500, at most 11,930 ticks) **before** building
an Arena, then replays and compares every number.

## The actors in the model

`DepotActors` (the Arena subsystem `actors`): each forklift or walker is a set of discs
covering its box at its kinematic pose (`worldspec_v3.actor_pose`), so the LiDAR sees it
and the robot cannot drive into it. SIMPLIFIED: the discs over-cover a forklift's long
sides by up to 0.25 m; clearance in the rules is measured to the exact box. Actors
never yield: they are a schedule, the same schedule `actors.json` gives Gazebo (Rules 1–4;
under Fetch Rush rules 5 the model's actors stop for COCO: see the end of this file.)

## Fetch Rush

- **Orders:** one at a time, drawn from the game's own seeded generator
  (`coco_lab.rng`): a shuffle of the objects Grasp Assist can pick somewhere on the level
  (10 on the Depot), each paired with a drop zone (4 on the Depot). Same seed, same
  orders, for every player.
- **Delivered:** the order's object is put down inside its drop zone.
- **Timer:** 180 s (README: three minutes).
- **Path efficiency against the planner ghost:** for each delivered order, the ghost's
  length (A* from where the robot stood when the order appeared to the object's best
  pre-grasp pose, plus A* from there to the drop zone's centre) divided by the distance
  the robot drove.
- **Contacts:** a tick the model refused the robot's motion (a wall or an actor), or the
  robot's circle overlapping an actor's box; one per episode, each logged with its time,
  place and whether an actor was involved.
- **Ranking:** net deliveries (deliveries − contacts: contacts subtract), then less time
  used, then higher path efficiency. No weights, no luck: every term is a real metric.

## Rush Hour

- **Objective** `aisle_to_dispatch`: pick the canister `obj_aisle_1` in high-bay aisle 1
  with Grasp Assist and deliver it to the Dispatch drop zone, across the east–west
  forklift lane and past the walker crossing.
- **Metrics:** delivered; time from start to delivery; minimum clearance between the
  robot's circle and any actor's box over the run; contacts (as above); the **fragile
  cargo rule**: RMS and peak jerk of the robot's linear motion while the canister is
  carried, `j = (a_k − a_{k−1}) / dt`, `a_k = (v_k − v_{k−1}) / dt`. **A game rule about
  how the robot is driven, not physics** (invariant 13): nothing breaks in the model, and
  the scorecard says so (`"fragile_cargo": "game rule, not physics"`). The driving assist
  in use (`move.controller`, or `builtin`) is on the scorecard.

## Stars come from the reference, never hand-picked

`games.stars(card, reference)` against the reference bot's card for the same level and
seed:

- Fetch Rush: ★ one delivery; ★★ net deliveries ≥ the reference's; ★★★ ranking at or above
  the reference.
- Rush Hour: ★ delivered; ★★ delivered with no contact, no slower than the reference;
  ★★★ also a minimum clearance ≥ the reference's and an RMS jerk ≤ the reference's.

## The reference bots and their results

`bot_fetch_rush` and `bot_rush_hour`: the planner (A*, the Arena's waypoint follower)
plus Grasp Assist, closed-loop, recording the input log they send. Both yield to actors:
before and while driving a leg they predict the path 4 s ahead at the auto speed against
the actors' known schedule and STOP when it would come within a robot diameter
(2 × 0.22 m) of an actor's box, re-planning when clear. Rush Hour's bot waits at a staging
point beside the lane for the earliest such window, then crosses.

Results, 2026-10-17, Depot `coco_depot_v1`, Arena seed 1 (CPython 3.12.3, nice 19, Codex
running, load average 1.7 at the end; the bots' wall times in the JSON are not
benchmarks):

| Run | Deliveries / delivered | Contacts | Time | Path efficiency | Min clearance | Jerk RMS / peak (m/s³) | Ticks, inputs |
|---|---|---|---|---|---|---|---|
| Fetch Rush seed 1 | 1 (obj_dock → Dock 2) | 0 | 136.7 s used | 0.987 | — | — | 1,801, 12 |
| Fetch Rush seed 2 | 1 (obj_dock → Dock 2) | 0 | 136.7 s used | 0.987 | — | — | 1,801, 8 |
| Fetch Rush seed 3 | 0 | 0 | 180 s (timed out) | — | — | — | 1,801, 6 |
| Rush Hour `aisle_to_dispatch` | delivered | 0 | 102.2 s | — | 0.573 m | 3.95 / 39.98 | 1,023, 9 |

So the thresholds for those seeds are: Fetch Rush seeds 1 and 2 — ★★ at 1 net delivery,
★★★ at 1 net delivery in ≤ 136.7 s (then path efficiency ≥ 0.987 on a tie); seed 3 —
★ at one delivery, ★★★ at one net delivery. Rush Hour — ★★ at a contact-free delivery in
≤ 102.2 s, ★★★ also with clearance ≥ 0.573 m and RMS jerk ≤ 3.95 m/s³.

**Found, and left visible:** at COCO's real autonomous speed (0.3 m/s, Nav2's FollowPath
limit, integrity rule 4) the Depot is large for a three-minute game. Seed 3's first order
(office SW → Dispatch) has a 77.9 m planner ghost, about 260 s at 0.3 m/s, so even the
reference cannot deliver it in time. Seeds 1 and 2 happen to draw the same first order.
Whether to lengthen the timer, draw orders within a reachable budget, or start Fetch Rush
in a zone is a game-design question for Gautham (in `PARALLEL_STATUS.md`). A person
driving at the teleop limit (0.5 m/s) can beat the reference.

## Fetch Rush rules 2 (G1.11, Gautham's 2026-10-18 decision)

Implemented 2026-10-21 in G1.11; rules 1 above are unchanged and still verify (a record
without `rules` is rules 1). Code: `games.draw_round`, `games.FetchRushRound`,
`games.round_for`; data: `coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.json`, made by
`tools/g1/make_fetch_rush_rounds.py` (Arena hash v3, CPython 3.12, cloud container);
tests `coco_lab/test/test_fetch_rush_rounds.py`.

- **A round starts inside one zone.** The start zone is drawn (seeded) among the Depot's
  regions from which a full round fits the budget, minus the forklift lanes (a start
  there is inside an actor's path at tick 0); COCO starts at the plan grid's free cell
  nearest the zone's centre (a `kidnap` in the record's tick-0 inputs).
- **Each order's planned round trip fits a budget**, **32 m**: from where the
  order begins (the start, then the previous order's drop zone) to the object's best
  pre-grasp pose, then to the drop zone's centre — M6F.6's ghost, measured from the
  order's start. Orders use distinct objects; each is drawn among those that fit and
  still let the round finish. **3 orders.** 32 m is the smallest budget that
  gives 3-order rounds on the Depot: only two objects (`obj_dock`, `obj_dispatch`) lie
  close to a drop zone, so every round's third order is about 32 m.
- **Timer = the reference bot's time for the 3 deliveries × 1.5.** The bot
  (planner + Grasp Assist, yielding to actors) plays the round first with time to spare;
  its time for the last delivery × 1.5, rounded to 0.1 s, is the round's timer, and its
  run under that timer is the stars' reference.
- **Nothing is planned while a game runs.** The orders, each order's ghost length and its
  route (for drawing) come from the file; `FetchRushRound` never calls the planner
  (tested: a 40-tick round with the planner functions replaced by failures).

| Seed | Start zone | Orders (planned round trip) | Reference bot | Timer |
|---|---|---|---|---|
| 1 | Loading dock | obj_dock → Dock 1 (16.0 m), obj_dispatch → Dispatch (21.4 m), obj_maze_2 → Dispatch (31.9 m) | 327.8 s, 0 contacts, path efficiency 0.988 | **491.7 s** (8:11) |
| 2 | High-bay aisles | obj_dispatch → Dispatch (23.4 m), obj_maze_2 → Dispatch (31.9 m), obj_dock → Dock 3 (31.8 m) | **did not finish**: 0 delivered, 214 contacts (stopped in the forklift lane) | — (not offered) |
| 3 | Loading dock | obj_dock → Dock 2 (13.3 m), obj_dispatch → Dispatch (24.9 m), obj_maze_2 → Dispatch (31.9 m) | 330.5 s, 0 contacts, path efficiency 0.989 | **495.8 s** (8:15) |
| 4 | High-bay aisles | obj_dispatch → Dispatch (23.4 m), obj_maze_2 → Dispatch (31.9 m), obj_dock → Dock 3 (31.8 m) | **did not finish**: 0 delivered, 214 contacts (stopped in the forklift lane) | — (not offered) |
| 5 | High-bay aisles | obj_aisle_1 → Dock 1 (31.6 m), obj_dock → Dock 1 (21.0 m), obj_dispatch → Dock 2 (30.8 m) | 384.8 s, 1 contacts, path efficiency 0.988 | **577.2 s** (9:37) |
| 6 | Loading dock | obj_dock → Dock 3 (11.9 m), obj_dispatch → Dispatch (28.4 m), obj_maze_2 → Dispatch (31.9 m) | 337.7 s, 0 contacts, path efficiency 0.993 | **506.5 s** (8:26) |

At COCO's real autonomous speed (0.3 m/s, integrity rule 4) three budgeted orders take the
reference 328–385 s, so the decision's formula gives timers of **8:11 to 9:37** (491.7–577.2 s), not three
minutes. Seeds 2 and 4 drew the same round, whose first leg crosses the east–west forklift
lane; M6F.6's reference bot stopped inside the lane and was hit repeatedly, so that round
has no reference time and no timer: it is kept on file with its result and refused as a
game. The game offers shifts 1, 3, 5 and 6.

## Fetch Rush rules 3 (G1.12, Gautham's 2026-10-22 decisions)

Implemented 2026-10-22 in G1.12; rules 1 and 2 above are unchanged and their records still
verify (rules 2 keeps its own file, `coco_depot_v1.fetch_rush.json`). Code:
`games.ROUND_MODES`, `games.round_for(seed, rules=3, mode=...)`, `games.FetchRushRound`;
data: `coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r3.json`, made by
`tools/g1/make_fetch_rush_rounds_r3.py` (Arena hash v3, CPython 3.12; G1.12 in the cloud, regenerated
on the laptop in G1.13 for the start heading below: rules 3 was never deployed, so no published
record used G1.12's start);
tests `coco_lab/test/test_fetch_rush_r3.py`. A record carries `rules: 3` and `mode`.

- **Two modes.** `phone` (the default): **2 orders**; `full` (the "Full shift", offered on
  the mode card and as `&mode=full`): rules 2's 3 orders within 32 m. Bests are kept per mode.
- **Routes never cross the forklift lanes.** A trip counts only if A*'s route on the plan
  grid (what AUTO and the reference bot drive) keeps every cell centre out of
  `zone_forklift_lanes`, from the order's start to the object's nearest such pre-grasp
  pose and on to the drop zone's centre; the drawn ghost route is that route.
- **Every round on file was finished.** The reference bot plays each draw; a round it does
  not finish, or where COCO ever stands inside a lane, is rejected and the seed draws again
  (`attempt`), listed under `rejected`, never offered. None was needed: every first draw
  was finished with 0 contacts.
- **Start in the open, facing the first route (G1.13):** the start point is the zone's free
  plan-grid cell with the most room around it, at least 1.5 m from the forklift lanes (ties:
  nearest the zone's centre); the heading (of 16) is the clear one (a free run of at least
  2.1 m, the chase camera's boom) closest to the direction of the round's first route (from
  the start to the route's point 1 m along it). G1.12 faced the longest clear run instead,
  which on the phone round pointed away from the first route (Gautham, 2026-10-22).
- **Timer = the reference bot's time × 1.5**, as in rules 2.

**The phone budget is 22 m (G1.13, Gautham's 2026-10-22 rule).** The decision's 16 m admits
no lane-free 2-order round: three objects can be reached at all (`obj_dock`, `obj_dispatch`,
`obj_maze_2`), every first order within 16 m is `obj_dock` from the Loading dock (10.7–14.8 m),
and every second order needs at least 21.4 m (`docs/v2/g1/data/g112/phone_budget.json`).
Gautham's rule: the smallest budget, from 22 m up, that gives at least 3 distinct rounds with
every timer ≤ 5:00, else 22 m. `tools/g1/sweep_phone_budget.py` tried every whole metre from 22 m
to the trip table's longest trip (82 m), each seed's round drawn, played by the reference bot
and timed as the generator does (`docs/v2/g1/data/g113/phone_budget_sweep.json`): **none
qualifies.** 22–25 m give one round; from 26 m on, at least one seed's round runs over 5:00
(26–28 m: seed 6's Workshop round, 349.1 s; up to 653.1 s at 80–82 m). So 22 m stands: one
round for every seed, reference 182.3 s, **timer 273.5 s (4:33.5)** (G1.12's 275.9 s changed with
the start heading). Objects were not moved next to the lanes (the decision).

| Mode | Seed | Start zone (heading) | Orders (planned round trip) | Reference bot | Timer |
|---|---|---|---|---|---|
| Phone | 1 | Loading dock (337.5°) | obj_dock → Dock 1 (14.8 m), obj_dispatch → Dispatch (21.4 m) | 182.3 s, 0 contacts, path efficiency 0.987 | **273.5 s** (4:33.5) |
| Phone | 2 | Loading dock (337.5°) | obj_dock → Dock 1 (14.8 m), obj_dispatch → Dispatch (21.4 m) | 182.3 s, 0 contacts, path efficiency 0.987 | **273.5 s** (4:33.5) |
| Phone | 3 | Loading dock (337.5°) | obj_dock → Dock 1 (14.8 m), obj_dispatch → Dispatch (21.4 m) | 182.3 s, 0 contacts, path efficiency 0.987 | **273.5 s** (4:33.5) |
| Phone | 4 | Loading dock (337.5°) | obj_dock → Dock 1 (14.8 m), obj_dispatch → Dispatch (21.4 m) | 182.3 s, 0 contacts, path efficiency 0.987 | **273.5 s** (4:33.5) |
| Phone | 5 | Loading dock (337.5°) | obj_dock → Dock 1 (14.8 m), obj_dispatch → Dispatch (21.4 m) | 182.3 s, 0 contacts, path efficiency 0.987 | **273.5 s** (4:33.5) |
| Phone | 6 | Loading dock (337.5°) | obj_dock → Dock 1 (14.8 m), obj_dispatch → Dispatch (21.4 m) | 182.3 s, 0 contacts, path efficiency 0.987 | **273.5 s** (4:33.5) |
| Full shift | 1 | Workshop maze (315.0°) | obj_maze_2 → Dispatch (25.7 m), obj_dispatch → Dock 2 (24.9 m), obj_dock → Dock 2 (15.5 m) | 316.5 s, 0 contacts, path efficiency 0.987 | **474.8 s** (7:54.8) |
| Full shift | 2 | Loading dock (337.5°) | obj_dock → Dock 2 (12.2 m), obj_dispatch → Dispatch (24.9 m), obj_maze_2 → Dispatch (31.9 m) | 323.9 s, 0 contacts, path efficiency 0.996 | **485.8 s** (8:05.8) |
| Full shift | 3 | Workshop maze (315.0°) | obj_maze_2 → Dispatch (25.7 m), obj_dispatch → Dock 1 (21.4 m), obj_dock → Dock 2 (18.3 m) | 315.5 s, 0 contacts, path efficiency 0.988 | **473.2 s** (7:53.2) |
| Full shift | 4 | Loading dock (337.5°) | obj_dock → Dock 3 (10.7 m), obj_dispatch → Dispatch (28.4 m), obj_maze_2 → Dispatch (31.9 m) | 330.8 s, 0 contacts, path efficiency 0.999 | **496.2 s** (8:16.2) |
| Full shift | 5 | Loading dock (337.5°) | obj_dock → Dock 2 (12.2 m), obj_dispatch → Dispatch (24.9 m), obj_maze_2 → Dispatch (31.9 m) | 323.9 s, 0 contacts, path efficiency 0.996 | **485.8 s** (8:05.8) |
| Full shift | 6 | Workshop maze (315.0°) | obj_maze_2 → Dispatch (25.7 m), obj_dock → Dock 3 (31.8 m), obj_dispatch → Dispatch (28.4 m) | 383.4 s, 0 contacts, path efficiency 0.993 | **575.1 s** (9:35.1) |

With the lanes kept out the Depot offers little variety: the six phone shifts are one round
(from the Loading dock); the six Full shifts are five rounds, from the Loading dock or the
Workshop. (Rules 2's High-bay rounds, seeds 2, 4 and 5, all crossed a lane.)

## Fetch Rush rules 5 (G2, Gautham's 2026-10-24 report)

"There is no dynamic path or the fixed path in auto mode is not changing when the forklift
arrives; the robot just stays still and the forklift moves forward phasing through the robot."
Implemented 2026-10-24/25 on `v2/g2-actor-yield`; rules 1–4 are unchanged (their setup inputs,
records, hashes and files; every committed reference of rules 2, 3 and 4 replays to its chain).
Evidence and numbers: [`docs/v2/g2/data/rules5/README.md`](../g2/data/rules5/README.md) (MODEL).

- **Why it happened (rules 1–4).** An actor is a schedule: its pose is a function of time. The
  Arena refuses COCO's step into an actor's discs, but nothing checks an actor moving onto COCO.
  Once a disc covers COCO every step is refused (COCO "stays still") and the forklift drives on
  through it. AUTO planned once on the static map and never re-planned.
- **Actors stop for COCO** (`actors.yield=1`, a forklift's safety stop): each actor keeps its
  own clock (the ticks it has held, `lag`) and holds while its next box would come within COCO's
  radius + `ACTOR_STOP_MARGIN` (0.3 m) of COCO's centre and closer than now (COCO ahead of it in
  its direction of travel). Passing COCO sideways, or moving away, it goes on. The discs, the
  LiDAR, the clearance, the HUD's actors and every prediction read the actual poses.
- **AUTO reacts** (`avoid.on=1`, the subsystem `games.ActorAvoid`): a moving actor in the path's
  4 s look-ahead (2 × radius margin, the reference bots' rule) → AUTO holds and waits; after 3 s
  it re-plans once around the actor's box and takes the route only if it is clear; after 10 s it
  goes on (the actors stop for it) with a short-range check. An actor that has stopped for COCO
  gives COCO the right of way: AUTO drives on, re-plans around its box when the path runs into
  it (one search, at most one per 2 s, on a copy of the plan grid), or backs away from it.
- **Rounds** (`coco_lab/levels/coco_depot_v1.fetch_rush.r5.json`, `tools/g2/make_fetch_rush_rounds_r4.py
  --rules 5`): rules 4's draw, budgets and crossing rule; the reference bot plays under rules 5
  (no STOPs of its own: the model yields). Every round equals rules 4's; reference times are equal
  except Full shifts 2 and 4 (388.3 s, timer 582.5 s, against 387.8 s / 581.7 s). Phone timers are
  unchanged (4 distinct rounds, 4:35.9–5:49.1; ≤ 6:00, none ≤ 5:00, as rules 4). Records carry
  `rules: 5`; bests use new keys (`…r5-{mode}…`).
- **Free Drive** on a v3 level gets the same two settings in its setup.
- **The Gazebo stack's actors never yield** (they are parked in the recorded Race Nav2 ghosts,
  and scripted in Gazebo): model-vs-STACK comparisons under rules 5 compare a yielding model
  with a stack whose actors do not.
