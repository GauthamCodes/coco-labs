You are implementing Milestone M5 · Focus and polish of COCO Lab, and nothing beyond it.

The goal: turn the existing product into a focused, good-looking app with three doors (Play, Compare, Research), fix the known defects, cut the agents' startup overhead, and prepare the public v2.0 launch. No new world, no new mini-games, no cloud.

0. Authority and ground rules

Read first, in this order:

README.md (the master plan, revision 3, the authority): all of it, especially sections 1, 3, 5.3–5.7, 7 (M5) and 9.
docs/STATUS.md.
CLAUDE.md. It holds the repository's agent rules until checkpoint M5.2 replaces it with AGENTS.md. Where it conflicts with the README, the README wins.

The README's M5 section defines the checkpoints, acceptance criteria, scope fence and stop conditions. This prompt adds only operational detail; where the two differ, the README wins.

Gautham approved decisions E1–E8 (README section 8) by issuing this prompt.

The working tree is ~/coco_labs_ws/src/coco-labs.

Never use ~/ros2_ws(personal).
Never touch the COCO robot project or its worktrees (~/coco-isaac-21, ~/coco-p03d-target-search).
Read ~/coco_lab_runs/ only; never modify it.

Never, at any point:

delete evidence, tags or releases
create or edit releases
use git clean, git reset --hard, force-push, or delete branches or tags
merge the M5 pull request
invent a number, or mark a Gautham-owned row done

If your environment can't do something (no GPU, no access to ~/coco_lab_runs/, no network, no gh login), record the affected item as pending, needs the laptop and continue. Never estimate a measurement.

Measure on the balanced power profile, on AC. You may switch the profile with powerprofilesctl set balanced, and you must restore the original afterwards. Record the power state and GPU driver version with every measurement. Emulated results are labelled "emulated".

The machine is shared with the robot project. If Gazebo, Isaac or a robot-project batch run is active (ps aux | grep -Ei 'gz|gazebo|isaac|ros2'), run no heavy jobs; report and wait. M5 never needs Gazebo.

Commits and status.

Prefix commits [M5.x].
At the end of every checkpoint, update docs/STATUS.md: the current state, the evidence files, screenshots awaiting review, and the exact next step. From M5.2 on, append the checkpoint history to docs/v2/STATUS_HISTORY.md.
Continue between checkpoints without asking, unless a stop condition fires.
1. Checkpoints
M5.0 Setup
Sync main. Run git status (it must be clean, or stop and ask), git fetch origin, check out main, then git merge --ff-only origin/main. Confirm main contains the M4 merge 6c286b7.
Create the branch v2/m5-focus.
Install the README.
Copy ~/Downloads/README.md over README.md, byte for byte.
Check that line 1 is # COCO Lab v2 — Master Plan: Play, Compare, Research, and confirm the copy with cmp.
Record its sha256 in STATUS.md.
Record the decisions. Add dated plan-change log entries in STATUS.md for E1–E8, with the reasons from README section 8.
Gautham's notes. If ~/Downloads/coco_test_notes.md exists:
Commit it to docs/v2/usability/2026-10-pre-m5.md.
Copy its phone numbers into the Gautham rows in STATUS.md, as "recorded by Gautham", with the phone model.
Apply decision D1: if the phone result fails (under 30 fps, or first computation over 10 s), set the phone default camera to top-down.
Turn every usability observation into a line in docs/v2/M5_DESIGN_INPUTS.md. Checkpoints M5.4–M5.7 must address each line or say why not.
If the file doesn't exist, note that in STATUS.md and continue.
Save this prompt (everything below the line) as docs/v2/M5_PROMPT.md.
Baseline.
Use the pinned toolchain: Node from lab_web/.nvmrc (a pinned Node 24 may already sit under ~/coco_v2_ws/node), and the Python venv used by earlier milestones.
Run the three suites: package tests, lab_web typecheck plus vitest, and build-tool tests.
Record the counts, toolchain, power state and driver.
M5.1 Defects

