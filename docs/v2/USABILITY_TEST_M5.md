# M5 usability test · owner-run public-launch gate

Gautham owns this test. It is pending and does not block implementation or the PR.
The pre-design test/phone prerequisite was explicitly waived on 2026-10-14. The
committed pre-M5 blank template stays unchanged; no observations were supplied.

Recruit five people new to robotics who have not seen the app. Use the candidate
build, with a fresh preference profile for each person. Record device/browser,
build SHA, orientation and whether they used keyboard or touch. Do not coach or
explain the three modes before the tasks. Ask permission before taking notes;
record participant codes, not names or personal information.

Say: “Explore this robot app. Please say what you are trying to do.” Then ask:

1. “Start a game.” Time from seeing the title until they enter a game. Pass: at
   least four of five start within 30 seconds, unaided.
2. “In Compare, compare A* with Dijkstra. Explain why A* expanded fewer cells in
   this example.” Record their explanation verbatim, without teaching them first.
   Pass: at least four of five identify guidance toward the goal/admissible heuristic
   reducing work here, without claiming A* is always faster or its path always cheaper.
3. “Find a recorded ROS run in Research and open it.” Pass: at least four of five
   open a recording unaided and do not confuse a MODEL trace with a recorded Stack run.
4. Rate “Looks good” and “Easy to understand”, each from 1 (strongly disagree) to
   5 (strongly agree). Pass: median at least 4/5 for each question.

Also note unexpected scrolling, lost controls, text difficulty, motion discomfort,
phone orientation/full-screen failures and where someone mistakes simulation for
hardware. These observations are design inputs; do not invent their explanations.

| Person | Device / browser / build | Game time / unaided? | A* explanation | Recorded run / unaided? | Looks good | Easy to understand | Observations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | pending | pending | pending | pending | pending | pending | pending |
| P2 | pending | pending | pending | pending | pending | pending | pending |
| P3 | pending | pending | pending | pending | pending | pending | pending |
| P4 | pending | pending | pending | pending | pending | pending | pending |
| P5 | pending | pending | pending | pending | pending | pending | pending |

Gautham records the results and launch decision. The agent may transcribe supplied
results with attribution, but never marks this owner row done on its own. Link the
completed evidence from STATUS, M5_RESULTS and the release draft before public launch.
