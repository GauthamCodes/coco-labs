# R4.7 · plausible bugs the course's checks do NOT catch (kept, never hidden)

Each file here was written as a "plausible wrong solution" and PASSED its exercise's check. They are not in
`course_wrong/` (whose files must all fail, `test_course.py`), because a check cannot be made to fail them without
failing correct answers too. They are listed in `docs/v2/r4/R4_RESULTS.md`.

| file | the bug | why the check does not see it |
| --- | --- | --- |
| `m1_dijkstra__stop_on_push.py` | stops when the goal is first pushed, not when it is popped | Dijkstra pops in cost order, so the first push of the goal comes from its cheapest-to-reach neighbour; the path differs from the optimum only when a later-popped neighbour has a cheaper final step (straight vs diagonal) by more than its extra cost so far. On the exercise's scenarios (public and hidden) its path cost equalled the reference's every time. A correct answer is "stop on pop"; the lesson text says why. |
| `m1_bench__lethal_only.py` | blocks only lethal cells (254), not inscribed ones (253) | with the planner's inflation cost weight (2.0), an inscribed cell costs about 3x a free one, so the optimal paths on the Depot never enter one: on 6 public + 6 hidden scenarios the bug changed nothing. It would matter with cost weight 0. |

Two answers that meet a target as stated and are therefore NOT wrong (recorded, not here): pure pursuit with a
1.0 m lookahead reaches every corner-route goal without contact (clearance 0.03-0.05 m against the reference's
0.13-0.18 m), and A* with its heuristic weighted x5 meets the benchmark's median target (path ratio 1.005 public,
1.026 hidden).
