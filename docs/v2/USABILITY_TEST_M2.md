# Learn usability test (M2) — for Gautham

M2's usability criterion (M2 prompt, B.3): **5 people new to robotics
complete missions 1, 3 and 5 and explain one computation each, unaided.**
Only Gautham runs it; the agent never marks it done. This page is the script
and the results table. (M1's test is `docs/v2/USABILITY_TEST.md`.)

## Who

Five people who have **not** studied robotics, path planning or computer
science algorithms, and have not seen COCO Lab before. They may be the same
kind of people as M1's five, but not the same people. Record each one's
background in a few words.

## Setup (before each person)

- A laptop (or the person's own phone), a **new private tab** per person,
  opened on Learn: `https://gauthamcodes.github.io/coco-labs/?view=learn`
  after the M2 merge, or the local build (`docs/v2/PHONE_MEASURE.md`, step
  B, with `?view=learn`).
- A timer and paper. No screen recording unless they agree to it.

## The script (read it word for word)

> "This page teaches how a robot finds its way, through short missions. I'll
> ask you to do three of them and then stay quiet — I can't help you, but
> please think out loud. There are no wrong answers; we're testing the page,
> not you.
>
> Please do **mission 1**, then **mission 3**, then **mission 5**, from the
> first step to the last. In each one, when the page asks you to try
> something in the Arena, try it. At the end of each mission, tell me in your
> own words what one of the pictures the robot drew was showing."

Start the timer when you finish reading. **Do not** point, hint, or answer
questions; if asked, say "do whatever you think makes sense". There is no
time limit; record how long each mission took.

## What counts

A mission is **completed** when the person reaches its last beat
(Challenge, a stub until M3) having made a prediction on the Predict beat
and opened the Arena from at least one beat that offers it.

The **computation** they explain, one per mission (any one of these, in any
words):

| Mission | Counts as explained if they say something equivalent to… |
|---|---|
| 1 How does a robot find a path? | the coloured cells are the places the planner **looked at before choosing** the route (ideally: in that order); A* looks at fewer than Dijkstra for the same route |
| 3 How does a robot know where it is? | the cloud of dots is the robot's **guesses** of where it might be, and it **shrinks / follows** as the scans fit; or: after being moved without being told, the guesses are in the wrong place until some are thrown elsewhere |
| 5 How does it avoid things? | the fan of lines is the **moves the controller tried** (or could make) in the next second, and it drives the best one; or: the robot stopped because **every** option was blocked |

Saying only "that's the path" or "that's the robot" does not count. A
person passes if they complete all three missions **and** explain one
computation in each, unaided. The criterion is met only if all five pass.
Report the result either way: a miss is a result, and its notes are what M3
needs.

## Results

| # | Background | Device / browser | M1 time | M1 explained (their words) | M3 time | M3 explained (their words) | M5 time | M5 explained (their words) | Pass? | Where they got stuck |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | | |
| 2 | | | | | | | | | | |
| 3 | | | | | | | | | | |
| 4 | | | | | | | | | | |
| 5 | | | | | | | | | | |

Date: ______ Site version (commit, or "public site, date"): ______

Also note, per person: did they open the "Model gap" chips? Did they use the
Arena's "Back to the mission" link? Did any label (MEASURED, TESTED,
SIMULATION RESULT, SIMPLIFIED MODEL, ASSUMPTION, UNRESOLVED) confuse them?

## Afterwards

Send back the table and the notes. The agent records them in
`docs/RESULTS.md` as **measured by Gautham** (evidence class MODEL: it tests
the page, not a robot), quotes the words people used, and turns every "where
they got stuck" into a line in `docs/IDEAS.md` for the milestone that fixes
it. Nothing is closed on your behalf.
