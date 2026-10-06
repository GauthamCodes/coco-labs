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

(Filled from `docs/data/lab4/results.json` when the matrix completes.)

## 5. Not verified

(Written with §4.)

## 6. Known limitations

(Written with §4.)
