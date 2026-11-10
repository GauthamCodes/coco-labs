# R4 prompt (Gautham, 2026-11-10) — saved verbatim

You are continuing COCO Lab (repo GauthamCodes/coco-labs, live at https://gauthamcodes.github.io/coco-labs/). R3 · COCO-Bench v1 and the paper is merged (62096d1) and deployed. This session has two parts:

Part A: finish R3's loose ends.
Part B: build R4 · Learn Course, which turns the site into a real robotics course where you learn by predicting, coding and checking, connected to real ROS 2.

All earlier rules and the standing authority (R3 prompt §0) hold. Save this prompt as docs/v2/r4/R4_PROMPT.md, track progress in R4_STATUS.md (and Part A in the same file), commit [R4.n] and push.

## Part A · R3 loose ends (Gautham's decisions, 2026-11-10: record them in STATUS)

The held-out secret. Set up COCO_HELDOUT_SECRET yourself, so the value is never printed, logged, written to a file or shown in your context.
Generate it inside a single pipeline and pass it straight to gh secret set COCO_HELDOUT_SECRET -R GauthamCodes/coco-labs.
Compute its commitment exactly as ADR 0014 defines it, in the same pipeline, and commit only the commitment.
Prove it works: a verifier run that uses the secret, plus the attack tests.
Then merge Theta*'s v1 claim PR (from 9ca4d58) under the gate, and confirm its held-out results.
Merge PR #37 (the deploy record) when its CI is green.

A stronger localisation reference: yes.
Add an "MCL reference" (for example 2,000 particles with random-particle injection or recovery). It is labelled reference, slow and shown in its own row.
Run it on loc-global-20 and loc-kidnap-20 to show the suites can be solved.
Keep the 60-particle built-ins' 0/40 and 0/60 as visible negative baselines, and report the numbers honestly whatever they are.

Reference rows are never ranked. The waypoint driver (a plan-following reference) and the new MCL reference appear pinned, greyed and unranked on every board, with a one-line note saying what each one is. Only real controllers and localisers get ranks. Fix the other two "looks to judge" items in docs/v2/r3/BEFORE_AFTER.md the same way: by being honest, with the smallest fix.

The missing Gazebo repeats (control and localisation, 2 more repeats): run tools/r3/ros2_queue_r34.sh 2 3 then tools/r3/finalize_r34.py.
Only while the laptop is otherwise free. First check that no other simulator, Isaac Sim, FR3 launch or ~/franka_ws process is running; Gautham uses this laptop for his internship. If it's busy, leave it for the end of the session or overnight, and say so.
Update the model-vs-ROS 2 numbers and the paper's generated macros, then merge and deploy under the gate.

The paper: don't submit anything. Gautham decides; see the report questions.

## Part B · R4 · Learn Course (worktree ~/coco_labs_ws/worktrees/r4, branch v2/r4-learn from the latest main)

Why: COCO Lab now has a game, a Workbench, an Algorithm Studio, a benchmark and a paper. But learners still get seven guided tours and nothing that teaches them by doing and checks whether they understood. R4 builds a real course: free, no account, works on a phone. Every exercise is graded automatically and exactly (because the model is deterministic), and every lesson connects to how real ROS 2 and Nav2 do it, with real recordings as evidence.

### B1. Course structure

Three tracks with clear entry points on the Learn page:

- Explorer (no code, phone-friendly): predict, observe, tune parameters, find the failure.
- Builder (fill-in code): complete one function in the Studio.
- Researcher (full algorithm): write, benchmark, submit to the leaderboard, run in ROS 2.

Modules (extend the seven missions):

1. How does a robot find a path? (BFS, Dijkstra, A*, heuristics, weighted A*)
2. Costmaps and inflation (the Nav2 formula, robot radius, why paths keep their distance)
3. What if the world changes? (replanning, D* Lite)
4. Following a path (pure pursuit, DWA, RPP, MPPI: what each one optimises)
5. Where am I? (odometry drift, particle filters, AMCL, kidnapping)
6. Building a map (occupancy grids, the SLAM chicken-and-egg problem)
7. Avoiding things that move (actors, yielding, safety, STOP and the cmd_vel arbiter)
8. Deciding where to look (search, the colour fetch)
9. Why did the robot fail? (reading a recording, finding the tick where it went wrong)
10. From browser to ROS 2: topics, messages, TF frames, the Nav2 stack, rosbag2, exporting your algorithm as a real node

Each lesson follows one pattern:

- Predict: a multiple-choice or "click where" question before seeing anything.
- Observe: the run, live in GAME, SIM or Compare, with the relevant displays on.
- Explain: a short text (at most about 250 words) plus one diagram.
- Try: an exercise.
- Check: automatic, exact grading.
- In real ROS 2: what the same thing is called and does in Nav2, linked to a real STACK recording or a Gazebo comparison from R3, with its evidence label.

### B2. Exercises and grading

Exercise types:

- predict (multiple choice, or click a cell or tick)
- tune (sliders to reach a target, for example "pass the corridor with clearance ≥ 0.3 m")
- find the failure (pick the tick or event where it went wrong)
- code (fill in a function in the Studio)
- benchmark (meet a target on a mini-suite)

Code exercises use the R2 sandbox and API. Examples:

- write the A* heuristic
- implement Dijkstra
- add inflation
- choose the pure-pursuit lookahead
- write particle-filter resampling
- add a goal tolerance
- make a planner respect a no-go zone

Grading:

- Deterministic: each exercise has public example scenarios plus hidden check scenarios, generated from the exercise seed in the browser. Grading compares exact counts and properties (path optimality ratio, clearance, success, error), never fragile text matching.
- Feedback: clear messages about what failed and where, with a button that opens the failing scenario in Compare.
- Hints: three levels per exercise (nudge → concept → nearly the answer). A reference solution unlocks only after a real attempt, and using it is recorded honestly in progress.
- Misconceptions: each predict question has a written explanation of the common wrong answer.

### B3. Progress and teaching without accounts

- Progress lives in prefs: stars per lesson, the track completed, the hints used. Learners can export and import progress as a file.
- Completion links: finishing a module gives a completion link that encodes the learner's solutions and results. Anyone who opens it can re-verify it in their browser (deterministic re-run). It is labelled "self-verified, not proctored". No server.
- Teacher mode:
  - Assignment links: a chosen set of exercises, an optional deadline label, and an optional name field.
  - A class dashboard: the teacher pastes students' completion links, and the page re-verifies them all in the browser and shows a table (who passed what, hints used), exportable to CSV.
  - Nothing leaves the teacher's browser.
- Privacy: no analytics, no tracking, and names stay only in links the learner chooses to share. State this plainly on the Learn page.

### B4. Content quality

- Every factual claim about ROS 2, Nav2 or algorithms is either backed by an evidence link (a recording, a Gazebo comparison or a test) or cites a real source, checked; anything unverified is marked [CHECK] and listed in the report.
- Diagrams: your own SVGs, colour-blind safe.
- Reading level: plain English for Explorer, with technical terms introduced once each and gathered in a glossary page (ROS 2 terms included).
- Accessibility: WCAG AA; every interactive works by keyboard; screen-reader labels on predict questions.
- Phone: the Explorer track is fully playable on the Nothing Phone (1) in landscape. The Builder and Researcher tracks are readable there, with a note that coding is better on a laptop.

### B5. A small learning study (prepare; Gautham runs it)

Write docs/v2/r4/STUDY.md: a 30-minute protocol for 5–8 friends or students. Module 1 and Module 2: pre-quiz, lessons, post-quiz, and three open questions. Include a printable consent note and an anonymous results template. The site's own checks feed the post-quiz. Gautham runs it; you only prepare it.

### B6. Checkpoints (in this order)

- R4.0 Baseline. Setup, all suites, before screenshots of the Learn page and the tours (desktop and phone).
- R4.1 Lesson engine. The engine and its data format (coco.lesson.v1, ADR 0015). Lesson steps, predict questions, exercise definitions, grading contracts, and hidden check-scenario generation. Unit tests.
- R4.2 Modules 1–2, end to end. Every step works, along with all three tracks and hints. This is the first look checkpoint: commit screenshots and list them for Gautham, but don't wait.
- R4.3 Modules 3–6. All of them, including their "In real ROS 2" sections linked to R3 evidence.
- R4.4 Modules 7–10. Module 10 uses the Studio export to real ROS 2 and links R2's Gazebo results.
- R4.5 Progress and teaching. Progress, completion links with re-verification, teacher mode with the class dashboard, and CSV export.
- R4.6 Glossary and accessibility. The glossary, diagrams, the accessibility audit, and the phone pass (the real Nothing Phone if adb devices lists it, otherwise emulated and labelled).
- R4.7 Grading integrity. For every code exercise: the reference solution passes; at least 3 plausible wrong solutions fail with helpful messages; hidden check scenarios can't be passed by hard-coding the public ones. Also confirm that browser and native grading agree exactly.
- R4.8 Close. After screenshots, BEFORE_AFTER.md, all suites, determinism, parity, security, Play fps unchanged, and R4_RESULTS.md. Ship: open the PR "R4 · Learn Course", self-review it, merge it under the gate, deploy, and run the live smoke test, now including one full lesson with a code exercise passed on the live site.

### Stop and report if

- Any golden or model hash changes unexpectedly.
- A grading check can be passed by a wrong solution you can't fix.
- A lesson would need a claim with no evidence or verifiable source.
- The secret could only be set by exposing its value.
- The live site fails its smoke test and a revert doesn't fix it.

### Final report

- Part A: secret set (commitment SHA, proof run), Theta* v1 merged, #37 merged, MCL reference results (global/kidnap), reference rows unranked, Gazebo repeats (done / pending: why), paper macros updated, deploys and smoke results
- R4 checkpoints done:
- Course: modules, lessons, exercises per type, tracks
- Grading integrity: per code exercise, reference passes / wrong solutions caught / hidden-scenario check
- Progress and teaching: completion-link verification, class dashboard test
- Content: [CHECK] items remaining, glossary size, accessibility result, phone (real or emulated)
- Study: STUDY.md ready
- Tests, determinism, parity, security, Play fps:
- PRs merged, deploys (IDs), live smoke results:
- Questions for Gautham:
- Next step (R5 · World editor, Run it in ROS 2 and Live ROS 2 in Docker):
