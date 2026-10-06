# Lab 4 — Search

> **Try it:** <https://gauthamcodes.github.io/coco-labs/?view=search>
> (DRAFT — the deploy line is written when it is deployed). Phase 5 of
> `docs/ROADMAP.md` (P0.4).

Labels used here, as everywhere in this repository: **(measured)** was
produced by a run in Phase 5 and is recorded with its command, sample count
and evidence path; **(derived)** was computed from recorded evidence or from
the robot's own map; **historical** is an earlier, documented result kept as
it was; **unverified** was not observed; **assumed** is a model parameter
nobody measured. **Sketch** results are coco_lab's MODEL, not the robot.

## 1. What the lab teaches

**Where should the robot look next, given what it knows?**

Until Phase 5, COCO's autonomous mode was TOLD where the target was:
`resolve_lane()` turned the colour into a bay (the episode's region map, or
with none, the frozen `lane_for_colour()` table), and the robot drove
straight there. Lab 4 takes that away. The robot is told one word — a
colour — and must find the target itself.

What it knows (all of it robot-available, none of it the answer):

| it knows | where it comes from |
|---|---|
| the four bays, and for each the pre-ramp pose, the ramp, the platform, the exit | `coco_config.robot.TARGET_REGIONS` — static world geometry |
| what it costs to drive between them | coco_lab's own A* on the robot's own Nav2 map, inflated by the robot radius (derived; `test_regionsearch.py::test_the_arena_travel_table_is_coco_labs_astar_on_the_nav2_map`) |
| what a look costs | up the ramp to the end of the climb and back down it: 2 × (2.95 − 0.5) = 4.9 m (derived) |
| how often its camera finds a target that is there | d = 0.9 — **assumed**, not measured (`mission_search.DEFAULT_DETECTION`); the matrix counts what happened |
| where the target is | nothing: a **uniform** prior. The frozen colour→bay table would be the told answer by another name |

The platform is invisible from the flat — the crest hides it
(`target_finder`'s docstring) — so every look is a climb, and a miss is
expensive. That is what makes the order matter.

**The model** (`coco_lab/coco_lab/regionsearch.py`, standard library only):

- **Belief** over the bays; the target is in exactly one.
- **Bayes on a miss:** p_i ← p_i (1 − d) / (1 − p_i d), every other bay
  rescaled. With d < 1 a searched bay keeps a little belief — a miss is
  evidence, not proof.
- **Expected search cost** of a one-pass order:
  E = Σ_k P_k C_k + (1 − Σ_k P_k) C_last, P_k = p d of the k-th bay, C_k the
  metres driven by then; a search that finds nothing drives the whole order.
- **The robot's policy** costs EVERY remaining order exactly (at most 8! =
  40,320) and takes the cheapest's first bay, re-planned after every look;
  ties go to the lower bay index. Teaching policies beside it: nearest
  first, most likely first, and the learner's own order.

**What the arena teaches** (derived, the travel table above):

| d | the robot's order | expected | nearest first | most likely first |
|---|---|---|---|---|
| 1.0 | bay_3, bay_2, bay_1, bay_4 (= nearest first) | 28.45 m | 28.45 m | 30.48 m |
| 0.9 (the mission) | **bay_3, bay_4, bay_2, bay_1** | **30.45 m** | 30.83 m | 32.26 m |

With a perfect camera, nearest-first is optimal here. With one that can
miss, it is beaten: a search that finds nothing drives the whole tour, so
the tour's length starts to count, and the robot swaps bay_2 for bay_4
(`test_regionsearch.py::test_the_arena_order_when_the_camera_can_miss_is_not_nearest_first`).
If every bay cost the same to reach from anywhere, "most likely per metre
first" (the index rule) would be optimal —
`::test_index_rule_is_optimal_when_costs_do_not_depend_on_order`, 1,000
problems against brute force. COCO's bays do not, which is why the robot
enumerates.

## 2. The mission, searching

`mission.launch.py search:=true` is the default since Phase 5
(`search:=false` is the told mission, exactly as measured before it). The
state machine (`coco_mission/scripts/mission_states.py`) gains four states
around the proven fetch:

