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
never yield: they are a schedule, the same schedule `actors.json` gives Gazebo.

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
