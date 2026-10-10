# M2 prompt — Part B (as issued by Gautham, 2026-10-09)

Saved verbatim in substance from the owner's prompt, as B asks. Part A of
that prompt (the independent review and merge of M1, PR #20) is recorded in
[`reviews/M1_REVIEW.md`](reviews/M1_REVIEW.md) and `docs/STATUS.md`. Section
0's decisions are in `docs/STATUS.md`'s plan-change log (2026-10-09). This
file quotes the plan; it never extends it (README §0).

---

## PART B — Milestone M2 · The whole loop

The M2 goal: localization, mapping and SLAM, local control and search
decisions run together in the one arena, as glass boxes. Labs 2–5 live on
as Learn missions. A learner can watch one subsystem break another. Run 15
shows localization error making the controllers refuse the path. The old
per-lab views are retired without breaking a link.

Read README sections 3, 5, 7 (M2) and 9. Save Part B of this prompt into
the repo as `docs/v2/M2_PROMPT.md`.

### B.1 Setup and preflight

- In `~/coco_labs_ws/src/coco-labs`, fast-forward `main` to `origin/main`
  (`--ff-only`). If the checkout has local changes or unique commits, stop
  and ask Gautham.
- Create branch `v2/m2-whole-loop`.
- Run the three suites as the M2 baseline. Record them, with the toolchain
  versions and power state.
- Read `docs/STATUS.md`. If Gautham has recorded phone results there that
  fail a budget (under 30 fps at default detail, or first visible
  computation over 10 s on mobile data), fixing that comes first, as
  checkpoint M2.0b. Do this before any other work.

### B.2 Checkpoints

Prefix commits `[M2.x]`. Update `docs/STATUS.md` at the end of every
checkpoint with: what was done; the evidence file; the exact next step.

Continue between checkpoints without asking, unless a stop condition fires.
Every algorithm stays in `coco_lab`, in Python, with no rclpy. The browser
only renders events.

**M2.0 Carry-overs from M1.**
- Cancellable planning: a new goal or planner change cancels the in-flight
  search. Target: goal click after a planner change, median ≤ 100 ms and
  maximum ≤ 500 ms, from 293 ms median and 4.0 s maximum today.
- Delay attract-mode work until the live model has loaded. Measure the
  effect on live-model-ready.
- Make every harness record power state (section 0, item 1).
- Live model ready ≤ 10 s on emulated 4G for the Plan lens. Other lenses
  lazy-load their Python modules within 3 s of being selected, warm cache.

**M2.1 Schemas**, all additive within `coco_schemas`:
- `estimate`
- `localise.particles`, `localise.ekf`
- `map.grid`, `map.slam`
- `control.local`: candidate trajectories, per-critic scores, rejection
  reasons, selected command
- `decide.search`: region beliefs, expected cost per order, chosen action,
  observation
- `mission.fsm`: transitions with reasons
- `sensor.detect`: abstract colour detection with a labelled detection
  probability
- `arm`: kinematic joint state, finger state, magnet state

Update `docs/v2/SCHEMAS.md`. The CI compatibility check must pass.

**M2.2 Lens framework.**
- A lens registry. One lens per family: Plan, Localise, Map, Move, Decide.
- A Focus toggle that dims everything outside the lens.
- Three disclosure levels:
  - Watch: at most 2 computation layers by default
  - Explain: value labels on hover, short captions at key events
  - Inspect: full inspector, event log, metric charts
- Inspector templates per family.
- Charts appear only at Inspect level or when a mission asks for one.
- Extend `docs/v2/VISUAL_SYSTEM.md` with fixed colours for each new layer.
  Uncertainty is always translucent; truth is always an outline.

**M2.3 Localise lens.**
- MCL (particle count, motion and sensor noise, random-particle injection)
  and EKF, run in the arena on identical inputs.
- Kidnapping by dragging the robot.
- Belief against truth, with the error series at Inspect level.
- An optional, labelled wheel-slip option in the Arena model, addressing
  the known turn divergence. Measure its effect on odometry against the
  recorded Gazebo data, and keep it off by default unless the measurement
  says otherwise.
- Reproduce the model kidnapping result (18/20 with injection, 0/20
  without) with the new engine, or explain the difference.

**M2.4 Map lens.**
- Log-odds occupancy mapping, EKF-SLAM (its landmark sensor labelled
  idealized), FastSLAM, and pose-graph SLAM with loop closure shown before
  and after.
- Map-quality metrics: ATE and F1.
- The existing map-the-arena scenario runs in the new engine.

**M2.5 Move lens.** New teaching implementations, all labelled MODEL:
- a DWA-style velocity sampler
- a pure-pursuit tracker with regulated speed
- a small MPPI

Each emits `control.local` with per-critic scores and rejection reasons.
Arena actors have collision bodies, unlike Lab 5's Gazebo actors. Say so
wherever the two are compared. Rebuild Lab 5's three scenarios (hairpin,
crossing, head-on) from their world definitions. Run the model controllers
on them and compare with Lab 5's STACK results in
`docs/v2/M2_MOVE_COMPARISON.md`. Report differences honestly; the model
doesn't have to match. Run 15 in the model: inject a 3.4 m localization
error and show the path falling outside the local window, with all three
controllers producing no valid candidate. Label it MODEL. The STACK result
(9/9) is cited beside it.

