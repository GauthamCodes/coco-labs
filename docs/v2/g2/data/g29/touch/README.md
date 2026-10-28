# G2.9 item 1 · touch-to-motion over 1 s

**Finding: not a G2 regression; a measurement artefact present at G1.13's head (78a1596) too.**

- G1.13's "150 ms median" ([G1_REVIEW.md](../../../../g1/G1_REVIEW.md) line 48) is `samples[0:15]`, the 15
  deliberate swipes on open floor. G1.13's own 10-minute soak on the same build
  ([`phone_free_defaults_10min/phone_free.json`](../../../../g1/data/g113/phone_free_defaults_10min/phone_free.json))
  has **89 samples, median 1315 ms, p90 4961 ms**: the same > 1 s samples G2.8 reported.
- Every slow sample (G1.13 and G2.8 alike) sits at about 0.13 s + k × 1.2 s (1.3, 2.5, 3.7, 4.9, 6.1 s);
  1.2 s is the soak's swipe period (`input swipe … 1000` + 150 ms + adb). The soak pushes COCO into walls.
- Mechanism (`src/arena/perf.ts`): a drive input with the robot at rest arms a timer that stops at the
  first frame drawing the robot moved. A push into a wall never moves it (game rules stop it), and the
  timer stayed armed through the release until a *later* swipe moved COCO, so that swipe's real ~130 ms
  response was recorded as 1.3 s, 2.5 s, …
- Reproduced on the laptop (NVIDIA, Free Drive, Depot): `tools/g2/touch_blocked_check.mjs` turns COCO to
  face a wall, drives until the pose stops, pushes 1 s into the wall, pauses 200 ms, backs away.
  - G1.13 build 78a1596 (`index-DCz1wYLt.js`): back-away recorded as **1269 ms** → FAIL
    ([`blocked_check_g113_78a1596.json`](blocked_check_g113_78a1596.json)).
  - G2.9 build (`index-Sv29mc72.js`): back-away recorded as **129 ms**, the blocked push counted once in
    `inputNoMotion` → PASS ([`blocked_check_head_fix.json`](blocked_check_head_fix.json)).
- Because the start of the bisect range already has the artefact, there is no commit between 78a1596
  and the head to bisect to. The touch and tick path changes since G1.13 (PlayGame.tsx, session.ts)
  are measured on the real phone instead: the same recorder, outside the build, on both builds.

**Fix** (`perf.ts` `driveRelease`, called when keys, joystick or gamepad return to zero in Play and the
Arena): an input released before any motion is no sample, counted in `inputNoMotion` (shown in `?perf`).
Tests: `test/perf_input.test.ts` (5).

**Pacing (2977762).** Emulated phone (4× CPU, `tools/g2/touch_path_check.mjs`): the worker's step is the
same in both builds (62.8 vs 63.4 ms), so G2 added no step cost. But an input amended during a step's final
synchronous stretch missed that tick and waited in the worker for the next scheduled send (up to 0.1 s).
Now the tick after an amendment is sent as soon as the one in flight arrives, and an input with nothing in
flight is sent at once: emulated median 132 → 90 ms ([`emulated_before_after.json`](emulated_before_after.json)).

**Real phone:** [`../real_phone/README.md`](../real_phone/README.md) — 0 samples over 1 s on the final build
(313 samples); GAME 142 / 149 / 184 ms medians (pooled 166 ms), SIM pooled 134 ms; ≤ 150 ms met in 2 of 3
GAME runs, not in the hot 10-minute one.