Each fix gets a regression test.

Bound every share-link field (race z=, the older s=, challenge, replay and run links).
Limits: derive them from the longest legitimate committed link times a stated margin: maximum ticks, maximum inputs, maximum encoded size, maximum first tick.
One place: put the limits in one shared place used by both the browser and coco verify.
Failure: refuse within 50 ms with a clear message.
Tests: cover every field, plus the crafted huge-first-tick case from the Codex review of PR #23.
State hash v2.
Audit everything that can change the model's behaviour. The planner's hand-back goal is known to be missing; record any other gap you find in an ADR (docs/v2/adr/00NN-state-hash-v2.md).
Define v2 to include all of it. Links record their hash version.
v1 links must still verify under v1: every committed link, all golden traces, and every flat-scene determinism hash, unchanged.
Add a v2 determinism run: 100 sessions across Chromium, Firefox, WebKit and Pyodide-in-Node.
Race integrity. During a race, lock the planner, Grasp and Autonomy controls, with a toast saying why. Test that a race run cannot use them.
Case File robot.
Load robot_low.glb before the recording data, and cache it across Case Files.
Measure the first frame with the real robot mesh on emulated 4G for 100 of 100 Case Files; the budget is 2 s or less.
Goal picking in the perspective camera.
An assessment once saw a floor click just ahead of the robot produce "Goal reached · 1 expansion · 0 m". Reproduce it with a test hook that clicks known floor points in the follow and orbit cameras.
Assert that the goal cell lands within one cell of the intended point. Fix it if real.
The "v1 site reproducible" workflow has failed since before M4. Fix it; or document why and disable it, with a note in STATUS.md.
M5.2 Agent overhead

Use git mv wherever possible, so history follows the content.

Archive the robot-stack lore. Move the robot-stack history in CLAUDE.md (everything about v1/M7/COCO 2.0, the web platform P0.x, episodes, language traps, simulator hygiene) verbatim to docs/archive/robot_stack/CLAUDE_robot_stack.md.
Write AGENTS.md, 250 lines or fewer (target about 200), for every agent:
authority and read-first order
the drift test
the invariants and integrity rules in short form
evidence classes
git rules
how to build and test (exact commands)
workspace and toolchain paths
measurement rules and visual review
the final report template
pointers to the archives
Replace CLAUDE.md with a few lines: @AGENTS.md plus one sentence saying AGENTS.md is canonical.
Slim docs/STATUS.md.
Move the current file to docs/v2/STATUS_HISTORY.md.
Write a new docs/STATUS.md of 200 lines or fewer: current SHA and branch, milestone and checkpoint, open Gautham rows, open questions, the plan-change log, and the next step.
Slim PROJECT_STATE.md. Move it to docs/archive/robot_stack/PROJECT_STATE_full.md, and write a short pointer page in its place.
Move the RL-era root scripts (train_curriculum.sh, train_curriculum.sh.next, resume_curriculum.sh, overnight_chain.sh, watch_training.py, and any other RL-only root script you find) to coco_rl/scripts/.
Search the repo (tests, Dockerfile, docs, CI) for references and update them.
Run the coco_rl tests and any test that referenced them.
Remove the committed test cache: git rm --cached on the files under the root node_modules/ (test caches only), and add the directory to .gitignore. This is the only deletion allowed in M5; list the files in the commit message.
M5.3 Code shape

No behaviour change in this checkpoint.

