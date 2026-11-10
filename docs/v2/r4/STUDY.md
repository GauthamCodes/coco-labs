# R4 · A small learning study (prepared by the agent; Gautham runs it)

**Question.** After 30 minutes with Modules 1 and 2 of the Learn course, do learners answer more questions about
path planning and costmaps correctly than before, and what confuses them?

**Who.** 5-8 friends or students, any background; no robotics needed. Not a statistical study: a usability and
learning check. Report every participant, including anyone who stops.

**What you need.** A laptop or phone with the live site (https://gauthamcodes.github.io/coco-labs/?view=learn), this
page printed or open, a timer, the consent note and one results sheet per person.

## Protocol (30 minutes)

| time | step | what the participant does | what you record |
| --- | --- | --- | --- |
| 0-2 | consent | reads and signs (or says yes to) the consent note | consent yes/no |
| 2-7 | pre-quiz | answers Q1-Q6 below on paper, no site, no help | each answer |
| 7-17 | Module 1 | Explorer lesson "A* against Dijkstra": all six steps, including the tune exercise | time, stars, hints used (from **My progress**) |
| 17-25 | Module 2 | Explorer lesson "Why paths keep their distance": all six steps | time, stars, hints used |
| 25-28 | post-quiz | the same Q1-Q6 again, on paper | each answer |
| 28-30 | open questions | O1-O3 below, aloud or written | their words, verbatim |

Say only: "Think aloud if you like. I can't help with the content." Note where they hesitate or get stuck, without
helping. If they ask how something works, write the question down; it is data.

**The site's own checks feed the post-quiz.** From **My progress** copy, per lesson: passed (yes/no), stars, hints
used, solution viewed. Or ask the participant to make a completion link and paste it into the Teacher page's class
dashboard afterwards (it re-verifies in your browser and exports a CSV). Names are optional; use P1, P2, ...

## Pre- and post-quiz (same questions)

1. A* and Dijkstra plan from the same start to the same goal. Which path costs less? (A*'s / Dijkstra's / the same / depends on the map)
2. Giving A* the heuristic h = 0 turns it into: (greedy search / Dijkstra / breadth-first search / nothing: it stops working)
3. Weighted A* (w = 3) compared with A*: (fewer expansions and never longer paths / fewer expansions, paths possibly longer / more expansions / no difference)
4. In a costmap, what does cost 253 mean? (a wall / the robot's centre there would hit something / expensive but allowed / unknown)
5. Without inflation, a shortest path around a corner: (stays in the middle / hugs the corner / is random / keeps 0.5 m away)
6. Raising the inflation cost weight makes paths: (shorter and closer to walls / longer and further from walls / unchanged / impossible)

Answers: 1 the same; 2 Dijkstra; 3 fewer expansions, paths possibly longer; 4 the centre there would hit; 5 hugs the
corner; 6 longer and further from walls.

## Open questions

- O1. What was the most confusing moment, and what would have helped?
- O2. Did predicting before seeing the answer help or annoy you? Why?
- O3. Would you continue to Module 3 on your own? What would make you stop?

## Consent note (print one per participant)

> I am taking part in a short test of COCO Lab's free robotics course, run by Gautham. It takes about 30 minutes.
> I can stop at any time without giving a reason. No account is made and the site records nothing about me; my
> progress stays in this browser. Gautham will write down my quiz answers, my time, the site's check results and
> what I say about the course, under a participant number (P1, P2, ...), not my name. The anonymous results may be
> summarised in COCO Lab's public documentation. I can ask for my notes to be deleted until they are summarised.
>
> Participant number: ______   I agree: yes / no   Date: ______

## Anonymous results template (one row per participant; commit as `docs/v2/r4/data/study/results.csv`)

```
participant,device,pre_q1,pre_q2,pre_q3,pre_q4,pre_q5,pre_q6,post_q1,post_q2,post_q3,post_q4,post_q5,post_q6,m1_minutes,m1_passed,m1_stars,m1_hints,m2_minutes,m2_passed,m2_stars,m2_hints,stopped_early,o1,o2,o3,observer_notes
P1,laptop|phone,,,,,,,,,,,,,,,,,,,,,no,,,,
```

**Report.** Per question: correct before / after (counts, not percentages, with N). Per lesson: passed, median time,
stars and hints. The open answers verbatim, grouped by theme. No claim that the course "works" from 5-8 people;
say what you saw. Negative results stay.