**M2.6 Decide lens and the fetch mission.**
- Bayesian bay search over COCO's four bays: belief, the expected cost of
  every order, the chosen region, and the update after a miss. The
  detection probability (0.9) is labelled ASSUMPTION.
- Abstract colour detection through `sensor.detect`.
- A kinematic 2-DOF arm in a side-view inset. The gripper has two fingers
  and a magnet, and the magnet does the holding.
- A complete Arena fetch mission (`mission.fsm`): localise → choose a bay →
  plan → local control → detect → grasp → return.
- Whole-loop visibility: when localization degrades, the learner can see it
  reach the planner and controller. This is the point of M2.

**M2.7 Converters.**
- Labs 2–5 bundles convert losslessly into the new families. Round-trip
  tests compare every field.
- All 16 recorded search runs replay byte for byte through the new
  pipeline. This is a hard requirement.
- Lab 5's Nav2 candidate overlays play as STACK.

**M2.8 Learn missions 1–6**, as YAML data, not code:
1. How does a robot find a path?
2. What if the world changes?
3. How does a robot know where it is?
4. How does it build a map?
5. How does it avoid things while following a path?
6. How does it decide where to look?

Each mission follows the seven beats from the README: hook, predict,
reveal, manipulate, explain, check against the Stack, challenge (the
challenge beat is a stub until M3). Add a mission player. Then add a CI
check: every learner-facing claim in mission files carries an evidence
reference that resolves to a `docs/RESULTS.md` anchor or a committed
evidence file. Any claim without one fails CI. Every claim from the Lab 1–5
pages must reappear in some mission, with its evidence, including the
negative and unresolved results. Prove this with a coverage table in
`docs/v2/M2_CLAIMS_COVERAGE.md`.

**M2.9 Fidelity report v1.**
- `docs/v2/FIDELITY_v1.md`: LiDAR agreement, odometry in straight lines and
  in turns (with and without the slip option), and controller tracking
  against the Lab 5 recordings.
- In the UI, a "model gap" chip wherever a lesson depends on one of these.

**M2.10 Retire the v1 lab views** (section 0, item 5).
- Build v1 from the tag `coco-lab-v1-final` and serve it at `/v1/` from the
  Pages deploy. Choose how it is stored and record the choice in
  `docs/v2/adr/0003-v1-archive.md`.
- Redirect `?view=plan|localise|map|search|move` to the matching Learn
  mission. Each mission page has a link to its v1 page.
- Make `?bundle=` and `?v=` share links open the run in v2 through the
  converters, or forward them to `/v1/` with their query intact if they
  can't be converted.
- The Live view stays in `main` until M5.
- Remove the v1 lab view code from `main` only after all of the following
  are true:
  - a test opens every v1 URL form and asserts it resolves with 0 console
    errors
  - `M2_CLAIMS_COVERAGE.md` is complete
  - the 16 search runs replay byte for byte
