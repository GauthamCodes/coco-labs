**Try it:** https://gauthamcodes.github.io/coco-labs/?view=search

COCO Lab's fourth lab, **Search**: where should the robot look next, given
what it knows? Until now COCO's autonomous mode was TOLD which bay the
colour was in. Now it is told one word — a colour — and finds the target
itself: a belief over the four bays, Bayes' rule on every miss, and the
order with the least expected search cost, chosen by `coco_lab` (Python, in
your browser via Pyodide, and in the real mission — the same code). The page
never decides. Write-up, every claim's evidence and the limitations:
[`docs/labs/LAB4_SEARCH.md`](https://github.com/GauthamCodes/coco-labs/blob/lab4-v1.0/docs/labs/LAB4_SEARCH.md).

### In the lab

- **Find it (Sketch, labelled as a model):** choose your search order,
  predict whose order has the lower expected cost, place the target, reveal
  coco_lab's plans, and watch both searches on the same placement and seed —
  belief bars, searched bays, the camera's view while it looks, the costs
  coco_lab compared at every step. Change the prior and the detection
  probability and see the robot's order change.
- **The real robot (Replay):** 16 searches the real mission ran in Gazebo,
  told only the colour, with the mission's state machine in simulator
  seconds and the truth — from the episode manifest, the evaluator's side —
  behind a toggle.
- **What is proven:** every claim with the test it rests on, and the Gazebo
  matrix.
- **The Live tab** labels the autonomous mode from what the running mission
  reports: "the robot discovers the target" only when it is searching.

### Measured (details in `docs/RESULTS.md` "COCO Lab Phase 5")

The searching mission in Gazebo, 16 runs, a fresh simulator each, never
`--fast`, told only the colour (both robot nodes held an empty region map in
every run) — `docs/data/lab4/`:

- **14 COMPLETE, 2 ABORT.** Of the 14, three relocalised once on the way
  home and recovered. The aborts: one localisation failure on the return
  after the target was found and lifted (AMCL 4.8 m from ground truth, not
  recovered, **not attributed**), and the deliberate "give up after the
  first bay" order, which fails the challenge as designed.
- **Negative search, on the robot:** in 14 runs the target was not in the
  first bay; twice it was in the last of four.
- **39 looks, all agreeing with the truth** (24 misses, 15 finds); 24 of 24
  retreats down the ramp; lift verified 15 of 15; home error 0.016–0.169 m.
- **The robot chose what coco_lab chooses:** every recorded search is rebuilt
  from its own looks and reproduces byte for byte.
- 16 runs is an inventory, not a rate. The detection probability the robot
  plans with (0.9) is an assumption.

Found and fixed on the way: the default `mission.launch.py` — and so the Live
tab's local stack — had been unable to start since 2026-10-02 (`origins` `*`
parsed as YAML).

### Tests

`run_all_package_tests.sh` 2,975 passed, 0 failed, 0 skipped (coco_lab 533,
coco_mission 371, coco_sim 323); lab_web vitest 289, tools 104; CI green.

### Demo video

`coco_lab4_demo.mp4` (attached): recorded in headless Firefox from the
public site, browser only; coco_lab's computing waits cut and listed
(`docs/data/lab4/video/`).