```
LOCALIZE -> SELECT_SEARCH_REGION -> NAVIGATE_TO_RAMP -> ALIGN_FOR_CLIMB -> CLIMB
  -> VERIFY_CLIMB -> SURVEY_REGION --found--> STOW_ARM -> ... -> COMPLETE
                         |
                       miss -> MARK_REGION_SEARCHED -> LEAVE_REGION
                                  -> SELECT_SEARCH_REGION (bays left)
                                  -> RETURN_HOME -> ABORT SEARCH_EXHAUSTED (none left)
```

- **SELECT_SEARCH_REGION** asks coco_lab (`mission_search.SearchSession`)
  for the next bay. It reads the search's own state — no pose, no colour,
  no perception line (`test_mission_search.py::test_the_selection_check_reads_only_the_search_state`).
- **SURVEY_REGION** looks for 20 s. A find is target_finder's `found=1` for
  the requested colour; its base_footprint point is recorded. A miss must
  rest on ≥ 10 fresh perception lines for that colour — **silence is not a
  miss** (`PERCEPTION_SILENT`, never evidence).
- **MARK_REGION_SEARCHED** applies Bayes and marks the bay. A miss is an
  observation, not a failure: it never enters RECOVERY.
- **LEAVE_REGION** backs down the ramp it climbed (`/ramp/retreat`, a new
  scripted reverse in ramp_driver, on its existing `/cmd_vel_rl`, mode
  `rl`). The forward descent would cross a deck that still holds another
  colour's target. A grasp given up after a find leaves the same way.

**The anti-cheat boundary**, on the existing EpisodeSpec seam, not a new
mechanism: a searching launch hands the robot `search_mission_inputs(spec)`
— `task_view()`'s colour and nothing else. The region map is empty for both
nodes whatever the manifest says (and a searching plan refuses one);
ramp_driver in search mode ignores the colour and holds the climb to the bay
the search chose (`/mission/search_region`); target_finder's `lane=` field
(the told lane) is never read; the target's final pose is perception's,
through approach_server, as before. The manifest is never a fallback.

**The Live autonomous mode** reads `/mission/search` (via coco_web's
additive `mission.search` block): its label says "the robot discovers the
target" only when the running mission reports `mode=discover`; a told stack
is labelled told, and one that reports nothing gets no claim either way
(`lab_web/test/live.test.ts`). The search is shown as it happens.

## 3. Claims and their evidence

