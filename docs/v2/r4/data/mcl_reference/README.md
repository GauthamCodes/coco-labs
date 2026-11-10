# R4 Part A · the MCL reference on loc-global-20 and loc-kidnap-20 — MODEL (TESTED)

Gautham (2026-11-10): add a stronger localisation reference to show whether the suites can be solved; label it a
reference (never ranked); keep the 60-particle built-ins' 0/40 and 0/60 as visible negative baselines; report the
numbers honestly whatever they are.

**Configuration.** MCL with augmented random-particle injection, **2,000 particles, 24 beams** (the built-ins use 60
particles, 12 beams), the R3.2 baselines' scenarios exactly: the public suite and the reference held-out draw
(`tools/r3/mcl_reference.py`; laptop i5-13420H, 8 workers, AC; 2026-11-10/11).

| suite | public | held-out | 60-particle built-ins (R3.2) |
| --- | --- | --- | --- |
| loc-global-20 | **1/20** localised (18 timeouts, 1 not localised) | **1/6** | 0/40 |
| loc-kidnap-20 | **0/20** (19 timeouts, 1 not localised; one run recovered after the kidnap but did not end localised) | **0/6** | 0/60 |

**Verdict: the reference does NOT show these suites are solvable in the model.** Larger clouds and other filter
settings were tried first on g001 (2,000 and 5,000 particles; 12 and 24 beams; the textbook product score; resampling
on N_eff; sigma 0.3): every one timed out 9-22 m from the truth.

**Why (diagnosed on g001, 2,000 particles, 1,000 ticks; INFERENCE beyond what was logged):** the robot drives on its
belief from tick 0. With the belief 9-19 m wrong it drove 18.5 m, touched an obstacle at about tick 650 and never
moved again; the filter got no new views. The same closed-loop failure was measured for kidnaps in the Arena
(`where-it-is/arena-kidnap-closed-loop`: 0/20 with and without injection, where the open-loop Sketch recovered 18/20).
The suites measure localisation while driving on the estimate; a filter alone cannot win them unless the robot stops
or explores until it is localised. That is a question for the suite design (Gautham), not a filter setting.

Leaderboard: `leaderboard/results/loc-{global,kidnap}-20/mcl_reference/` (`tools/r2/leaderboard.py mcl-reference`),
shown pinned, greyed and unranked with a one-line note.
