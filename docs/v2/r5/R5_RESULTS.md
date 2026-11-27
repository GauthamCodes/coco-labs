# R5 · Live ROS 2, Run it in ROS 2, World editor — results

Branch `v2/r5-live-ros2` (worktree `~/coco_labs_ws/worktrees/r5`). Prompt: [R5_PROMPT.md](R5_PROMPT.md); progress and
every measurement's provenance: [R5_STATUS.md](R5_STATUS.md). Evidence classes: MODEL (the browser model), STACK (a
recording of COCO's ROS 2 stack in Gazebo), LIVE (that stack running now, in the visitor's container: a Gazebo
simulation, never hardware).

## Steps done

| step | state | evidence |
| --- | --- | --- |
| R5.1 the coco-ros2 image | **done** | CI runs 45867550987 → 45890459420; laptop run; [data/r51](data/r51/) |
| R5.2 Connect to ROS 2 | **done** (laptop; the live-site https check: R5.6) | [data/r52](data/r52/) |
| R5.3 Model vs LIVE | **done** | [data/r53](data/r53/) |
| R5.4 Run it in ROS 2 (level packages) | **done** | [data/r54](data/r54/) |
| R5.5 World editor (first version) | **done** | [data/r55](data/r55/) |
| localisation v1.1 suites, leaderboard re-verify matrix | **deferred** to a follow-up PR (Gautham, 2026-11-27: ship R5.1-R5.5 first) | R5_STATUS |
| R5.6 close | this PR | below |

## What existed and was reused

