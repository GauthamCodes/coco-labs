# G1.12 evidence — phone rounds, lanes, AUTO, chase camera

Gautham's decisions of 2026-10-22 (`docs/STATUS.md` plan-change log; `G1_STATUS.md`).
All runs in this cloud container (Xeon × 4, Chromium on SwiftShader, no GPU): every
browser number below is **emulated / cloud**, not a phone or the laptop.

## 1–2. Fetch Rush rules 3: phone round, Full shift, lanes kept out

Rounds: `coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r3.json`
(`tools/g1/make_fetch_rush_rounds_r3.py`); rules and the per-seed table:
[`docs/v2/m6/GAMES.md`](../../../m6/GAMES.md#fetch-rush-rules-3-g112-gauthams-2026-10-22-decisions).

- No route crosses a forklift lane: a trip counts only if A*'s cells (the plan grid AUTO and
  the reference bot drive) all stay out of `zone_forklift_lanes`; the reference bot's run is
  rejected, and the seed redrawn, if COCO ever stands in a lane or does not deliver every
  order. None was rejected (every first draw: all orders delivered, 0 contacts, no lane).
- **The decision's 16 m phone budget cannot be met on the Depot.** With the lanes kept out,
  three objects can be reached; every second order needs ≥ 21.4 m. Per budget, the 2-order
  rounds that exist: [`phone_budget.json`](phone_budget.json) (16–21 m: none; 22–24 m: one;
  25 m: two; 30 m: fifteen). The phone round uses **22 m, provisionally** — one round for
  every seed, reference 183.9 s, **timer 275.9 s (4:35.9)** against the 3–4 min target.
- Full shift (32 m, 3 orders): five rounds over six seeds, timers **475.7–577.5 s**.
- Start: the zone's roomiest free cell, ≥ 1.5 m from the lanes, facing the longest clear run.

## 3. AUTO without pausing the model

`Arena.prefetch` runs, between ticks, the very search AUTO's goal would start (same
planner, start cell, goal cell and grid); the tick that AUTO opens takes it over, finished or
part-done — the same generator, so the same plan and every hash unchanged
(`coco_lab/test/test_arena_prefetch.py`: full, part-done and stale prefetches leave every
tick's hash, plan and summary identical; `test_g1_game_glue.py`: the AUTO tick adopts the
prefetched search). The worker runs it while idle in slices of ≤ 4 ms and gives way to any
step or query; the game streams no search events (it draws none).

`lab_web/tools/g1/fetch_timing.mjs`, desktop 1280 × 720, `tier=low`, the page's own keys,
**one machine, back to back** ([`timing_before.json`](timing_before.json): G1.11's build
`a4b39a6`, rules 2 shift 1; [`timing_after_full.json`](timing_after_full.json): G1.12 Full
shift 1; [`timing_after_phone.json`](timing_after_phone.json): G1.12 phone round 1). Tick
arrivals are time-stamped on the worker's message; the model's tick period is 100 ms.

| | Before (G1.11) | After, Full shift | After, phone |
| --- | --- | --- | --- |
| AUTO presses | 8 | 8 | 5 |
| Worker step of the AUTO ticks, max | **452 ms** | **101 ms** | **89 ms** |
| Tick gap around a press, range | 243–854 ms | 127–747 ms | 286–626 ms |
| All tick arrivals: median / p95 / max | 57 / 450 / 854 ms | 59 / 334 / 747 ms | 76 / 304 / 626 ms |
| "Clock waits" banner | never | never | never |
| Deliveries | 3/3 | 3/3 | 2/2 |

**What this shows, and what it does not.** The planner no longer stalls the AUTO tick: its
worker step falls from 452 ms to ≤ 101 ms, about one tick period. The target — "AUTO press →
motion with no model-tick gap over 100 ms" — is **not shown in this container**: here tick
arrivals jitter by hundreds of milliseconds with no AUTO press at all (p95 304–450 ms; the
renderer is software and competes with the worker for 4 cores), and the largest gaps fall at
the first press, 0.3 s into the round, where the worker step was short (56–76 ms) and the
main thread busiest. It is a laptop measurement (G1_STATUS). A first set from before this
container restarted, on a faster host, is kept in [`run_a_before_restart/`](run_a_before_restart/)
(AUTO-tick worker step 407 → ≤ 63 ms there; arrival p95 329 ms before, 128–137 ms after).

## 4. Chase camera

`lab_web/src/game/render/camera.ts`: a 2.1 m boom (never under 1.7 m; camera ≥ 1.2 m above
the floor), COCO's centre at NDC y = +0.2 (40 % down: the upper-middle third), clear rays
from COCO's centre and both shoulders; a wall makes the boom rise and tilt down, not move in.
Headlight 6 → 2.2, its floor pool halved, bloom 0.55 → 0.35 with threshold 0.92 → 0.97.

- `lab_web/test/g1_camera.test.ts` (vitest, 25): on 20 scripted paths no clipping, nothing
  between the camera and COCO's centre or shoulders, distance ≥ 1.7 m, height ≥ 1.2 m, COCO's
  centre in the upper-middle third on every frame; beside a wall the boom rises (elevation up,
  length ≥ 1.7 m); G1.11's spawn (half hidden by the south wall) as a case.
- `lab_web/tools/g1/chase_hud_check.mjs` (a CI step): the real page, 20 scripted poses (off the
  forklift lanes), phone landscape (emulated Nothing Phone (1)) and desktop; after each pose the
  camera settles (COCO's box still; up to 3.4 s here); COCO's projected box overlaps **no HUD
  rectangle in 40/40** ([`chase_hud.json`](chase_hud.json); COCO's centre 40.5–43.8 % down; box
  55–105 px wide on the phone, 96–184 px on desktop; samples in [`chase/`](chase/)).
- After shots: [`../../screens/after_g112/`](../../screens/after_g112/), BEFORE_AFTER.md column
  "After G1.12". **Gautham judges the look.**