- List every removed file in the commit message.

**M2.11 Measure and decide.**
- Measure every budget in B.3, in balanced mode on AC.
- Write `docs/v2/M2_RESULTS.md` and append to `docs/RESULTS.md`.
- Update `docs/v2/PHONE_MEASURE.md` for the new lenses.
- Write `docs/v2/USABILITY_TEST_M2.md`: five people, missions 1, 3 and 5, a
  results table.
- Record any WebAssembly decision in a new ADR, and port only a kernel that
  fails a budget, under trace-equivalence tests.

### B.3 Acceptance criteria

| Area | Criterion | Who measures |
|---|---|---|
| Determinism | Identical per-tick hashes across Chromium, Firefox, WebKit and Pyodide-in-Node, over 100 sessions that include localization noise, mapping and the fetch mission | Agent |
| Correctness | Golden traces for every algorithm family on its property corpus; the 16 search runs replay byte for byte | Agent (CI) |
| Claims | Every Lab 1–5 learner-facing claim appears in a mission with resolving evidence; the CI evidence check passes | Agent (CI) |
| Laptop performance | 60 fps with all lenses' default layers on the fetch mission, plus a stress scene: 2,000 particles, 1,000 MPPI samples × 56 steps, a full occupancy grid | Agent |
| Responsiveness | Goal click after a planner change: median ≤ 100 ms, maximum ≤ 500 ms; seek ≤ 100 ms on a 5-minute fetch-mission recording | Agent |
| Cold start | First visible computation ≤ 10 s and live model ready ≤ 10 s (Plan lens), emulated 4G; other lenses ready within 3 s of selection, warm cache | Agent |
| Links | Every v1 URL form resolves with 0 console errors; the bare URL opens the Arena | Agent |
| Hygiene | 0 console errors in all views; phone-width layout checked; all suites and CI green | Agent |
| Phone | ≥ 30 fps at default detail on the fetch mission; first visible computation ≤ 10 s on mobile data | Gautham |
| Usability | 5 people new to robotics complete missions 1, 3 and 5 and explain one computation each, unaided | Gautham |

The agent closes every criterion it can measure. The Gautham rows stay
pending Gautham; never mark them done yourself.

### B.4 Scope fence for M2

Not in M2:
- the Case Files UI or a ROS-to-event adapter that reads raw rosbags (M3);
  converting existing bundles is in scope
- Play mode, challenges, scoring, leaderboards (M3)
- the cloud, accounts, Stack batch runs (M4)
- any change to the Live view beyond keeping it working
- RL, multi-robot, VLM
- a third simulator
- changes to the frozen robot-stack packages or the robot repo

Anything else worth doing goes to `docs/IDEAS.md` as one line.

Git:
- Work only on `v2/m2-whole-loop`. Push it regularly.
- Open a pull request into `main` when all agent-measurable criteria pass.
  Do not merge it. The merge permission in section 0 covers PR #20 only.
- Do not deploy Pages manually, and do not edit releases.

### B.5 Stop and ask Gautham if

- Phone results recorded in `STATUS.md` fail a budget and the cause isn't
  found within one checkpoint.
- Cross-browser hashes differ for a new algorithm family and the cause
  isn't found within one checkpoint.
- The 16 search runs cannot be made to replay byte for byte.
- A Lab 1–5 claim cannot be carried into a mission with its evidence.
- Retiring a v1 view would break any URL or lose any claim.
- Any step would require deleting evidence, a release or a working public
  URL.

### Final report (end of every session)

```
Part A (first session only): review verdicts summary | fixes made | PR #20 merge SHA | public-site check result
Balanced-mode re-measurement vs power-saver (M1 budgets):
Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements taken (with device, power profile and conditions), against M1:
Acceptance criteria: each → met / not met / pending Gautham, with evidence:
Files removed (full list) and why:
Decisions recorded (ADRs):
Plan-change log entries added:
Deviations from the plan, and why:
Ideas parked in docs/IDEAS.md:
Stop condition hit? which one:
Questions for Gautham:
Next step according to README.md:
```