| claim | evidence |
|---|---|
| Bayes' rule, exactly | `coco_lab/test/test_regionsearch.py::test_update_is_bayes_rule_against_the_enumerated_joint` (1,000 problems, brute-force joint), `::test_a_miss_lowers_the_searched_region_and_keeps_the_others_ratios`, `::test_a_find_is_certain_and_a_perfect_miss_is_proof` |
| the expected cost is what it says | `::test_plan_cost_equals_the_enumerated_expectation` (every truth and detection outcome enumerated) |
| the robot's order is optimal | `::test_the_robot_order_is_no_worse_than_any_other_order`, `::test_candidate_costs_rank_the_policy_choice_first`, `::test_the_robot_plan_is_its_optimal_order_and_needs_no_truth` |
| the index rule, and where it stops applying | `::test_index_rule_is_optimal_when_costs_do_not_depend_on_order`; the arena counterexample `::test_the_arena_order_when_the_camera_can_miss_is_not_nearest_first` |
| negative search: A, then B, then found in C, each miss marked first | `::test_negative_search_finds_it_in_the_last_region_checked`; the mission `coco_mission/test/test_mission_search.py::test_a_then_b_then_found_in_c` |
| giving up after A fails the challenge | `test_regionsearch.py::test_giving_up_after_the_first_region_fails_the_challenge`; the mission `test_mission_search.py::test_aborting_after_the_first_bay_fails_with_nothing_found`, `::test_a_given_order_is_followed_and_a_short_one_ends_exhausted` |
| a policy cannot see the truth | `test_regionsearch.py::test_no_field_a_policy_reads_can_hold_the_truth`, `::test_choices_depend_on_observations_not_on_where_the_target_is`, `::test_the_truth_is_read_on_one_line_only`, `::test_regionsearch_imports_nothing_that_knows_the_world` |
| the robot is told the colour and nothing else | `coco_sim/test/test_episode_search.py` (all: corrupted manifest, moved target, 40 permutations, no coordinate or region in the inputs); `test_mission_search.py::test_searching_an_episode_sets_the_colour_and_no_region_map`, `::test_moving_the_target_launches_the_same_search`, `::test_a_searching_plan_refuses_a_region_map`, `::test_the_plan_holds_no_lane_until_the_search_chooses` |
| the choice ignores the pose, the colour and the told-lane field | `test_mission_search.py::test_the_ground_truth_pose_does_not_change_the_choice`, `::test_the_first_bay_does_not_depend_on_the_colour`, `::test_the_told_lane_on_the_perception_line_is_never_read` |
| discovery is perception's | `test_mission_search.py::test_a_then_b_then_found_in_c` (the recorded point is target_finder's); `::test_lines_for_another_colour_do_not_count_toward_a_miss` |
| silence is not a miss | `::test_a_survey_with_no_perception_lines_is_not_a_miss`, `::test_silence_twice_leaves_by_the_ramp_and_aborts_at_home` |
| leaving never crosses the deck | `::test_every_bay_empty_comes_home_and_says_so` (no `/ramp/descend`), `::test_a_grasp_given_up_after_discovery_leaves_by_the_ramp`; `coco_rl/test/test_ramp_driver_search.py` |
| a recorded search is the policy's | `coco_lab/test/test_searchbundle.py::test_a_recording_that_disagrees_with_the_policy_is_refused`; every Gazebo run is rebuilt by `replay_search` |
| the page draws, coco_lab decides | `lab_web/tools/test_tools.py::test_lab_web_src_has_no_search_implementation` (belief updates and order costing added for Lab 4); worker glue `lab_web/tools/test_search_glue.py` |
| the Live label follows the running mission | `lab_web/test/live.test.ts` ("says the robot discovers the target only when the mission says it searches" and the told/unknown cases) |

## 4. Measured

### 4.1 The searching mission in Gazebo (measured, 16 runs)

`docs/data/p05_matrix.sh` (16 runs, `docs/data/p05_search_run.sh` each: a
fresh headless simulator, never `--fast`, ROS domain 64), robot code at
`d78a1d8`; evidence `docs/data/lab4/` (`results.json`, `runs/`, the replay
bundle), rebuilt by `python3 docs/data/p05_evidence.py
~/coco_lab_runs/lab4/matrix`. Every run passed every runner check,
including **both robot nodes holding an EMPTY region map, the executive
`search=true`, ramp_driver `search_mode=true`, and no parameter naming a
manifest** — what the robot was given was the colour.

