# G2 · Before / after screenshots (G2.8)

Screenshots catch regressions; **Gautham judges the look**. The sentences below describe only what is
visible in the images; no number here is a measurement except where a committed file is cited.

| | Before (G2.0) | After (G2.8) |
| --- | --- | --- |
| Tree | `origin/main` `7475896` | `v2/g2-sim-identity` `89ce9d0` build (re-captured 2026-10-27, after Rules 5, Fetch by colour, the hotfix and the /rosout fixes; the first after set was `5c77bbe`), served at `http://127.0.0.1:4184/coco-labs/` |
| Laptop | RTX 4050, driver 580.178.04, balanced, on AC | same GPU/driver, balanced, on AC |
| Renderer (both) | ANGLE (NVIDIA GeForce RTX 4050 Laptop GPU, OpenGL ES 3.2) | same |
| Metadata | [`before/screens/shots.json`](screens/before/screens/shots.json), [`before/review/shots.json`](screens/before/review/shots.json) | [`after/screens/shots.json`](screens/after/screens/shots.json), [`after/review/shots.json`](screens/after/review/shots.json) |

Load note: the after `screens` run recorded other work on the laptop at capture time (`top_cpu_now` in
`after/screens/shots.json`: brave, `ament_flake8`, python, each 69–123 % of a core). The before run
recorded a quiet machine. Wall-clock numbers shown inside the screenshots (Compare's "ms · This
device") are single samples under different load and are **not** a before/after comparison.

**Fetch Rush seed 1 is a different round now.** G2.1's decision (G2_RESULTS.md, "Decisions applied")
moved the phone rounds to a 26 m budget with rules 4; seed 1 is now a workshop round with a 5:31 timer.
So every Play "after" shows the fenced workshop maze, where "before" showed the open loading dock with
a 4:29 timer. The scene difference is that decision, not the new looks.

## 1. Desktop and emulated phone — `tools/g1/screens.mjs`

Command (after): `G1_GPU=nvidia node tools/g1/screens.mjs SITE ../docs/v2/g2/screens/after/screens --play '?view=play&game=fetch_rush&seed=1' --play-click '[data-testid="g1-play"]'`
(same queries as the before set's `shots.json`). Desktop is 1440 × 900. Phone rows are the
**EMULATED** Nothing Phone (1): viewport, touch and a 4× CPU throttle, rendered by the laptop's GPU.
They are not phone measurements.

| Surface | Before | After | What changed (as seen) |
| --- | --- | --- | --- |
| Desktop · title | [before](screens/before/screens/desktop-title.png) | [after](screens/after/screens/desktop-title.png) | Tagline "See what the robot computes." replaced by "a ROS 2 robot you can drive in your browser", plus a monospace badge line "Model of COCO's ROS 2 stack · Nav2 · Gazebo Harmonic · MoveIt ⓘ". The wordmark moved up to make room. COCO now has a footprint ring and small RGB TF axes. |
| Desktop · Play | [before](screens/before/screens/desktop-play.png) | [after](screens/after/screens/desktop-play.png) | The eye button is replaced by a panels button (P) and a GAME \| SIM switch (V). New: faint LiDAR rays fanning out from COCO, a footprint ring, the telemetry strip under the speed gauge (`/cmd_vel v … ω … · /odom x … y … θ … · sim … s`) and a `/rosout · no events yet` line bottom-left. The gauge moved up. The fence walls show a metallic mesh material. The round is different (see above). |
| Desktop · Compare | [before](screens/before/screens/desktop-compare.png) | [after](screens/after/screens/desktop-compare.png) | No visible change apart from the wall-clock ms (see load note). |
| Desktop · Recordings | [before](screens/before/screens/desktop-recordings.png) | [after](screens/after/screens/desktop-recordings.png) | No visible change. |
| EMULATED phone landscape · title | [before](screens/before/screens/phone-landscape-title.png) | [after](screens/after/screens/phone-landscape-title.png) | Same new tagline and badge line. The wordmark and tagline now sit on top of the robot (see "Looks wrong"). |
| EMULATED phone landscape · Play | [before](screens/before/screens/phone-landscape-play.png) | [after](screens/after/screens/phone-landscape-play.png) | Panels button and GAME \| SIM switch replace the eye. LiDAR rays, footprint ring, telemetry strip and `/rosout` line are all present at phone size. Workshop round. |
| EMULATED phone landscape · Compare | [before](screens/before/screens/phone-landscape-compare.png) | [after](screens/after/screens/phone-landscape-compare.png) | No visible change apart from the wall-clock ms. |
| EMULATED phone landscape · Recordings | [before](screens/before/screens/phone-landscape-recordings.png) | [after](screens/after/screens/phone-landscape-recordings.png) | No visible change. |
| EMULATED phone portrait · title | [before](screens/before/screens/phone-portrait-title.png) | [after](screens/after/screens/phone-portrait-title.png) | New tagline and badges. The badge line wraps, leaving "MoveIt ⓘ" alone on a second line. The robot shows the footprint ring and TF axes. |
| EMULATED phone portrait · Play | [before](screens/before/screens/phone-portrait-play.png) | [after](screens/after/screens/phone-portrait-play.png) | The rotate card, identical, as designed. The tool's "press PLAY" step timed out in both runs because PLAY sits under the card (`ready: false` in both `shots.json`). |
| EMULATED phone portrait · Compare | [before](screens/before/screens/phone-portrait-compare.png) | [after](screens/after/screens/phone-portrait-compare.png) | No visible change. |
| EMULATED phone portrait · Recordings | [before](screens/before/screens/phone-portrait-recordings.png) | [after](screens/after/screens/phone-portrait-recordings.png) | No visible change. |

## 2. Review set — desktop 1440 × 900

Before: `tools/g1/review_shots.mjs`. After: `G1_GPU=nvidia node tools/g2/review_shots.mjs SITE ../docs/v2/g2/screens/after/review`.
It covers the same nine surfaces. Only 04 and 05 changed what they capture, because G2 replaced G1's
Robot-vision eye with the GAME | SIM switch:

- 04 was **Robot vision on**. It is now **SIM view** (V).
- 05 was tactical **with Robot vision**. It is now the tactical camera (C) **in GAME view**.

| Surface | Before | After | What changed (as seen) |
| --- | --- | --- | --- |
| 01 title | [before](screens/before/review/01-title.png) | [after](screens/after/review/01-title.png) | Same changes as the desktop title: the new tagline and badge line, and the footprint ring and TF axes on COCO. |
| 02 modes | [before](screens/before/review/02-modes.png) | [after](screens/after/review/02-modes.png) | The Fetch Rush card gains "RACE NAV2 · REAL ROS 2 RECORDING" on its own row (G2.6). A new **Fetch by colour** card sits beside it: four chips labelled with text and colour (RED · 20 mm, GREEN · 24 mm, BLUE · 28 mm, YELLOW · 32 mm), its own RACE NAV2 row and the line "As COCO's first Gazebo fetch: four rods, one per colour." The footer now names Fetch Rush, Fetch by colour and Free Drive. |
| 03 Play chase | [before](screens/before/review/03-play-chase.png) | [after](screens/after/review/03-play-chase.png) | Workshop round. LiDAR rays, footprint ring, TF axes and the global plan line are visible. The `/rosout` line shows a real model event as level, node and message on up to two lines (`INFO cmd_vel_arbiter: passing teleop (/cmd_vel_teleop)`), ending before the telemetry strip. The telemetry strip reads `/odom x 1.29 y 0.05 θ 2°` after the W press. |
| 04 Robot vision → **SIM view** | [before](screens/before/review/04-play-robot-vision.png) | [after](screens/after/review/04-play-sim.png) | An entirely new view. It has a header "SIM · RViz-style view of the browser model MODEL · Fixed Frame: map", costmaps in the RViz palette (magenta/cyan/purple), LaserScan hit points in yellow-green, labelled TF frames (`lidar_link`, `base_link`, `base_footprint`, `odom`) and a Gazebo-style bottom bar (`Sim time · Real time · RTF · Iterations`) above the telemetry strip. The HUD drops CAM and AUTO, keeping STOP, the joystick, GRAB, pause, panels and the switch. |
| 05 tactical (vision) → **tactical, GAME view** | [before](screens/before/review/05-play-tactical-vision.png) | [after](screens/after/review/05-play-tactical.png) | Top-down over the workshop maze instead of the loading dock. The before shot had Robot vision's cyan wall highlighting; after shows the plain GAME look, with LiDAR rays and the plan line. The telemetry strip and `/rosout` line are present. |
| 06 "What is real here" | [before](screens/before/review/06-play-what-is-real.png) | [after](screens/after/review/06-play-what-is-real.png) | The sheet text is unchanged. Behind it the camera is much closer to COCO and shows the G2 materials: rubber tyres, metallic chassis, orange plastic arm, green status light. TF axes and the footprint ring are on the robot, and the floor and walls show reflections. |
| 07 Compare | [before](screens/before/review/07-compare.png) | [after](screens/after/review/07-compare.png) | No visible change apart from the wall-clock ms. |
| 08 Research | [before](screens/before/review/08-research.png) | [after](screens/after/review/08-research.png) | No visible change. |
| 09 M5 Arena | [before](screens/before/review/09-m5-arena.png) | [after](screens/after/review/09-m5-arena.png) | No visible change. |

SSAO is on the high tier only (G2.5). The review set's Play shots load `tier=high`. In these screenshots
I can't tell SSAO apart from the lighting and material changes, so I don't claim it is visible.

## Since the first after set (2026-10-27)

What is new in the re-captured images, as seen: the Fetch by colour card (02); the /rosout line as
level, node and message, clear of the telemetry strip (03, desktop and phone Play); Fetch Rush seed 1
plays rules 5 (the same round and timer; the actors now stop for COCO). The no-WebGL fallback pages are
in [`../hotfix_webgl/screens/`](../hotfix_webgl/screens/) and [`../hotfix_webgl/g2/screens/`](../hotfix_webgl/g2/screens/); Fetch by colour in
[`screens/fetch_colour/`](screens/fetch_colour/); Rules 5's forklift stopping in [`screens/rules5/`](screens/rules5/).

## G2.9 · Polish before deploy (2026-10-27)

Gautham reviewed PR #28 and this file's "Looks wrong". Real-device shots (status bars blacked out, each looked at):
[`screens/g29/real_phone/`](screens/g29/real_phone/) — SIM with every display on, the GAME pill and both results screens. The after set below is the G2.9 build, served at
`http://127.0.0.1:4184/coco-labs/` (RTX 4050, driver 580.178.04, balanced, on AC; the laptop also ran the
derivation 5 Gazebo gate during capture, so no number inside these images is a measurement). Desktop
1440 × 900; phone rows are the **EMULATED** Nothing Phone (1) (viewport, touch, UA; rendered by the laptop).
Folders: [`screens/g29/after/screens/`](screens/g29/after/screens/), [`…/review/`](screens/g29/after/review/),
[`…/sim/`](screens/g29/after/sim/), [`…/results/`](screens/g29/after/results/).

| "Looks wrong" item | G2.8 | G2.9 | What changed (as seen) |
| --- | --- | --- | --- |
| 1. SIM background light grey; joystick label and key hints hard to read | [04](screens/after/review/04-play-sim.png), [real phone](screens/g28/real_phone_final/sim1-one-line-04-end.png) | [desktop](screens/g29/after/review/04-play-sim.png), [phone](screens/g29/after/sim/phone-landscape-2-sim.png) | Background #303030 with a grey map (free a shade lighter, occupied light grey, unknown not drawn). Costmaps are see-through overlays on desktop and **off by default on phones** (Displays turns them on; a saved choice wins). COCO starts closer and is lit more in SIM; the high tier's post passes are skipped in SIM (they washed it out). TF labels are small (12–16 px), placed right of COCO's footprint, stepped to a free row with a leader line and kept off the HUD's top and bottom rows (`odom` sits above the Gazebo bar). Joystick hint and ESC / P / V hints sit on dark pills. |
| 2. Title over the robot (landscape); "MoveIt ⓘ" alone (portrait) | [landscape](screens/after/screens/phone-landscape-title.png), [portrait](screens/after/screens/phone-portrait-title.png) | [landscape](screens/g29/after/screens/phone-landscape-title.png), [portrait](screens/g29/after/screens/phone-portrait-title.png), [desktop](screens/g29/after/review/01-title.png) | COCO is drawn in the band between the top icons and the title text on every screen (a view offset; the camera still looks at COCO). The badge line wraps only between "Model of COCO's ROS 2 stack ·" and "Nav2 · Gazebo Harmonic · MoveIt ⓘ". |
| 3. Tagline | "a ROS 2 robot you can drive in your browser" | "Drive COCO, a ROS 2 robot, modelled in your browser." | Gautham's wording, 2026-10-27. |
| 4. Mode card chips cramped | [02](screens/after/review/02-modes.png) | [02](screens/g29/after/review/02-modes.png) | Fetch Rush's card is as wide as Fetch by colour's. "PLAY · 2 ORDERS" and "FULL SHIFT · 3" are one line each; "RACE NAV2 · REAL ROS 2 RECORDING" is one line on both cards. |
| 5. Real-phone HUD crowding (status pill vs pause) | [1 min](screens/g28/real_phone/close-fetchrush-game-1-minute.png) | **REAL DEVICE** [1 min](screens/g29/real_phone/game_fetchrush_6min_results_game__03-one-minute.png) | The pill "DELIVER 0/2 · 3:53 · ✖ 30" ends clear of the pause button (denser backing; no code change to its width). |
| 6. Results on the phone: bag button cut, STOP over the results, HUD text through, legend line that is not drawn | [real phone](screens/g28/real_phone/close-fetchrush-game-end-results.png) | [EMULATED phone](screens/g29/after/results/phone-landscape-results-colour-red.png); **REAL DEVICE** [GAME](screens/g29/real_phone/game_fetchrush_6min_results_game__04-end.png), [after SIM](screens/g29/real_phone/sim_all_fetchrush_6min_saved_prefs__04-end-results.png) | STOP and the whole HUD are hidden while the results are up; the backdrop is 94 % opaque (no HUD text shows); "SAVE AS ROSBAG2 (MCAP)" is one line. The inset's legend lists only lines that are drawn: a drive under 0.5 m is said in metres ("COCO drove 0.1 m (too short to draw)") instead of an orange key (`test/g29_inset_legend.test.tsx`). The drive is drawn over the plan, thinner. |
| 7. Tactical: fences hide the maze, clipped labels, haze | [05](screens/after/review/05-play-tactical.png) | [05](screens/g29/after/review/05-play-tactical.png) | A 24° lens from higher up frames the same ground, nearly straight down; the world is drawn at 30 % of its height while tactical (a cut-away; presentation only); no headlight cone (the haze). Region names now start inside their zone ("FORKLIFT LANES" whole). In this frame the start of "WORKSHOP MAZE" is under the joystick hint (the HUD over the floor, not a wall). |
| 8. Plan line through the HUD | [03](screens/after/review/03-play-chase.png) | [03](screens/g29/after/review/03-play-chase.png) | The plan, the planner ghost's line and its chevrons fade out from COCO's own floor depth toward a camera behind it: the route behind COCO no longer runs through the gauge and the telemetry strip. Gauge, strip and status pill have denser backings. |
| 9. "COCO Lab" wordmark clipped; Research's Level select overflowing | [08](screens/after/review/08-research.png) | [08](screens/g29/after/review/08-research.png) | The header keeps a 12 px gutter; the filter selects fit their column. (Not asked and unchanged: the phone-landscape Compare rows under the Replay bar, and "…final phase was succeeded.") |

Checks on this build: `chase_hud_check` 4 profiles × 20 poses + SIM, 0 failed; `saved_view_check` ok;
`rosout_room_check` ok; `fetch_colour_check --phone` ok, results fit (412 / 412 px)
([`data/g29/looks/`](data/g29/looks/), [`data/g29/sim/`](data/g29/sim/)).

## 3. Real phone — **REAL DEVICE** (Nothing Phone (1), status bars redacted)

Before: G2.0, Fetch Rush seed 1 (loading dock), 1 minute ([`phone_free.json`](screens/before/real_phone/phone_free.json)).
After: G2.8's runs (numbers in [G2_RESULTS.md](G2_RESULTS.md) and [`data/g28/`](data/g28/)). These
shots were captured and checked earlier in G2.8. They were not re-captured here.

| Moment | Before | After | What changed (as seen) |
| --- | --- | --- | --- |
| GAME, ~1 minute | [before](screens/before/real_phone/03-one-minute.png) | [after](screens/g28/real_phone/close-fetchrush-game-1-minute.png) | Workshop round with mesh fences. The GAME \| SIM switch and panels button replace the eye. LiDAR rays, footprint ring, telemetry strip, and the `/rosout` last line (`[WARN] [109.600] [local_…`). The status pill reads "DELIVER 0/2 · 3:40 · ✖ 41". |
| GAME, end | [before](screens/before/real_phone/04-end.png) | [after](screens/g28/real_phone/close-fetchrush-game-end-results.png) | Before ended mid-round. After shows the new results screen: TIME USED 331.4 s · DELIVERIES 0 · CONTACTS 178 · PATH vs PLANNER —. It adds the "What the planner computed" A* inset (labelled MODEL) and buttons PLAY AGAIN · WATCH HOW THE PLANNER DID IT · GAMES · SAVE AS ROSBAG2 (MCAP). |
| SIM, 1 minute | — (no SIM view before G2) | [after](screens/g28/real_phone/sim-1-minute.png), [close run](screens/g28/real_phone/close-sim-1-minute.png) | SIM view on the phone: the header wraps to two lines, with costmaps, scan points, labelled TF frames and a visible floor grid. There is no Gazebo bar on the phone (desktop/SIM only, per spec). |
| SIM, end | — | [after](screens/g28/real_phone/sim-end.png), [close run](screens/g28/real_phone/close-sim-end.png) | Same view at about 2 minutes. COCO sits in the same place throughout, against a wall ("Contact! −1" toast). |
| GAME, final build (2026-10-25) | — | [one minute](screens/g28/real_phone_final/game10-final-build-03-one-minute.png) | Free Drive on the Depot: the /rosout last line is level and node ("INFO cmd_vel_arbiter:…"), clear of the strip. |
| SIM, final layout (2026-10-27) | — | [end](screens/g28/real_phone_final/sim1-one-line-04-end.png) | One unwrapped /rosout line, "WARN local_contro…", under the joystick and before the strip. |
| SIM defect (fixed) | — | [sim-BUG-saved-view-before-fix](screens/g28/real_phone/sim-BUG-saved-view-before-fix.png) | Kept as evidence. The switch shows SIM and the SIM header is up, but the scene is still the GAME render. This was the saved-view defect found and fixed in G2.8. |

## 4. Other G2 screenshot folders

- [`screens/g22/`](screens/g22/): G2.2 GAME → SIM → GAME and each panel (Displays, ROS 2 graph, Topic echo, Plot, Learn), desktop and **EMULATED** phone landscape.
- [`screens/g26/`](screens/g26/): G2.6 Race Nav2 — [modes](screens/g26/1-modes.png), [racing the STACK ghost](screens/g26/2-racing.png), [three-way results](screens/g26/3-results.png).
- [`screens/g27/`](screens/g27/): G2.7 looks — [title](screens/g27/01-title.png), [Play chase](screens/g27/03-play-chase.png).
- [`screens/g28/real_phone/`](screens/g28/real_phone/): **REAL DEVICE** G2.8 shots (table above).

## Looks wrong / for Gautham to judge

*(G2.8's list, kept as written. G2.9's answer to each item is in the G2.9 section above.)*

1. **SIM background is light grey, not dark.** G2_PROMPT §2.1 asks for "a dark neutral background". The SIM shots (desktop 04, g22, real phone) show a light grey floor/background. Against it:
   - the joystick ring and the "WASD / ARROWS" / "DRAG TO DRIVE" label are hard to read (desktop 04, phone SIM);
   - the small ESC / P / V key hints under the top-right buttons fade out.
2. **Title wordmark over the robot (EMULATED phone landscape).** "COCO LAB" and the new tagline now sit on top of the robot and the orange pad. The tagline crosses the robot model, and the wordmark's orange dot is hard to see against the pad. In portrait, the tagline crosses the pad's orange stripe and the badge line wraps with "MoveIt ⓘ" alone.
3. **Tagline wording.** "a ROS 2 robot you can drive in your browser" is the prompt's own wording (§2.5). The badge line beneath says "Model of COCO's ROS 2 stack" and the ⓘ explains. G2's stop list includes "a UI element would claim the browser runs ROS 2", so this is flagged for Gautham's reading. I did not change it.
4. **Modes card chips are cramped (02).** With the third chip, "PLAY · 2 ORDERS" and "FULL SHIFT · 3" each wrap to three lines. "RACE NAV2 · REAL ROS 2 RECORDING" wraps to four lines and reaches the card's right edge.
5. **Real-phone HUD crowding.**
   - On the 1-minute shot, the status pill ("… ✖ 41") runs right up to the pause button.
   - ~~In [sim-1-minute](screens/g28/real_phone/sim-1-minute.png) the telemetry strip overlaps the `/rosout` box~~ — fixed (efb61fb: fixed-width strip; 12aa0ab and 89ce9d0: the console ends before the strip, one line on short screens; `data/g28/rosout_room/`).
   - ~~The phone `/rosout` last line is cut to `[WARN] [109.600] [local_…`~~ — now level and node first (`WARN local_contro…` on the phone); still short at rest, tapping expands it.
6. **Results screen on the real phone.**
   - "SAVE AS ROSBAG2 (MCAP)" wraps to two lines and is cut off by the bottom edge.
   - STOP stays drawn over the results.
   - The stat cards sit over the faded HUD pill text, which shows through ("DELIVER 0/2", "178").
   - In the inset I can't see "your drive" (orange) at all, only a speck near the start. That is consistent with 0 deliveries / 178 contacts in that run (COCO pressed against a wall at its start, noted in G2_RESULTS.md), but the legend promises a line that isn't visible.
7. **Tactical camera over the workshop (05).**
   - Tall fence walls in top-down perspective hide much of the maze.
   - The floor labels are clipped ("…RKLIFT LANES", "…P MAZE").
   - "…P MAZE" runs into the "WASD / ARROWS" label.
   - There is a large bright haze over the centre of the frame.
8. **Plan line through the HUD.** In GAME Play (03, desktop Play) the cyan global plan is drawn through the speed gauge and the telemetry strip. The before shots had the same overlap with the gauge.
9. **Pre-existing, unchanged by G2** (listed so they are not mistaken for regressions):
   - Research's "Level" select overflows the filter panel.
   - The "COCO Lab" wordmark is clipped at the left edge of the top bar.
   - On the phone-landscape Compare, the result rows are cut off under the Replay bar.
   - The case-file sentence reads "…final phase was succeeded."
