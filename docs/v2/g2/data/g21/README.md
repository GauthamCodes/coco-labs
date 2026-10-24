# G2.1 — Gautham's decisions on G1.13's open items: evidence

MODEL (the browser model's rules and reference bot), computed on the laptop.

## 1. Phone round variety — Fetch Rush rules 4

**The rule** (Gautham, 2026-10-23; planning answer 2026-10-24): routes may cross the east–west forklift
lane only at a marked (hazard-striped) crossing, never run along it. Implemented in `coco_lab/games.py`
(rules 4: `crossings`, `crossing_bands`, `crossing_windows`, `lane_grid`) and
`tools/g2/make_fetch_rush_rounds_r4.py`; the stripes painted (`describe.ts`) are the crossings the rule
uses (`lab_web/test/g2_crossings.test.ts`). Rules 3's file and records are unchanged.

**Measured: neither marked crossing can be used.** The two crossings (x 23.7–24.7 and 39.5–40.5, the lane's
full depth) are exactly where the walkers walk, end to end. `games.crossing_windows` tries a straight
crossing at COCO's auto speed (0.3 m/s, 13.1 s) from each of 600 start times (60 s, covering the
walkers' 10 s and the forklift's 40 s cycles), against the actors' own schedules: **0 of 600** keeps
COCO clear of the walker at either crossing (best clearance −0.22 m: the walker's box over COCO's
centre). A first generation without this check drew 269 crossing trips of 360; the reference bot never
finished one (it yields to the walker in the crossing indefinitely), so every crossing draw was
rejected. With both crossings closed, **no route crosses the lane**: the rule is kept by never crossing.
Question for Gautham: move or widen the crossings, or keep "routes never cross".

**The budget sweep** (`tools/g2/sweep_phone_budget_r4.py`, G1.13's method: whole metres from 22 m,
seeds 1–6, "distinct" = (start zone, orders), a budget fails at the first timer over the limit):

- **≤ 5:00** ([`phone_budget_sweep_r4_5min_log.txt`](phone_budget_sweep_r4_5min_log.txt)): no budget from
  22 m to 81 m qualifies (22–25 m: one round; 26–81 m: some seed's timer is over 5:00 every time —
  seed 6 in 35 budgets, seed 5 in 10, seed 1 in 7, seeds 2 and 4 in 2 each; the failing timers 330.6 s to
  622.3 s). The sweep runs to the longest trip, **152.4 m** (closed crossings make cross-hall
  trips go round the lane), and was still running at G2's close; its last row is in G2_RESULTS.md.
- **≤ 6:00** ([`phone_budget_sweep_r4_6min.json`](phone_budget_sweep_r4_6min.json)): **26 m is the smallest
  budget** with ≥ 3 distinct rounds and every timer ≤ 6:00 — 4 distinct rounds:

  | Seeds | Start zone | Orders | Timer |
  | --- | --- | --- | --- |
  | 2, 4, 5 | loading dock | obj_dock → dock_2, obj_dispatch → dispatch_drop | 275.9 s (4:35.9) |
  | 3 | workshop | obj_maze_2 → dispatch_drop, obj_dispatch → dispatch_drop | 299.1 s (4:59.1) |
  | 1 | workshop | obj_maze_2 → dispatch_drop, obj_dispatch → dock_1 | 331.4 s (5:31.4) |
  | 6 | workshop | obj_maze_2 → dispatch_drop, obj_dispatch → dock_2 | 349.1 s (5:49.1) |

**So the phone budget is 26 m** (`games.ROUND_MODES_R4`), the Full shift keeps 3 orders within 32 m;
the rounds file `coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r4.json` is regenerated with it
(its reference records, cards and hash chains; `coco_lab/test/test_fetch_rush_r4.py`). Bests move to new
keys (`…r4-{mode}…`); rules-3 bests stay.

## 2. AUTO stall (119–141 ms vs 100 ms)

Accepted for now, tracked open; re-measured at G2.8 (G2_RESULTS.md) to show G2 did not make it worse.

## 3. Heavy saved settings on phones

`lab_web/src/game/fps_watch.ts`: on a phone, if the drawn frame rate stays under 55 fps for 10 s (ten
1 s windows in a row) while playing, a one-tap "Switch to recommended settings" toast (medium, 60 fps
cap; it says it restarts the run). Never applied silently; never suggests heavier settings; once per
session. `lab_web/test/g2_fps_watch.test.ts`.

## 4. Old phone screenshots in git history

Accepted; no history rewrite (recorded only).