The Live Stack tab's `coco.v1` client and **coco_web's own platform_server** (the LIVE control gateway, unchanged:
its allowlist, STOP latch, code access, origin allowlist); the World Spec v3 kit and reader (the editor's live
check); `tools/m6/gen_level.py`'s generation (moved into `coco_lab.level_files`, its outputs byte-identical); R2's
ROS 2 exporter pattern and the Studio exports (`user_package:=`); the M6F.7 shapes and the G2.5 CDR writer (the
reader's goldens); R1's experiments API (Model vs LIVE's MODEL side, the editor's experiments); Play's SIM view and
panels (fed LIVE ticks of the model's own shape); the coco-ros2 entrypoint's bring-up (the level package's).

## The image: `ghcr.io/gauthamcodes/coco-ros2`

`docker run --rm -p 8765:8765 -p 8766:8766 ghcr.io/gauthamcodes/coco-ros2 --level depot` (two ports: the read-only
bridge and the control gateway; the prompt's command had one). Jazzy ros-base, Gazebo Harmonic headless (Xvfb,
software GL), Nav2, CycloneDDS, `cmd_vel_arbiter`, foxglove_bridge 3.6.3 **read-only**, coco_web's platform_server
(remote mode, code access) and COCO Lab's levels (depot, depot_colours, depot_clutter byte-identical to the committed
records; arena). Latest verified: `sha-cebbcea6a835`, 3,942,696,893 bytes unpacked (budget 4.0 GB), 1,175,907,620
bytes per pull, **public** (anonymous pull checked in CI and on the laptop). CI (every push): build, size, levels,
Nav2 active, the six topics (/scan /odom /tf /map /plan /cmd_vel), the arbiter the only wheel publisher, the bridge
probe and the gateway probe (10/10), then the push. Laptop: healthy in 40 s, RTF 0.88.

Defects found on the way, each measured: foxglove_bridge 3.6.3 **does not apply** `client_topic_whitelist` (a client
made the bridge a second wheel publisher; the bridge is read-only now); 3.x speaks only `foxglove.sdk.v1`; Ubuntu's
tornado 6.4.0 closed every gateway connection at its first keepalive (6.5.7, ci.yml's pin, installed); remote mode
needs code access (platform_server refuses open); coco_web's 60 s idle limit is now 30 min in a visitor's own
container.

## Connect to ROS 2 (LIVE)

Play (Free drive): a HUD button, the SIM caption and the pause menu open "Connect to ROS 2" (bridge URL + the control
code the container prints). While LIVE the model pauses; GAME and SIM views, the panels (the ROS 2 graph lists the
real nodes), telemetry and the evidence labels show LIVE; drive, STOP, GO and AUTO are `coco.v1` intents to the
gateway (the browser names no ROS topic to command COCO). Laptop, `tools/r5/live_e2e.mjs`, **Chromium and Firefox
11/11 each**: a wrong port said in words (with the docker command); LIVE; the real graph (36 nodes, 184 topics, the
wheel topic published by `/cmd_vel_arbiter` only); W for 2 s drove COCO 0.535 m / 0.600 m through the arbiter; a goal
`succeeded` in Nav2; STOP latched and held (0.000 m); R released; SIM LIVE; disconnect to MODEL; 0 page errors. Lost
connection (container stopped): words, back to MODEL. Screen recording: `data/r52/laptop/chromium_live_session.webm`.
Fails safe: a device too slow to send drive frames every 0.5 s has its stick zeroed by the gateway (measured with
headless SwiftShader).

**https → ws://localhost (the public site):** works in both browsers once the visitor allows local network access;
see R5.6 below.

## Model vs LIVE

Every LIVE goal also runs in the browser model (an R1 control experiment from Nav2's believed pose, controller `rpp`),
both paths drawn (violet MODEL, amber LIVE) with distance and sim time. Example (a goal ~1 m ahead; one goal: an
example, not a rate): Chromium MODEL 0.95 m / 3.9 s vs LIVE 0.95 m / 4.2 s; Firefox 0.94 m / 3.8 s vs 0.92 m / 3.9 s.
UNRESOLVED: the gateway's Gazebo-truth pose sits ~2 m off in this container's frame (x 25.0 on the start pad at
x 23.0); no truth-vs-belief number is shown.

## Run it in ROS 2 (level packages)

`coco_lab.level_package.package` (the browser's worker and the CLI `tools/r5/level_package.py`, the same function): `coco_level_<id>` with the world, the Nav2
map and parameters, `scenario.json`, a launch file (bring-up as the image's, then the arbiter and Nav2, or a Studio
export with `user_package:=`), `run_goals` and a README. Results (STACK; AMCL's last pose to the goal):

| where | level | goals |
| --- | --- | --- |
| image `sha-cebbcea6a835` (README path A) | coco_depot_v1 | 2/2 SUCCEEDED |
| image | coco_depot_clutter_v1 | 2/2 |
| laptop Jazzy (path B) | coco_depot_v1 | 2/2 |
| laptop Jazzy | coco_depot_clutter_v1 | 2/2 |
| laptop Jazzy, the Studio's particle-filter starter in place of AMCL | coco_depot_v1 | 2/2 |
| the zip downloaded from the browser (= the native package, 37/37 files), laptop Jazzy | coco_depot_v1 | 1/1 |
| the world editor's zip (R5.5), laptop Jazzy | editor_two_rooms | 2/2 |

In the browser this needed `coco_lab._xml` (Pyodide has no `xml`; byte-identical to ElementTree on every World Spec)
and an on-demand pack: putting the level modules in the game pack had **broken Play's boot** (caught locally).

## World editor

Workbench › World editor: kit pieces on a 0.5 m grid, start and goals, move/rotate/delete, undo/redo; a live check in
the worker (the reader's own refusals, COCO fits at its start, every goal reachable); Play this level, Use in an
experiment, Download as ROS 2 package, share link. Test level built from scratch by mouse (two rooms, a door, a bench,
a rack, two goals), **Chromium and Firefox PASS**: check ✓ (10.07 m, 1.91 m), experiment 4/4 found (A*, Dijkstra),
Play GO drives in AUTO, a box in the doorway refused in words, Undo restores, its package 2/2 in Gazebo. Found: a
level without actors made every Play tick invalid JSON (`clearance: Infinity`); fixed in the glue.

## Not verified (honest list)

- The real Nothing Phone (1): not connected (`adb devices` empty); phone views are emulated.
- WebKit determinism ran in CI only (the laptop's no-sudo WebKit runner was removed in a disk cleanup).
- LIVE version mismatch: unit-tested against a fake server, not a live wrong-version bridge.
- Displays/Topic echo/Plot while LIVE show LIVE values rebuilt in ROS 2 shapes from ticks, not raw messages (labelled).
- The Depot's actors stand still in the image and in level packages (their scenario script is not included).
- The world editor (first version): axis-aligned pieces only; no ramps, platforms, objects or actors; canvas
  pointer-driven (keyboard: tools, lists, actions and R/Delete/Ctrl+Z on the canvas).
- Localisation v1.1 suites and the leaderboard re-verify matrix: deferred (a follow-up PR).

## Tests, determinism, fps, security

**Local suites** (`tools/g2/suites.sh`, laptop, balanced, AC). The first full run (on `03fbc09`) caught the R5
modules breaking three of the model's own rules: `level_files` imported `math` (the model takes it from `numerics`),
`level_check` used float `**`, and the level-package CLI imported PyYAML (`coco_lab` imports the standard library
only). Also flake8/pep257 on the R5 Python. Fixed in `1fac4ae` and `[R5.6]` after it: the CLI moved to
`tools/r5/level_package.py` (its output byte-identical to the old CLI's, 37/37 files); `numerics.hypot` replaced the
float pows. Second full run (`1fac4ae`): every step green except one more float pow (fixed; the rule file passes,
38/38) and determinism (below). Final checks after the last fix: `coco_lab` package suite (see PR), lab_web tools
324/324, vitest 686/686, typecheck, build, `check_dist`, native gate (818,951 planner values exact), coco verify
18/18, update isolation, screenshots, chase HUD, saved view, v1 links 50/50, replays.

**Determinism** (hash v1, 10 sessions / 1,500 ticks; terrain, 3 sessions / 2,100 ticks): Chromium, Firefox and
Pyodide-in-Node **0 mismatched ticks**, identical digests (`9a9d582d03f4`, `3a8c227eca45`). WebKit: the laptop's
no-sudo WebKit runner was deleted in the 2026-11-26 disk cleanup, so WebKit runs in CI only (lab.yml runs all three
browsers on the PR). [data/r56/](data/r56/)

**Play fps** (`tools/g1/perf_play.mjs`, Fetch Rush, 2 min, `G1_GPU=nvidia`: ANGLE on the RTX 4050, driver
580.178.04; balanced, AC). Baseline = the live site (main `c629821`, deployed):

| run | drawn fps median | min | frame interval median / p99 / max (ms) |
| --- | --- | --- | --- |
| baseline, desktop high | 60.26 | 58.44 | 16.6 / 18.2 / 51.3 |
| **R5, desktop high** | **60.27** | **59.12** | 16.6 / 18.3 / 21.1 |
| baseline, emulated phone medium | 60.03 | 57.57 | 16.6 / 21.5 / 35.3 |
| **R5, emulated phone medium** | **60.03** | **56.25** | 16.6 / 21.1 / 36.7 |

Unchanged. (A first attempt ran on SwiftShader, software rendering; it was discarded as not comparable.)

**Security.** The bridge is read-only, and every command goes through coco_web's gateway (access code, origin
allowlist, STOP latch, dead-man): the CI image probes check both on every push. The browser names no ROS topic to
command COCO (`test/live_gate.test.ts`). New input, the `#level=` link: a hostile-link check
(`tools/r5/hostile_links.mjs`, Chromium and Firefox, **14/14 each**, in Play and the World editor: a deflate bomb,
not base64, wrong version, a 300 kB token, a script in the title, a broken editor state, non-numeric goals). Every
case fails in words or is ignored, with no script run, no dialog and no page error. Found and fixed: (1) the
512 kB cap was checked only *after* full inflation (a few-kB bomb could have inflated without limit), so it now
applies while streaming, plus a token-length cap; (2) the link's editor state was trusted, so it is now checked
field by field (`asLevel`); (3) Play showed a raw Python traceback for a refused spec, so it now shows the reader's
own reason (`boot: SpecError: spec: missing ['robot', 'arena']`). R2's sandbox escape tests: **PASS** in Chromium
and Firefox.

**Screenshots:** [screens/before/](screens/before/) (the live site) and [screens/after/](screens/after/), desktop
and emulated phone landscape: Play, pause menu, SIM, Workbench › World editor. For Gautham's review.

## PRs, merges, deploys, live smoke

- **PR #44 "R5 · Live ROS 2"**: CI, Paper and Lab green on the exact head `f0e3de4` (WebKit determinism included);
  self-review on the PR; merged with a merge commit as **`78b662b`**. The image workflow on main `78b662b`: success
  (pushes `latest`). **Deploy run 45956408353: success.**
- **Live smoke (`tools/r3/live_smoke.mjs`): PASS 9/9**: a tab opened before the deploy showed "New version ready"
  without a reload; title; Play (Fetch Rush, COCO moves under AUTO); Compare; Workbench experiment; Studio A*;
  Leaderboard; Learn; 0 page errors. [data/r56/smoke/](data/r56/smoke/)
- **https → ws://localhost, from the public site, with the published image** (`ghcr.io/gauthamcodes/coco-ros2:latest`
  pulled from GHCR, digest `sha256:65fea6ad…`, healthy in 35 s). Found: **Chromium 156 blocks it**
  (`net::ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS`) and **Firefox 157 holds it on its local-network prompt**,
  until the visitor allows the site to reach the local network; with that permission given (`--allow-local-network`:
  the visitor's Allow), **Chromium and Firefox 11/11 each** from `https://gauthamcodes.github.io/coco-labs/`: the real
  graph (36 nodes, 184 topics), W drove COCO 0.62 m / 0.56 m through the arbiter, a Nav2 goal succeeded, STOP latched
  and held (0.000 m), release, SIM LIVE, disconnect. [data/r56/live_from_https/](data/r56/live_from_https/)
  The site's words for a refused connection were wrong ("nothing answered … is the container running?"), so they
  now name the browser's prompt, or the denial when Chrome reports one, and the Connect sheet mentions the prompt up
  front: follow-up PR (below).
- **PR #45** (the local-network words): CI, Paper and Lab green on the exact head `ee63f81`; merged as **`02a7282`**;
  **deploy run 45971894923: success**; live smoke **PASS 8/8** ([data/r56/smoke_45/](data/r56/smoke_45/)). On the
  live origin, without the permission (headless Chromium: state "prompt"): the Connect sheet shows the prompt note,
  and the refused connection's words end "…choose Allow (Chrome and Firefox ask before a website can reach
  localhost)" ([screenshot](data/r56/live_from_https/chromium_denied_words.png)). With it, from the live site:
  **Chromium and Firefox pass** again: drive 0.59 m / 0.54 m (teleop through the arbiter), a Nav2 goal executing
  (22-point plan), STOP held at 0.000 m ([data/r56/live_from_https_after45/](data/r56/live_from_https_after45/)).
- Disk: on the laptop's Docker (containerd image store) the pulled image takes **5.42 GB** (1.18 GB of compressed
  layers kept beside the unpacked 4.2 GB). The README now says so.

## Questions for Gautham

1. Image size: 3.94 GB of the 4.0 GB budget (1.4 % left). Raise the budget, or trim (e.g. Gazebo's GUI libraries)?
2. foxglove_bridge's ignored `client_topic_whitelist` is an upstream bug (source: parsed, never checked). Report it
   upstream (your account), or leave it?
3. The Depot's actors in LIVE and in packages: add their scenario driver to the image (a moving, yielding forklift
   in LIVE), or keep them still?
