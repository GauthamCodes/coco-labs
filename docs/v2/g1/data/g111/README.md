# G1.11 — Gautham's follow-up (2026-10-21)

Evidence class MODEL in the browser, TESTED. Cloud container (Xeon 2.1 GHz × 4, Chromium on
SwiftShader: no GPU, so drawn frame rates are not measured; frame times are main-thread JS).

## The Fetch Rush freeze: before and after

`lab_web/tools/g1/fetch_timing.mjs`: Fetch Rush shift 1 through the page's own keys (AUTO, GRAB,
AUTO, DROP), desktop profile, `tier=low`, the same machine and harness. **Before** = the build at
`81121dc` (G1.10's head; static-cache hash `a23aee4…`, the same as G1.10's), 2 deliveries
attempted. **After** = this branch, 3 deliveries ([`timing_before.json`](timing_before.json),
[`timing_after.json`](timing_after.json)).

| | Before (rules 1, G1.10) | After (rules 2, G1.11) |
| --- | --- | --- |
| Rules / orders / timer | 1: 10 orders, 180 s | 2: 3 orders, 491.7 s |
| Deliveries played | 1 | 3 |
| Worst gap between model ticks | 25.81 s | 0.96 s |
| Gaps over 0.8 s | 15 (worst: 25809 ms at tick 1415) | 3 (worst: 960 ms at tick 9) |
| Worker's step per tick, median / p95 / max | 39 / 68 / 2184 ms | 33 / 54 / 76 ms |
| "Clock waits" banner | 2×, 26.8 s | never |
| Main-thread JS per frame, median / p95 / max | 1.3 / 4.2 / 408 ms | 1.5 / 4.3 / 19 ms |
| Frames over 50 ms | 1 of 1626 | 0 of 3162 |

Before, the next order's planner ghost (M6F.6's `FetchRush._new_order`: up to 17 A* searches on the
Depot) ran inside the tick after a delivery: **25.8 s** with the banner up (the old run then
reached only 1 delivery before its order-2 timeout). After, the round's orders, ghosts and routes
are precomputed (`coco_lab/levels/coco_depot_v1.fetch_rush.json`), nothing is planned in play
(tested: `test_playing_a_round_never_plans`), and the next order appears in the next tick. The
three gaps of 0.82–0.96 s that remain fall where AUTO is pressed (ticks 9, 20, 2148): the
Arena's own planner routing COCO to the goal, as for a tapped goal (measured on the main
thread, where a SwiftShader frame is itself ~0.25 s); the banner never showed. They are not
hidden: AUTO's route planning is the remaining sub-second wait, not part of this fix. One 467 ms frame in the first after-run (the first
AUTO compiling the plan, target and chevron shaders) is gone: every material is now compiled
behind the loading screen (`GameRenderer.precompile`).

## Fetch Rush against the 2026-10-18 decision

The HUD's "DELIVER 0/10" and 3:00 were the code's (M6F.6's rules 1), not the decision's. Rules 2
implement it — see [`docs/v2/m6/GAMES.md`](../../../m6/GAMES.md#fetch-rush-rules-2-g111-gauthams-2026-10-18-decision)
for the rules and every seed's reference numbers: a start zone, 3 orders each within a 32 m
planned round trip, timer = the reference bot's time × 1.5 → **491.7 / 495.8 / 577.2 / 506.5 s**
on seeds 1 / 3 / 5 / 6 (8:11–9:37). Seeds 2 and 4 drew a round whose first leg crosses the
forklift lane; the reference bot stopped in the lane (0 delivered, 214 contacts), so they have no
timer and are not offered.

## Hash v3's cost

Profiled once (CPython, 400 Depot ticks): the LiDAR computed each beam's `cos`/`sin` three times
a tick (walls, ramps, discs). Now once (`Arena._scan` → `SketchMap.cast_dir`, the helpers take
`dirs`): the same expression, so the same bits — v1/v2/v3 goldens and both chains unchanged.
Pyodide-in-Node per model tick on the Depot, both versions in the same run
([`tick_cost.json`](tick_cost.json)): v2 23.3 ms, v3 25.6 ms median —
**v3/v2 1.10**, from 1.15 at G1.8.

## gz

`@pytest.mark.gz` on `test_worldgen.py::test_gz_sdf_check_passes_on_every_generated_world`; the
plain-venv CI job runs `-m "not gz"` (no skips, its guard holds). The gz tests run on the laptop.

## Look

[`../../BEFORE_AFTER.md`](../../BEFORE_AFTER.md), after shots in
[`../../screens/after_g111/`](../../screens/after_g111/): exposure and a cool fill, COCO's rim light,
brighter body and LED glow, the ghost route as a thin line with chevrons and a small pin, the
minimap's contrast, ghost route, PICK/DROP markers and off-map arrows. **Gautham judges the look.**
