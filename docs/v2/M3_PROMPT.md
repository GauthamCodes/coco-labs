# M3 prompt — Part B: Milestone M3 · Play and Case Files

Saved verbatim from Gautham's prompt of 2026-10-10 (Part B; Part A — the M2
review and merge — is recorded in `docs/v2/reviews/M2_REVIEW.md`). Section 0
of the prompt (decisions and one-off permissions) is recorded in
`docs/STATUS.md`'s plan-change log, dated 2026-10-10.

---

The M3 goal: COCO Lab gets its two public-facing hooks.

- **Case Files:** every recorded full-stack run, inspectable in the same arena viewer, with the model-vs-Stack comparison.
- **Play:** challenges scored only with real robotics metrics.

This is the content of the public v2 launch. The launch itself stays gated on Gautham's phone and usability results.

Read README sections 3, 5, 7 (M3) and the game and evidence rules. Save Part B of this prompt as `docs/v2/M3_PROMPT.md`.

## B.1 Setup

- Fast-forward `main` (`--ff-only`). If the checkout has local changes, stop and ask.
- Create branch `v2/m3-play-casefiles`.
- Run the three suites as the M3 baseline, with the toolchain and power state.
- If Gautham has recorded phone results in STATUS.md that fail a budget, fixing that comes first, as M3.0b.

## B.2 Checkpoints

Prefix commits `[M3.x]`. Update STATUS.md at every checkpoint with:

- what was done
- the evidence file
- the exact next step

Continue between checkpoints without asking, unless a stop condition fires.

**M3.0 Carry-overs.**

- The v1-site archive (section 0, item 2).
- "Reset home" for the Arena fetch mission. Each fetch in a multi-fetch session starts from home, so one controller stall doesn't poison later fetches.
- Re-record any affected recordings honestly.

**M3.1 ROS-to-event adapter, in `coco_lab_ros`.**

