# Arena usability test (M1) — for Gautham

M1's usability criterion (README M1, B.4): **5 people new to robotics set a
goal and explain the heatmap within 2 minutes, unaided.** Only Gautham runs
it; the agent never marks it done. This page is the script and the results
table.

## Who

Five people who have **not** studied robotics, path planning or computer
science algorithms (a friend, a relative, a classmate from another
department). Not someone who has seen COCO Lab before. Record each one's
background in a few words.

## Setup (before each person)

- A laptop or the person's own phone, with the Arena open fresh:
  `https://gauthamcodes.github.io/coco-labs/?view=arena` (after the M1
  merge), or the local build (`docs/v2/PHONE_MEASURE.md`, step B).
- A **new private tab** per person, so each sees the page as a first visit
  (the recorded demo playing, the MODEL badge).
- A timer. Paper for notes. No screen recording unless they agree to it.

## The script (read it word for word)

> "This is a page about how a robot plans a route. I'm going to give you two
> small tasks and then stay quiet — I can't help you, but please think out
> loud. There are no wrong answers; we're testing the page, not you.
>
> **Task 1.** Make the robot go somewhere you choose.
>
> **Task 2.** When it gets there, tell me in your own words what the
> coloured area on the map shows."

Start the timer when you finish reading. **Do not** point, hint, or answer
questions; if asked, say "do whatever you think makes sense". Stop at
**2:00**.

## What counts

| | Passes when… |
|---|---|
| **Set a goal** | They make the robot plan and drive to a place of their choosing (click / tap on the map, or the keyboard / joystick followed by a goal) without help, before 2:00. |
| **Explain the heatmap** | Before 2:00 they say, in any words, something equivalent to: *the coloured area is where the robot (its planner) looked / searched / tried before choosing the route*, and ideally that colour shows the order (dark first, bright last). Saying only "that's the path" does not count. |

A person passes only if they do **both** within 2 minutes, unaided. The
criterion is met only if **all five** pass. Report the result either way:
a miss is a result, and its notes are what M2 needs.

## Results

| # | Background (a few words) | Device / browser | Goal set at (m:ss) | Heatmap explained at (m:ss) | Their words for the heatmap | Pass? | Where they got stuck |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

Date: ______ Site version (commit or "public site, date"): ______

## Afterwards

Send back the table. The agent records it in `docs/RESULTS.md` as
**measured by Gautham** (evidence class MODEL: it tests the page, not a
robot), quotes the words people used, and turns every "where they got
stuck" into a line in `docs/IDEAS.md` for the milestone that fixes it.
Nothing is closed on your behalf.