| run | episode | asked | truth (manifest) | order given | bays looked | found (look) | mission | lift | home error | reloc. | recov. | sim s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1_fixed_red | fixed 0 | red | bay_1 | policy | bay_3, bay_4, bay_2, bay_1 | bay_1 (4) | COMPLETE | yes | 0.016 m | 0 | 0 | 410.6 |
| A2_fixed_green | fixed 0 | green | bay_2 | policy | bay_3, bay_4, bay_2 | bay_2 (3) | COMPLETE | yes | 0.074 m | 0 | 0 | 314.4 |
| A3_fixed_blue | fixed 0 | blue | bay_3 | policy | bay_3 | bay_3 (1) | COMPLETE | yes | 0.079 m | 0 | 0 | 145.0 |
| A4_fixed_yellow | fixed 0 | yellow | bay_4 | policy | bay_3, bay_4 | bay_4 (2) | COMPLETE | yes | 0.169 m | 0 | 0 | 229.6 |
| B1_colours_s5_red | colours 5 | red | bay_1 | policy | bay_3, bay_4, bay_2, bay_1 | bay_1 (4) | COMPLETE | yes | 0.028 m | 0 | 0 | 414.1 |
| B2_colours_s1_red | colours 1 | red | bay_2 | policy | bay_3, bay_4, bay_2 | bay_2 (3) | **ABORT RETURN_FAILED** | yes | — | 0 | 3 | 305.5 |
| B3_colours_s7_red | colours 7 | red | bay_3 | policy | bay_3 | bay_3 (1) | COMPLETE (after a relocalisation) | yes | 0.047 m | 1 | 1 | 155.9 |
| B4_colours_s2_red | colours 2 | red | bay_4 | policy | bay_3, bay_4 | bay_4 (2) | COMPLETE | yes | 0.060 m | 0 | 0 | 239.1 |
| C1_green_stop_after_bay3 | fixed 0 | green | bay_2 | bay_3 | bay_3 | no | **ABORT SEARCH_EXHAUSTED** (as designed) | — | — | 0 | 0 | 85.2 |
| C2_green_nearest | fixed 0 | green | bay_2 | bay_3,bay_2,bay_1,bay_4 | bay_3, bay_2 | bay_2 (2) | COMPLETE (after a relocalisation) | yes | 0.060 m | 1 | 1 | 239.3 |
| C3_green_most_likely | fixed 0 | green | bay_2 | bay_1,bay_2,bay_3,bay_4 | bay_1, bay_2 | bay_2 (2) | COMPLETE (after a relocalisation) | yes | 0.022 m | 1 | 1 | 248.7 |
| C4_green_reverse | fixed 0 | green | bay_2 | bay_4,bay_1,bay_2,bay_3 | bay_4, bay_1, bay_2 | bay_2 (3) | COMPLETE | yes | 0.095 m | 0 | 0 | 343.6 |
| D1_positions_s1_red | positions 1 | red | bay_2 | policy | bay_3, bay_4, bay_2 | bay_2 (3) | COMPLETE | yes | 0.109 m | 0 | 0 | 320.2 |
| D2_positions_s2_red | positions 2 | red | bay_4 | policy | bay_3, bay_4 | bay_4 (2) | COMPLETE | yes | 0.151 m | 0 | 0 | 232.2 |
| D3_positions_s3_red | positions 3 | red | bay_2 | policy | bay_3, bay_4, bay_2 | bay_2 (3) | COMPLETE | yes | 0.044 m | 0 | 0 | 316.1 |
| D4_positions_s4_red | positions 4 | red | bay_2 | policy | bay_3, bay_4, bay_2 | bay_2 (3) | COMPLETE | yes | 0.102 m | 0 | 0 | 317.8 |