- Read rosbag2 / MCAP recordings and emit COCO event families: robot, truth (from the simulator's ground-truth topics only), sensor.scan, estimate, plan, control.local (from Nav2 candidate topics where recorded), mission.fsm, metrics.
- Pure conversion: no algorithm runs during conversion.
- Tests on short committed fixture bags.
- Record the mapping table in `docs/v2/ADAPTER.md`.

**M3.2 Case Files storage decision**, recorded in `docs/v2/adr/0005-case-file-storage.md`.

- Raw bags stay in `~/coco_lab_runs/`. Never move or delete them.
- Converted Case Files are summary-detail event MCAPs. Each manifest cites its source bag by checksum.
- Budget: about 20 MB per Case File and about 150 MB in total on the site, lazy-loaded.
- If they don't fit in the repo within that budget, stop and ask Gautham. The alternative is release assets, and only he creates releases.

**M3.3 Case Files.** Convert and publish these, each with the STACK badge:

- the 16 Lab 4 search runs
- the 54 Lab 5 Move runs (grouped by scenario and controller)
- the slam_toolbox and Cartographer tours, loop closure on and off
- Run 15
- the A* myth exhibit
- the Lab 2 AMCL kidnapping runs, and the robot_localization tour
- Lab 1's three recorded runs

Each Case File has:

- the timeline
- a short explanation, every sentence tagged with its evidence label and reference
- the known unresolved questions, stated as unresolved
- links to `docs/RESULTS.md`

Model-vs-Stack comparison view: where a matching Arena scenario exists, run it side by side with the recording (same world from the World Spec, same start and goal). The "model gap" chips come from `FIDELITY_v1.md`. Extend the CI evidence check to Case File text.

**M3.4 Capstone mission 7, "Why did the robot fail?"** Use Run 15 and Lab 4's return-leg abort. The learner scrubs to the point where localization diverges and connects it to the controller refusing the path. It is MODEL plus STACK, clearly separated. The mission is data, like the other six.

**M3.5 Play.** Ship exactly these five challenges:

| Challenge | Score |
|---|---|
| Beat the planner (draw a path by hand) | Your cost ÷ optimal cost |
| Next node (predict A*'s next 10 expansions) | Exact matches |
| Search the bays | Expected cost of the chosen order ÷ optimal expected cost; never luck |
| Map the arena | F1 and ATE within a path-length budget |
| Case File detective | Find the first divergence in a recording, within a stated tolerance |

Scoring rules:

- Every score is broken down on screen into its named metrics.
- Star thresholds come from reference algorithms and are published in `docs/v2/CHALLENGES.md`.
- Computation is measured in expansions within one implementation, never wall time.
- Personal bests are stored locally, with every storage access wrapped in try/catch, and the page works without storage.
- Challenge-a-friend links carry spec hash plus input log and reproduce the run exactly.

**M3.6 Score verification prototype.** `coco verify <link-or-file>` re-simulates a submission under Pyodide-in-Node and recomputes its score.

- Run it on 100 generated submissions across the five challenges. Every recomputed score must equal the browser's.
- No server, no accounts, no leaderboard.

**M3.7 One app, four modes.** Top-level navigation: Learn · Play · Sandbox · Case Files.

- Sandbox is the free Arena.
- The evidence badge is visible in every mode.
- The Live Stack (simulated) view stays reachable but is not one of the four modes.
- Phone-width layout for every mode.

**M3.8 Launch preparation.** Drafts only; nothing is published.

- `docs/releases/v2.0.md`: release notes with every number traced to `docs/RESULTS.md`.
- A Playwright script that records a 60–90 s demo of the Arena: a goal, the search spreading, the heatmap, a Learn mission moment, a Case File.
- `docs/v2/USABILITY_TEST_M3.md`: five people, covering one challenge, one Case File and mission 7.
- An update to `docs/v2/PHONE_MEASURE.md`.

**M3.9 Measure and decide.**

- Measure the budgets in B.3 (balanced, on AC).
- Write `docs/v2/M3_RESULTS.md` and append to `docs/RESULTS.md`.
- Open a pull request into `main`.

## B.3 Acceptance criteria

| Area | Criterion | Who measures |
|---|---|---|
| Evidence | Every Case File and mission-7 claim has a resolving evidence reference; the CI check covers them | Agent (CI) |
| Adapter | Round-trip and fixture tests pass; every converted Case File cites its source bag checksum | Agent |
| Reproducibility | 100/100 challenge links reproduce exactly across Chromium, Firefox and WebKit; `coco verify` matches 100/100 scores | Agent |
| Case File loading | Each Case File within budget; first frame ≤ 2 s and seek ≤ 100 ms on emulated 4G after the app is loaded | Agent |
| Regressions | All M2 budgets still met: fps, latency, cold start, the 16 replays, the 22 URL forms | Agent |
| Hygiene | 0 console errors in all modes; phone-width checked; suites and CI green | Agent |
| Phone cold start | A cold visitor sees computation within 10 s on a mid-range phone over mobile data | Gautham |
| Usability | 5 people complete one challenge, open one Case File and explain mission 7's failure, unaided | Gautham |

The public v2 launch happens only after the two Gautham rows pass, and only Gautham publishes it.

## B.4 Scope fence for M3

Not in M3:

- the cloud, accounts, servers, leaderboards (M4 and later)
- challenges beyond the five listed (Lost robot, Gauntlet, Drive it yourself and Trade-off frontier go to `IDEAS.md` for later)
- XP, levels, streaks
- new algorithms (fixes to existing ones only, with tests)
- interactive Stack sessions, or Live changes beyond keeping it working
- RL, multi-robot, VLM
- the robot repo or its frozen packages, beyond reading recordings

Git:

- Work only on `v2/m3-play-casefiles`. Open a pull request; do not merge it. The merge permission covers PR #21 only.
- Do not create releases or tags.

## B.5 Stop and ask Gautham if

- Case Files don't fit the storage budget.
- A recording is missing, or its checksum doesn't match what `docs/RESULTS.md` cites.
- A Case File would need a claim that has no evidence.
- A challenge cannot be scored without rewarding luck.
- Any M2 budget regresses and the cause isn't found within one checkpoint.
- Phone results in STATUS.md fail a budget.
- Any step would require deleting evidence or breaking a public URL.

## Final report (end of every session)

Fill in this report and update `docs/STATUS.md` to match:

```
Part A (first session only): review verdicts summary | fixes made | PR #21 merge SHA | public-site check | post-reboot re-measurement (driver version)
Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements taken (device, power profile, conditions), against M2:
Acceptance criteria: each → met / not met / pending Gautham, with evidence:
Case Files published (count, total size) and any recordings missing or mismatched:
Files removed (full list) and why:
Decisions recorded (ADRs):
Plan-change log entries added:
Deviations from the plan, and why:
Ideas parked in docs/IDEAS.md:
Stop condition hit? which one:
Questions for Gautham:
Next step according to README.md:
```