Split lab_web/src/arena/ArenaApp.tsx into a scene core (renderer, cameras, controls, session and the worker client) plus three shells: Play, Compare, Research.
Lazy-load the modes, and put three.js in its own long-cached chunk (manualChunks or the Rolldown equivalent).
Prove behaviour is unchanged. The existing suites, screenshot tests, URL-form checks, replay checks and coco verify must all pass before and after.
Measure the bundle sizes per route.
M5.4 Design system "Night Shift"
Tokens. One tokens file (CSS variables plus a TypeScript export) holding colours, type scale, spacing, radius, elevation and motion, with dark (default) and light themes.
Keep the computation colours' fixed meanings (README section 5.4), tuned for dark.
Check them under deuteranopia and protanopia simulation, and record the result.
Fonts and icons.
One display face and one UI face under the OFL, self-hosted (for example through @fontsource packages).
One permissively licensed icon set (for example Lucide or Phosphor).
Add every font and icon set to the asset manifest with licence, source and checksum.
Direction. Apply a deliberate aesthetic, not template defaults: a dark, calm warehouse after hours, where the computation is the only thing that glows.
Three reference screens: the title screen, the Play HUD and Compare with two panes.
Render them for real, not as drawings.
Commit screenshots at 1440 × 900 and 844 × 390 to docs/v2/data/m5/screens/reference/.
List them in STATUS.md for Gautham's review.
Carry on without waiting; apply his recorded feedback at the next checkpoint.
M5.5 App shell and routes
Title screen. It is the attract mode:
a light 3D scene of COCO idling, which loads first
three large cards: Play, Compare, Research
an About link
"Press any key" starts Play
Pyodide warms up behind it
About page:
what COCO Lab is
the evidence classes, in plain words
a link to Live Stack (simulated)
the /v1/ archive
credits and licences
Settings drawer (gear icon, in every mode): quality tier, wall height, sound, key bindings, theme, reduced motion, through the preferences module.
Route migration.
Every existing URL form keeps working and lands in its new home:
?view=arena → Play › Free roam (a replay= or run= parameter opens the run in Research's viewer)
?view=learn&mission=X → the Compare tour X
?view=casefiles → Research › Recordings
?view=play and the challenge links → Play
?view=live → still the Live view, linked from About
the 22 v1 forms → unchanged
Extend the URL-form test to every form, including M3 and M4 links (s=, z=), with 0 console errors each.
M5.6 Play
The full-screen 3D HUD, in the corners, on semi-transparent panels:
Position	Contents
Top left	Objective and timer
Top right	Minimap: COCO's own occupancy map
Bottom left	Speed in m/s, the two wheel-speed bars, and the command source (YOU, PLANNER, ASSIST, STOP)
Bottom right	Action buttons
Corner	The MODEL · kinematic badge
Centre	Short toasts that fade
Camera and world.
The follow camera becomes the three-quarter view (about 4–6 m back, pitched down 35–45°), sprung and collision-aware.
Walls display at half height by default in Play. This is a display setting; the model's geometry and hashes are unchanged.
Walls get lighter top caps, darker sides and edge lines.
LiDAR as a scan area. Draw it as a filled, translucent visible region with bright hit points. Remove per-ray drawing outside Compare's Inspect level. This fixes the moiré.
Robot vision (X) cycles Play's overlays: off → scan area → the planner's frontier and heatmap → the costmap → localization particles. Re-bind any conflicting key, and update the help overlay.
Game cards and scorecard.
The five challenges and Race the ghost become game cards with stars and personal bests.
A full-screen scorecard shows the score broken into its metrics, your path against the ghost on the minimap, the stars with their public thresholds, and buttons for Replay, Try again and Share.
A 10-second instant replay uses the existing timeline and keyframes.
First-run tutorial (about 20 s, skippable, remembered in preferences): drive to a glowing marker, click a goal and watch the planner, press X to see robot vision.
Free roam.
Phones.
Landscape is full-screen, with the joystick bottom left and the action buttons bottom right.
Portrait in Play shows a "rotate your phone" card.
The desktop never shows the joystick.
The Focus criterion. In Play at 1440 × 900 and at 844 × 390, there is no page scroll and at most 8 always-visible controls. Write a test that counts them.
M5.7 Compare
Panes.
2 or 4 panes rendered as scissored viewports in one WebGL context.
A synced camera, top-down by default with a 3D toggle.
The same map, start, goal and seed for every pane.
Portrait layout: stacked panes.
Costmap layers in coco_lab, emitted as a new additive costmap.layers family:
static, inflation, obstacle (from LiDAR) and combined
Nav2's documented inflation formula: lethal 254; inscribed 253 within the inscribed radius; beyond it, (253 − 1) · exp(−cost_scaling_factor · (d − inscribed_radius))
unit tests against hand-computed values
if a recorded Stack costmap exists in the repository's Case Files or evidence, compare against it and label the result
sliders for inflation radius, cost-scaling factor and robot radius, replanning every pane
hover shows a cell's cost
the lethal and inscribed bands outlined
Families.
Required: global planning (BFS, Dijkstra, A*, greedy, weighted A*, D* Lite), local control (the DWA-style sampler, pure pursuit, MPPI) and localization (MCL with and without injection, EKF).
Mapping: only if it fits; otherwise park it in docs/IDEAS.md for M7.
Views.
A difference view: cells only A expanded, only B, or both; both paths drawn.
A lockstep timeline across panes.
A results strip: expansions, path length, path cost, minimum clearance, compute time with the device named, success.
Guided tours.
Migrate missions 1–7 into tours that open Compare preset to their lesson. Keep every claim and evidence reference; the CI claims check must pass.
Add the five real-story tours, each sentence carrying its evidence reference:
The 44 mm band (robot_radius 0.20 → 0.25; find its evidence under docs/agents/)
the A* myth
D* Lite's 2.9×
the Lab 5 hairpin
Run 15
If an evidence file can't be found, stop that tour and report it. Never write the claim without its evidence.
M5.8 Research: the Recordings library
Replace the list of about 70 run links with a searchable library of every Case File and converted run.
Filters: level, algorithm or controller, outcome, and evidence class.
A "failures" quick filter.
Each card opens the recording in the viewer.
The experiment builder is not in M5.
M5.9 Caching and counter
Service worker scoped to the site:
Precache the app shell and content-hashed assets (JavaScript, CSS, Pyodide files, the coco_lab wheel, 3D assets).
Strategies: cache-first for hashed assets, network-first for index.html.
Cleanup: old caches are cleaned on activation.
Content: static assets only, never personal data.
Tests: a hard reload after a deploy picks up the new version; the site works with the service worker disabled.
Measure: warm start on emulated 4G (target: live model ready in 3 s or less).
Visit counter, cookieless and aggregate-only, wired behind one site-config value. While the value is empty, the page makes zero third-party requests (test this). Document in docs/v2/COUNTER.md how Gautham turns it on with his own counter ID. Do not create any account.
M5.10 Launch preparation (drafts only)
docs/releases/v2.0.md, rewritten for the three-mode app, with every number traced to docs/RESULTS.md
a 60–90 s demo-recording script (title → Play → Compare → Research), recorded locally if the laptop allows
docs/v2/USABILITY_TEST_M5.md, from the README's usability row
the phone guide, updated for Play's landscape layout
M5.11 Measure and close
Measure every agent-owned criterion in the README's M5 table.
Write docs/v2/M5_RESULTS.md, and append the numbers to docs/RESULTS.md.
Push the branch and open a pull request into main with gh pr create. Do not merge it.
2. Stop and ask Gautham if
A v1 hash or golden trace changes.
An old URL form can't be given a new home.
A claim would lose its evidence in a move.
The Focus criterion can't be met without removing a capability (rather than moving it).
The checkout has uncommitted or unpushed local work at M5.0.
Any step would require deleting evidence, a release or a working public URL.
3. Final report (end of every session)

Fill this in and make docs/STATUS.md match:

Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Gautham's notes: found / not found; phone result; design inputs addressed
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements taken (device or emulation, power profile, driver, conditions):
Acceptance criteria: each → met / not met / pending Gautham / pending laptop, with evidence:
Screenshots awaiting Gautham's review:
Files moved or removed (full list) and why:
Decisions recorded (ADRs) and plan-change log entries:
Deviations from the plan, and why:
Ideas parked in docs/IDEAS.md:
Stop condition hit? which one:
Questions for Gautham:
Next step according to README.md:
