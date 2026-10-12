# The consolidated usability test (M4) — for Gautham

**Decision D5** (2026-10-11): one five-person test at the end of M4 replaces M1–M3's
usability tests. Its criterion is README §7's M4 row, verbatim in substance:

> 5 people new to robotics, unaided: at least **4 of 5** drive to a marked spot within
> **60 s**, **point at the planner's search in 3D**, **explain the top-down heatmap**, and
> **say why they won or lost against the ghost**. "Felt like a game" and "I could see
> what the robot was computing" both **median 4/5 or more**. **Nobody** reports motion
> discomfort.

Only Gautham runs it; the agent never marks it done. This page is the script and the
results table. M1's page ([`USABILITY_TEST.md`](USABILITY_TEST.md)) stays as the record
of what M1 asked; this one supersedes it.

## Who

Five people who have **not** studied robotics, path planning or computer-science
algorithms, and have not seen COCO Lab before. A mix of devices is welcome (at least
one on a phone, if the phone rows pass). Record each one's background in a few words.

## Setup (before each person)

- The site fresh in a **new private window** per person (a first visit: the 3D landing,
  the MODEL · kinematic badge): `https://gauthamcodes.github.io/coco-labs/` after the M4
  merge, or the M4 preview (`lab_web/tools/preview_phone.sh start`).
- Open these in tabs, in this order, without explaining them:
  1. **Drive:** `…/?view=arena&play=race-the-ghost&pl=warm-up&camera=follow&seed=1` (the
     flag is the marked spot; the race panel is visible but not explained);
  2. **Search:** `…/?view=arena&world=v2` (the plain 3D Arena);
  3. **Race:** the same as tab 1, reloaded for the race proper.
- A timer, paper, the two rating questions printed. No screen recording unless they agree.

## The script (read it word for word)

> "This is a page about how a robot moves and plans. I'll give you four small tasks and
> then stay quiet — I can't help, but please think out loud. There are no wrong answers;
> we're testing the page, not you."

**Task 1 (tab 1).** "Drive the robot to the flag." Start the timer when you finish the
sentence; stop it when the panel says the robot reached the flag, or at **60 s**.

**Task 2 (tab 2).** "Send the robot to the far platform. While it decides how to get
there, show me — point at the screen — where you can see it working that out."

**Task 3 (tab 2, after it arrives).** "Now look at it from straight above, and tell me
what the coloured area shows." (If they ask how to look from above: "do whatever you think
makes sense".)

**Task 4 (tab 3).** "Race the robot's ghost to the flag. Afterwards, tell me why you won
or lost."

**Then ask, and write down the number (1 = not at all, 5 = completely):**

1. "It felt like a game." 1 2 3 4 5
2. "I could see what the robot was computing." 1 2 3 4 5
3. "Did anything on screen make you feel dizzy, sick or uncomfortable?" yes / no (and what)

**Do not** point, hint or answer questions during the tasks; if asked, say "do whatever
you think makes sense".

## What counts

| | Passes when… |
|---|---|
| **Drive to the spot** | The robot reaches the flag within 60 s of the instruction, unaided (keys, joystick, a click on the floor — any way). |
| **Point at the search** | In 3D (follow or orbit, not top-down), they point at the spreading search (the frontier and the cells it has visited) and say, in any words, that this is the robot working out its route. Pointing only at the robot or the finished path does not count. |
| **Explain the heatmap** | In top-down they say something equivalent to *the coloured area is where the planner looked before choosing the route*, ideally that the colour shows the order (dark first, bright last). "That's the path" alone does not count. |
| **Why they won or lost** | Any reason grounded in what they saw: they cut corners, it took a longer way, it slowed or turned on the spot, they hit something, it never hits anything... "It's a computer" alone does not count. |

A person **passes** only with all four. The criterion is met when **at least 4 of 5**
pass, **both** ratings have a median of **4 or more**, and **nobody** answers yes to the
discomfort question. Report the result either way: a miss is a result.

## Results

| # | Background | Device / browser | Flag reached at (s) | Pointed at the search? | Heatmap in their words | Won / lost, and why (their words) | Game (1–5) | Computing (1–5) | Discomfort? | Pass? | Where they got stuck |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | | | |
| 2 | | | | | | | | | | | |
| 3 | | | | | | | | | | | |
| 4 | | | | | | | | | | | |
| 5 | | | | | | | | | | | |

Date: ______ Site version (commit, or "public site, date"): ______

## Afterwards

Send back the table. The agent records it in `docs/RESULTS.md` as **measured by Gautham**
(evidence class MODEL: it tests the page, not a robot), quotes the words people used, and
turns every "where they got stuck" into a line in `docs/IDEAS.md` for the milestone that
fixes it. Nothing is closed on your behalf.
