# G1.6 — Fetch Rush, playable

Evidence class **MODEL** (the Arena model in Pyodide; Grasp Assist "MODEL · MoveIt-style").
Cloud container (Chromium SwiftShader; Pyodide 314.0.7 = Python 3.14 on WebAssembly;
CPython 3.12.3); none of the wall times below is a phone or laptop number.

## Played through the page's own controls

`lab_web/tools/g1/fetch_play.mjs` plays Fetch Rush seed 1 in Chromium with the keys a
person would use (F = AUTO, G = GRAB / DROP), reading the model's ticks:
[`browser/browser_record.json`](browser/browser_record.json), [`browser/after.png`](browser/after.png).

| Step | Model tick |
| --- | --- |
| started | 4 |
| at the object (GRAB lit) | 818 |
| carried | 1076 |
| in the drop zone (DROP lit) | 1350 |
| delivered | 1412 |

Scorecard (coco_lab.games, in the browser): **1 delivery, 0 contacts, time used 141 s**,
path efficiency 0.9916; 0 console errors. The results screen (stars from
`coco_lab.games.stars` against the committed reference card) is in `results_run/` when present.

What the player sees during the run: the order's object glows (a ring, a ▼ marker and a light
column); GRAB lights only when Grasp Assist's own candidates say the object can be picked (else
it is greyed with Grasp Assist's reason); the ring fills through approach, align and reach while
COCO's real arm joints follow Grasp Assist's script (`coco.arm.state.v1`); the drop zone pulses
while COCO carries; DROP lights only inside the order's drop zone. Robot vision adds the LiDAR
fan and the candidates ringed by verdict (✓ / ✕). The planner ghost (Settings) draws the A*
route for the current order (`game_op('ghost')`, read-only).

## Determinism: one record, three runtimes

| Comparison | Hash chain | Last hash | Scorecard |
| --- | --- | --- | --- |
| Browser Pyodide vs Pyodide in Node (`game_node.mjs --record`) | identical | identical | identical |
| Pyodide vs CPython (`tools/g1/game_parity.py`) | DIFFERENT | DIFFERENT | DIFFERENT |

**CPython and Pyodide differ, from tick 0** ([`cpython_parity.json`](cpython_parity.json)). Not hidden; it is G1.8's
item. Diagnosis made here: on the first tick, 2 of 480 LiDAR ranges differ in the last bit
(e.g. Depot beam 29: `6.121790243928102` in CPython, `6.1217902439281` in Pyodide; the Proving
Ground shows the same, beams 143 and 208). Hash v1 quantises ranges, so its tick-0 hash agrees;
hash v2 encodes the exact float, so it differs at once. The divergence is also real downstream:
under hash v1 a scripted full game first differs at tick 144 and the scorecards' floats differ
(same delivery count and time used). CPython agrees on the outcome here (1 delivery, 0 contacts,
141.0 s) but not on every float.

## Found: the next order's planner ghost stalls the model

After a delivery, `coco_lab.games.FetchRush._new_order` computes the next order's ghost: A*
to each of up to 16 pre-grasp poses plus one to the drop zone, each fully traced, across the
48 × 32 m Depot. Measured: **12.1 s in CPython** for one such call (from Dock 2 to the
mezzanine object), and a **17.4 s tick in Pyodide-in-Node** in a scripted full game
([`node_scripted_full.json`](node_scripted_full.json), `timing.slow_ticks`). Model time does not
advance during it (every timer is the model's clock), so scores stay fair, but the screen waits:
the HUD now says "COCO's planner is computing… (the clock waits)". G1 did not change the rule
(it is M6's code, and the stall is M6F.4's open planning budget, the WebAssembly gate); AUTO no
longer repeats that 16-search query (it targets the object; GRAB finishes the approach).
Question for Gautham in `G1_STATUS.md`.
