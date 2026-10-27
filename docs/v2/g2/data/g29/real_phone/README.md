# G2.9 — the real phone (2026-10-27)

**MEASURED on the real device.** Nothing Phone (1) (A063, Android 15, Chrome), full screen 803 × 361,
**medium tier (shipped default)**, pixel ratio 1.25, on AC, served by the laptop over USB (`adb reverse`)
from a frozen copy of the build; `lab_web/tools/phone/real_phone_free.mjs` (no DevTools while playing;
Android input only). Gautham handed the phone over for these runs and **waived the cool-start wait**
(`--cool 100`), so most runs started warm (battery column). Gazebo's gate and the suites ran on the laptop
meanwhile (the phone renders on its own GPU; the laptop serves static files). Rotation settings restored
to 0 / 0 after every run; COCO's saved settings on Gautham's usual origin were never touched (each build on
its own port; the test origin `localhost:4233` keeps the runs' own prefs).

Builds: **G2.9 final = `index-BG9HQCy4.js`** (app source of `2977762`), port 4233; **G1.13 = 78a1596**
(`index-DCz1wYLt.js`), port 4232, the bisect's start. Both hashes checked on the port before the runs.

Touch-to-motion columns: samples · **median** · p90 · max · over 1 s (ms), **by the corrected rule computed
outside the build** (`touch_to_motion_ext`: perf.ts's rule, plus "a touch lifted before any motion is no
sample"); for the G2.9 build the page's own measure is identical. "Blocked" = touches lifted with COCO not
moving (pushed into a wall), not samples. Step = the model's worker step (ms, median; recorded from the
4-minute run on).

| Run | Build | View | Game | min | fps median / min / p05 | frame p99 / max (ms) | > 50 ms | lost | touch | blocked | step | battery °C |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| touch_g113_freedrive_3min | G1.13 78a1596 | GAME | Free Drive | 3 | 60 / 47 / 59 | 26.1 / 40.0 | 0 of 10718 | 0 | 21 · **159** · 209 · 800 · 0 | 0 | — | 37 → 40 |
| touch_g29_freedrive_3min | G2.9 | GAME | Free Drive | 3 | 60 / 54 / 59 | 22.2 / 66.6 | 1 of 10784 | 0 | 43 · **142** · 195 · 254 · 0 | 21 | — | 40 → 41 |
| game_freedrive_10min | G2.9 | GAME | Free Drive | 10 | 60 / 48 / 53 | 25.9 / 56.5 | 3 of 35204 | 0 | 113 · **184** · 234 · 322 · 0 | 107 | — | 41 → 43 |
| game_fetchrush_6min_results_game | G2.9 | GAME | Fetch Rush seed 1 → results | 6 | 60 / 40 / 58 | 25.5 / 94.8 | 16 of 21449 | 0 | 41 · **149** · 202 · 276 · 0 | 44 | 96 | 41 → 42 |
| sim_fetchrush_2min_defaults | G2.9 | SIM, default displays (costmaps off) | Fetch Rush seed 1 | 2 | 60 / 59 / 59 | 23.3 / 30.0 | 0 of 7200 | 0 | 24 · **208** · 247 · 264 · 0 | 19 | — | 43 → 43 |
| sim_fetchrush_1min_all_displays | G2.9 | SIM, every display on | Fetch Rush seed 1 | 1 | 60 / 59 / 59 | 25.3 / 33.8 | 0 of 3600 | 0 | 9 · **184** · 227 · 227 · 0 | 0 | — | 43 → 43 |
| sim_all_fetchrush_6min_saved_prefs | G2.9 | SIM, every display on (*) | Fetch Rush seed 1 → results | 6 | 60 / 60 / 60 | 20.0 / 28.0 | 0 of 21600 | 0 | 44 · **103** · 145 · 162 · 0 | 41 | — | 38 → 40 |
| sim_all_freedrive_4min_saved_prefs | G2.9 | SIM, every display on (*) | Free Drive | 4 | 60 / 54 / 59 | 20.2 / 118.5 | 1 of 14394 | 0 | 39 · **127** · 185 · 203 · 0 | 13 | 65 | 40 → 41 |

(*) These two were meant as GAME runs: the test origin had kept the previous runs' saved `view` (SIM) and
`displays` (all on), and the screenshots show SIM with every display. They are reported as what they were.
The tool now sets each run's view and resets the displays unless asked (`real_phone_free.mjs`).

**Pooled, G2.9 final build:** GAME 197 samples, median **166 ms**, p90 225, max 322, **0 over 1 s**;
SIM 116 samples, median **134 ms**, p90 208, max 264, **0 over 1 s**. No WebGL context loss and no page
error in any run; every run's fps median is 60 (SIM with every display on included).

**Reading (Gautham's target: ≤ 150 ms median, matching G1):**
- The blocker (samples over 1 s) is **gone**: 0 of 313 on the final build. Its cause was a measurement
  artefact present at G1.13 too ([`../touch/README.md`](../touch/README.md)): G1.13's own measure on this
  phone today gives p90 3718 ms (session 1, [`s1_BiDn1JQc/`](s1_BiDn1JQc/)).
- ≤ 150 ms is met by 2 of the 3 GAME runs (142, 149 ms) and **not** by the 10-minute one (184 ms, battery
  41 → 43 °C), so the pooled GAME median (166 ms) misses it. The G1.13 build measured 159 ms in the same
  session (37 → 40 °C) and 140 ms in session 1: G1's "150 ms" (15 swipes, a cool phone) is not a fixed
  property of the phone either.
- What remains is the model's own step: 65–96 ms median on this phone (the input waits for it), as at G1.13
  (laptop, 4× CPU throttle: 62.8 ms G1.13 vs 63.4 ms G2.9). The G2.9 pacing change removed the extra wait
  of up to 0.1 s an input could add (emulated median 132 → 90 ms, [`../touch/`](../touch/)). Shorter steps on a
  hot phone would need the model's Python made cheaper (its results unchanged): not done in G2.9.

**Session 1** ([`s1_BiDn1JQc/`](s1_BiDn1JQc/), the build before the pacing change, `index-BiDn1JQc.js`):
G1.13 build 140 ms median by the corrected rule vs its own measure's p90 3718 ms; G2.9 157 ms, 0 over 1 s.
Two runs of that session failed to load (the phone's `adb reverse` was reset while access was re-granted)
and a 10-minute run was stopped to measure the final build instead; none of them is reported.

Screens (looked at one by one; status bars blacked out where shown):
[`../../../screens/g29/real_phone/`](../../../screens/g29/real_phone/).