"sim s" is simulator seconds from LOCALIZE to the terminal state (from each
run's rosbag, `docs/data/p05_bagtimes.py`). Home error is ground truth at
COMPLETE vs home (−2, 0) — scoring only. Lift = VERIFY_GRASP passed
(grasp_server's `lifted=1`, which checks the object moved UP).

Derived from the table (16 runs: an inventory, **not a rate**):

- **14 COMPLETE, 2 ABORT.** Of the 14, 11 had nothing go wrong and 3 (B3,
  C2, C3) relocalised once on the return home (`SCAN_DISAGREES`, one spin,
  recovered). The aborts: **B2 `RETURN_FAILED`** and **C1
  `SEARCH_EXHAUSTED`** — the deliberate "give up after the first bay" order.
- **Negative search, physically:** in 14 of 16 runs the target was not in
  the first bay looked at; A1 and B1 searched bay_3, bay_4 and bay_2 and
  found red in the LAST bay. Every miss was marked before the find.
- **Every look agreed with the truth:** 39 looks, 24 misses and 15 finds;
  no find in a bay without the target, no miss in the bay with it. The
  assumed d = 0.9 was not contradicted (15 of 15 finds where the target
  was) — a count, not a measurement of d.
- **The real robot chose what coco_lab chooses:** all 16 recorded searches
  are rebuilt from their looks alone by `replay_search` and reproduce byte
  for byte; a recording whose bay differed from the policy's choice would
  have been refused.
- **Leaving:** 24 of 24 `/ramp/retreat` segments reached their goal; none
  entered RECOVERY. Lift verified 15 of 15. Home error 0.016–0.169 m over
  the 14 completed runs.
- **The B2 failure is localisation, not search.** Red was found in bay_2 and
  lifted; on the return, the planner was planning from map (6.52, 2.25)
  (world (4.52, 2.25)) while ground truth was world (6.66, −2.00) — 4.8 m
  apart, about one bay pitch across. The localisation monitor's verdict
  there was `UNKNOWN`, so nothing relocalised; three plans found no path and
  the mission aborted. This is the live limitation already recorded
  (severe confident AMCL divergence is not reliably recovered). The
  bay-pitch offset suggests aliasing between identical bays; **not
  attributed**. The return after bay_2's descent: B2 failed, C2 and C3
  relocalised and recovered, A2, C4, D1, D3, D4 were clean.

**Search orders on one placement (rule 6: FIXED, green in bay_2, same
world, same seed — only the order differs):**

| order | runs | looks | sim s to the end | expected cost of the order (derived, coco_lab) |
|---|---|---|---|---|
| the robot's (bay_3, bay_4, bay_2, bay_1) | A2 | 3 | 314.4 | 30.45 m |
| nearest first (bay_3, bay_2, …) | C2 | 2 | 239.3 (one relocalisation) | 30.83 m |
| most likely first (bay_1, bay_2, …) | C3 | 2 | 248.7 (one relocalisation) | 32.26 m |
| bay_4, bay_1, bay_2, bay_3 | C4 | 3 | 343.6 | 38.42 m |
| bay_3 only — stop after A | C1 | 1, not found | 85.2 | 8.67 m, but P(find) 0.225: the challenge FAILED |

On this one placement two simpler orders beat the robot's. That is the
lesson, not a contradiction: the robot minimises the EXPECTED cost over
where the target might be (it does not know), and on this bay its order
looks third. One placement per order: not a comparison of policies.

**Void:** `B3_colours_s7_red.void-1` — the runner's `ros2 service call
/mission/start` could not join DDS domain 64 ("Failed to find a free
participant index"): seven `ros2 bag record` processes from earlier runs had
outlived them (a backgrounded job ignores SIGINT). Harness, not robot; the
runner now stops them with SIGTERM (`3ddfe74`) and B3 was rerun. Those
leaked recorders also recorded later runs into earlier runs' bags; each
run's timeline is cut at its own first terminal state.

### 4.2 Gazebo smoke runs before the matrix (not results)

`smoke1_fixed_yellow`: died at launch on the `origins` defect (§7).
`smoke2_fixed_yellow`: searched bay_3, saw blue, backed down (retreat 0.003 m
drift), found yellow in bay_4, grasped — then the machine rebooted
mid-descent. Incomplete; kept in `~/coco_lab_runs/lab4/`.

### 4.3 The site (measured, headless Firefox, local build)

`python3 lab_web/tools/browser/check.py <site> <out> search search_phone`
on `vite preview` of the build: the Lab 4 flow end to end — order, predict,
place the target in bay_1, reveal (a cold Pyodide start + coco_lab: 17.6 s
wall, coco_lab's own part 22 ms for 4 searches), play to the end, the belief
table, the Replay of A1 with its FSM timeline and truth toggle, the evidence
tab; **0 console errors**; at 390 px no tab overflows. Re-run with the full
16-run Replay (`e25f9c8` + rebuilt catalog): 0 console errors on Lab 1's
smoke check and Lab 4's two scenarios; the Pyodide reveal 8.7 s wall
(coco_lab 8 ms); no overflow at 390 px. Public-site numbers: §4.5.

### 4.4 Tests

`COCO_WS=~/coco_search_ws ROS_DOMAIN_ID=77 scripts/run_all_package_tests.sh`
(a copy overlay of `e25f9c8`; the worktree's path has parentheses) on a
quiet machine after the matrix: **2,975 passed, 0 failed, 0 skipped**
(Phase 4 closed at 2,848).

| package | Phase 4 | now | what is new |
|---|---|---|---|
| coco_config | 93 | 93 | |
| coco_sim | 280 | **323** | `test_episode_search.py`: what a searching mission is given |
| coco_mission | 344 | **371** | `test_mission_search.py`: the search states, anti-cheat, the launch path |
| coco_web | 857 | **863** | `mission.search`, the four states and five reasons, the default-launch parameters |
| gazebo_models | 229 | 229 | |
| coco_rl | 241 | **251** | `test_ramp_driver_search.py` (retreat, search-mode datum), Docker/CI build lists |
| coco_perception | 139 | 139 | (unchanged — target_finder untouched) |
| coco_moveit_config | 12 | 12 | |
| custom_teleop | 75 | 75 | |
| coco_lab | 492 | **533** | `test_regionsearch.py` (1,000-problem properties), `test_searchbundle.py` |
| coco_lab_ros | 86 | 86 | |

The first full run of the phase (at `3e043c1`) failed coco_lab's
`test_flake8` and `test_pep257` on three formatting findings in a test
helper (`golden_search_bundles.py`), fixed in `e25f9c8`; the rerun above is
complete. `lab_web`: vitest 275 → **286**; tools pytest 95 → **104**;
`tsc`, `vite build` and `check_dist` clean. CI on PR #14: green after two
fixes (coco_lab not built by the ROS CI; a static test that still expected
the old `origins` text).

### 4.5 On the public site

(Written after the deploy.)

## 5. Not verified

- **A real robot.** Everything here ran on the real stack in GAZEBO.
- **d.** 0.9 is assumed; 15 of 15 finds is a count on 16 runs, not a
  detection rate, and the lighting, target sizes and approach are
  Gazebo's.
- **Rates of anything.** 16 runs: COMPLETE 14 of 16 is an inventory.
- **Why B2's localisation diverged.** Measured, not attributed.
- **A real phone, Safari, Chrome.** Headless Firefox only.
- **The Docker image with coco_lab.** The Dockerfile now builds coco_lab
  (statically tested); the image was not rebuilt this phase.
- **Live mode with a browser attached.** The label logic is unit-tested
  against the mission's `/mission/search` line and the line itself was
  recorded in every matrix run; a live browser session on a searching stack
  was not driven this phase.

## 6. Known limitations

- **The search domain is COCO's four bays**, and the prior is uniform. A
  look costs a climb, because the crest hides the platform from the flat.
- **One pass.** The real mission surveys each bay once; with d < 1 a miss
  is not proof, but a second pass is a Sketch option only.
- **The survey is a fixed 20 s window** from the end of the climb; a target
  the camera cannot see from there (e.g. far off the bay's centreline)
  would be missed — the POSITION episodes stay within ±0.030 m across the
  bay (measured envelope), so this was not exercised.
- **Leaving backs down the ramp** (`/ramp/retreat`): 24 of 24 here; a new
  scripted motion with no other evidence.
- **Localisation on the return** is the weak leg (B2, and three
  relocalisations), as before Phase 5.
- **Travel costs are the robot's map**, A* inflated by 0.20 m; Nav2's real
  paths differ (the matrix's sim seconds are the measured cost).
- **The told mission still exists** (`search:=false`) and is what every
  measurement before Phase 5 used.
- **Sketch ≠ the robot:** Lab 4's Sketch samples looks with the robot's d;
  it does not simulate climbing, perception or localisation.

## 7. Found and fixed during the phase (each measured)

- **The default `mission.launch.py` could not start** since `c921ec4`
  (2026-10-02): `platform.launch.py` passed `origins` (default `*`) as a bare
  substitution and launch_ros YAML-parses it (`*` is an alias token). Every
  default launch — including the Live tab's local stack — died before any
  node ran. Fixed (`180c9f1`), with a test that evaluates the parameters as
  launch does.
- **The ROS CI did not build coco_lab** (PR #14's first CI run), and a
  static test still expected the old `origins` text; both fixed.
- **The runner leaked bag recorders** (see "Void" above).
- **A given order that ran out was logged as "every bay searched"** (C1);
  now "every bay in the given order searched" (`3e043c1`).
