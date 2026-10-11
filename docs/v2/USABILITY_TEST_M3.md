# Play, Case Files and mission 7: usability test (M3), for Gautham

M3's usability criterion (M3 prompt, B.3): **5 people complete one challenge,
open one Case File and explain mission 7's failure, unaided.** Only Gautham
runs it; the agent never marks it done. This page is the script and the
results table. (M2's test is `docs/v2/USABILITY_TEST_M2.md`.)

## Who

Five people who have **not** studied robotics and have not seen COCO Lab
before: not M1's or M2's testers. Record each one's background in a few
words.

## Setup (before each person)

- A laptop or the person's own phone, with a **new private tab** for each
  person, opened on the landing page:
  `https://gauthamcodes.github.io/coco-labs/` after the M3 merge, or the
  local build (`docs/v2/PHONE_MEASURE.md`, step B).
- A timer and paper. No screen recording unless they agree to it.

## The script (read it word for word)

> "This site shows how a robot finds its way: it has four parts, named at the
> top of the page. I'll ask you to do three things and then stay quiet: I
> can't help you, but please think out loud. There are no wrong answers;
> we're testing the site, not you.
>
> First, in **Play**, finish any one challenge and get a score.
> Second, in **Case Files**, open any one recording and watch it.
> Third, in **Learn**, do mission 7, 'Why did the robot fail?', from the first
> step to the last. At the end, tell me in your own words why the robot
> failed."

Start the timer when you finish reading. **Do not** point, hint, or answer
questions. If asked, say "do whatever you think makes sense". There is no time
limit; record how long each part took.

## What counts

| Part | Completed when… |
|---|---|
| One challenge | a score is on screen with its stars and metrics (any challenge, any level, any stars) |
| One Case File | a recording has been opened and played or scrubbed, in the Case Files view or the Arena |
| Mission 7 | the person reached its last beat, having predicted on the Predict beat and opened at least one Case File from a beat |

**Mission 7's failure counts as explained** if they say something
equivalent to: *the robot was wrong about where it was* (its belief or its
estimate was somewhere else), *so the controller refused / could not follow a
good path*. For example: "it thought it was in the wrong place, so the path
didn't make sense to it." Neither "the robot broke" nor "the path was bad"
counts.

A person passes only if they complete all three parts **and** explain the
failure, unaided. The criterion is met only if all five pass. Report the
result either way: a miss is a result.

## Results

| # | Background | Device / browser | Challenge (which, stars) | Time | Case File (which) | Time | Mission 7 time | Failure explained (their words) | Pass? | Where they got stuck |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | | |
| 2 | | | | | | | | | | |
| 3 | | | | | | | | | | |
| 4 | | | | | | | | | | |
| 5 | | | | | | | | | | |

Date: ______ Site version (commit, or "public site, date"): ______

Also note, for each person:
- Did they find the four modes at the top?
- Did they notice the MODEL / STACK badge, and say what it meant?
- Did they use "Copy a challenge link"?
- Did any label (MEASURED, SIMULATION RESULT, SIMPLIFIED MODEL,
  UNRESOLVED…) confuse them?

## Afterwards

Send back the table and the notes. The agent records them in
`docs/RESULTS.md` as **measured by Gautham** (evidence class MODEL: it tests
the site, not a robot), quotes the words people used, and turns every "where
they got stuck" into a line in `docs/IDEAS.md` for the milestone that fixes
it. Nothing is closed on your behalf.
