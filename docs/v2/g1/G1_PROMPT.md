# G1 · Game Look — milestone prompt (as issued, 2026-10-20)

> Saved verbatim in substance by the agent at G1.0. Headings and tables were
> re-flowed into Markdown; no instruction was added, removed or reworded.

You are building G1 · Game Look for COCO Lab (repo GauthamCodes/coco-labs, site
https://gauthamcodes.github.io/coco-labs/). From now on, Claude Code does all COCO Lab
work; Codex is no longer used.

The goal, in Gautham's words: when you control the robot, it should look and feel like a
mobile phone game, like PUBG Mobile or a racing game, easy enough for anyone to pick up
and understand. The world itself must change drastically so it becomes attractive.

Today the phone version looks like a web page: stacked buttons, long lists of run links,
the ?perf overlay covering everything, a black floor with white boxes, and text
explaining things instead of the game showing them. All of that changes.

## 0. Setup and ground rules

**Branch.** Clone the repo. If PR #25 is merged, branch v2/g1-game-look from origin/main;
if not, branch from origin/v2/m5-focus and note it.

Then `git merge origin/v2/m6-foundations` into your branch. You need the COCO Depot, the
object catalog, Grasp Assist and the Fetch Rush rules. This is a one-time permission to
merge that branch into yours; never into main.

If another session pushes to v2/m6-foundations later, merge it again at a checkpoint
boundary.

Read README.md (especially §1, §3 invariants and integrity rules, §5.3–5.9 and §9),
AGENTS.md, docs/STATUS.md, and docs/v2/data/m5/closure-20261020/REPORT.md. Read evidence
in targeted pieces; never read generated code, Case File data or history files in full.

**Paperwork.** Save this prompt as docs/v2/g1/G1_PROMPT.md. Keep progress in
docs/v2/g1/G1_STATUS.md: the current checkpoint, the next step, laptop items, questions.
Add one dated entry (2026-10-20) to the plan-change log in docs/STATUS.md: "G1 · Game
Look inserted before the M6 UI phase; Claude Code replaces Codex; G1 absorbs the M6 Depot
rendering, Grasp Assist visuals and Fetch Rush HUD." Update README §7 to match. That is
the only README change.

**Rules that still hold.**

The model and the truth:

- Rendering never changes the model (invariant 11).
- Game rules are not physics (13).
- No browser physics engine (10).
- Every world stays a real Gazebo world (12).
- Determinism hashes are versioned (5).
- Evidence labels stay truthful: in Play they move into a small ⓘ chip, not banners.

Assets and storage:

- Asset licences (integrity rule 8): your own work, procedurally generated, or CC0
  (Kenney, Poly Haven, ambientCG), each recorded in the asset manifest. Fonts must be OFL
  and self-hosted, so the service worker caches them and no third-party request is made.
- Storage goes through the prefs module (rule 7).

Git and evidence:

- Never merge to main, never press or trigger "Deploy site", and never create releases.
- No force-push, git reset --hard, git clean, or branch or tag deletion.
- Never delete evidence. Never invent numbers.
- Label cloud and emulated results as such; MEASURED needs a real device.
- The five-person usability test stays Gautham's.
- Commits: one per checkpoint, prefixed [G1.n]. Push after each.

**Decorative honesty.** A thing that looks solid must be solid in the model and in
Gazebo, and a thing the robot can pass through must not look solid. Decoration is allowed
only on walls, ceilings, outside the drivable area, or flat on the floor (paint, decals).
Add a test that every decorative mesh either matches a collision footprint or lies
outside free space or below 2 cm in height.

## 1. The look we are going for

### 1.1 Art direction: "Night Shift Depot"

It is night inside a big robot warehouse. The look is dark and moody, with crisp light;
every surface should look like it belongs to a real place.

| Element | Treatment |
| --- | --- |
| Floor | Polished concrete: subtle tiling noise, roughness variation, light pools under the fixtures. Painted lane lines, yellow/black hazard stripes at crossings, large painted zone numbers ("A1", "DOCK 2"), drop-zone squares that glow when they are a target |
| Walls and structure | Modular panels with trim, steel columns, roll-up doors at the dock, a fence-mesh workshop maze, the mezzanine with railings and a ramp with chevrons |
| Racks | Pallet racking with boxes, crates and shrink-wrapped pallets (instanced, varied by seed) |
| Light | Cool blue-grey ambient; warm LED strip fixtures overhead; emissive EXIT signs; a dock light spilling in. Ambient occlusion and light are baked at build time (zero runtime cost) |
| Atmosphere | Light depth fog, faint dust in light shafts on the high tier only, and a dark ceiling with visible fixtures (no sky indoors) |
| The robot | COCO's real model, with orange accents, a headlight cone, an emissive status LED strip (green manual, cyan autonomy, red STOP), a soft blob shadow on low, and a real shadow on high |
| Moving actors | Forklifts with flashing amber beacons and walkers in hi-vis vests (low-poly), exactly on their collision bodies |
| Palette | Background #0E1116, surfaces #1B2230 / #2A3344, COCO orange #FF7A1A, sensor cyan #22D3EE, plan magenta #F43F8E, safe green #34D399, danger red #EF4444, hazard yellow #FACC15. Color-blind safe: shape and pattern also carry meaning |
| Type | A game display face for HUD numbers and headings (Chakra Petch or Rajdhani, OFL, self-hosted) and Inter for small text; numbers tabular |

The existing COCO arena (the "Proving Ground") gets a matching "test lab" look: light-grey
lab floor with grid lines and calibration marks, panel walls with trim, the same lighting
style and baked AO. It must still be byte-identical in the model; only the visuals change.

Build pipeline:

- Generate textures procedurally at build time (Node or Python, seeded) or take them from
  CC0 sources, compressed to KTX2, with props and meshes from the World Spec v3 kit.
- Budgets per world:

| Tier | Download (gzip) | Triangles | Draw calls |
| --- | --- | --- | --- |
| low | ≤ 1.2 MB | ≤ 150k | ≤ 120 |
| high | ≤ 3 MB | ≤ 400k | ≤ 250 |

- Instancing for repeats. Post-processing (ACES tone mapping always; bloom on emissives on
  the high tier only) must hold 60 fps on the emulated Nothing Phone (1) at medium.

### 1.2 The Play HUD (landscape, built for the Nothing Phone (1) at about 915 × 412 CSS px; scale for others)

The layout mirrors mobile shooters and racers: left thumb moves, right thumb acts,
information sits at the edges, and the centre stays clear. Everything respects
env(safe-area-inset-*).

| Position | Element | Details |
| --- | --- | --- |
| Left half (below the top 25%) | Floating joystick | Appears where the left thumb lands; ghost at rest bottom-left, 130 px; travel radius 60 px; dead zone 8%; semi-transparent. Drag beyond the ring to "nudge" the base along (as in PUBG) |
| Bottom-right, thumb arc | Primary action, 88 px | Context-sensitive and labelled with an icon plus a word: GRAB when Grasp Assist has a valid target (the target glows and a ring fills while it approaches), DROP when holding at a drop zone, GO when a goal is set and autonomy is off. Greyed with the reason when nothing is possible ("Too wide", "Out of reach"), taken from Grasp Assist's refusal codes |
| Around the primary, 56 px | AUTO, CAM | AUTO toggles autonomy (planner drives to the goal or next order). CAM cycles chase → top-down tactical → free orbit |
| Right edge, above the arc, 68 px | STOP | Red octagon. Always visible, never covered, works with any finger at any time (keep the M5 review's secondary-touch fix). Latched; the same button releases it with a hold |
| Top-left | Minimap, 112 px circle | North-up or heading-up; walls, robot arrow, planned path in magenta, order targets as icons. Tap opens the full tactical map: pinch and drag, tap to set a goal (this replaces "click the 3D view to set a goal" on phones) |
| Top-centre | Objective pill | "Deliver 1/3 · ⏱ 1:42 · ★★☆", or in Free Drive, "Free drive · Depot". Short, never wraps |
| Top-right, 44 px | Pause ⏸ and Vision 👁 | Vision toggles "Robot vision": LiDAR rays, costmap and inflation, the plan and the local trajectories drawn in a holographic scanner style over the world. This is how the glass box lives inside the game |
| Bottom-centre | Speed gauge | A small arc showing the real model speed in m/s, plus a mode chip: MANUAL / AUTO / STOPPED. No fake gauges: show only quantities the model really has (no battery, no fuel) |
| Centre-low | Context toasts | One line, 2 s: "Can in range: tap GRAB", "Forklift ahead!", "Delivered +1". Plus a contact flash at the screen edge, toward the hit, and haptics |

- Count: at most 8 always-visible controls (joystick, primary, AUTO, CAM, STOP, minimap,
  pause, vision = 8).
- Nothing else on the Play screen: no run links, no algorithm buttons, no tick sliders, no
  paragraphs, and no ?perf unless the URL asks for it. When it does, it is a small
  collapsible chip, not a full-screen overlay.
- Portrait Play: show the rotate card with STOP.
- Desktop: the same HUD with key hints on the buttons (WASD or arrows, G grab, F auto,
  C camera, V vision, Space STOP, Esc pause), mouse-drag orbit and wheel zoom.
- Gamepad API support: left stick drives, A grabs, X toggles AUTO, Y camera, B STOP,
  Start pause, triggers as throttle and brake scaling within the robot's real limits.

Cameras:

- Chase cam (default): behind and above the robot, spring-damped, looks slightly ahead in
  the direction of travel, and pulls in when a wall would block the view (a ray-cast
  against the render meshes).
- Top-down tactical, for planning.
- Free orbit: two-finger orbit and pinch zoom, as in M5.

### 1.3 Around Play: a real game shell

- **Title:** a full-bleed 3D hero shot of COCO in the Depot under the lights, a slow
  camera move, the logo, a big PLAY button, and three smaller cards: Compare (see
  algorithms race), Research, Learn. A small ⓘ shows what's real (MODEL, STACK and so on).
- **Loading screen:** the 3D world appears at about 3 s and the live model at about
  9–10 s, so hide the wait behind a loading screen.
  - Show the world rendering behind a progress bar driven by the real stages (worker →
    Pyodide → coco_lab → Arena), never a fake timer.
  - Rotate one-line tips ("The magenta line is the plan COCO's planner found").
  - Allow camera orbit while loading. The PLAY button lights when the model is ready.
- **Mode select:** cards for Fetch Rush (playable in G1), Free Drive (Depot or Proving
  Ground), and Rush Hour, Fog Scout and Lost & Found shown as locked "coming soon" cards.
  Each card shows best stars from prefs.
- **First-run tutorial** (about 20 s, skippable, remembered in prefs): a ghost thumb shows
  "drag to drive", "tap GRAB when the can glows", "STOP stops everything", "👁 shows what
  COCO sees".
- **Pause menu:** Resume, Restart, Settings (quality, haptics, sound, frame-rate cap,
  controls hints), Exit.
- **Results screen:** stars, time, deliveries, contacts, and path length against the
  planner ghost, with a button "Watch how the planner did it" that opens the same run in
  Compare. Stars come from reference results (M6 GAMES.md), never hand-picked.
- **Sound:** short synthesized WebAudio effects (motor hum scaled by real speed, grab
  clunk, delivery chime, STOP buzz, contact thud), muted until first interaction, toggle
  in Settings. Your own synthesis; no files needed.

Compare, Research and Learn keep their M5 function but get the same visual language (dark
theme, game type, card layout, the holographic algorithm style). The long lists of run
links move into a searchable Recordings library, never inline on a play surface.

## 2. Checkpoints (in this order; everything committed and pushed at each)

**G1.0 Baseline**

- Set up as in §0.
- Build, then capture before screenshots with the emulated nothing-phone-1 profile
  (landscape and portrait) and at 1440 × 900. Cover: title, Play, Compare, Recordings.
- Run all suites as the baseline. Commit the screenshots to docs/v2/g1/screens/before/.

**G1.1 Art direction and HUD mockups**

- Write docs/v2/g1/ART_DIRECTION.md from §1.1.
- Build static HTML mockups of the Play HUD (Fetch Rush and Free Drive), the title, the
  loading screen, mode select, pause and results at 915 × 412 and 1440 × 900. Render them
  to PNG under docs/v2/g1/mockups/.
- Don't wait for approval. Continue, and list the mockups in G1_STATUS.md under "Gautham:
  look at these".

**G1.2 Game shell** — Title, loading screen (real stages), mode select, tutorial, pause,
results, settings, routing between them, and the Recordings library. Remove the stacked
web-page controls from every play surface.

**G1.3 Play HUD and controls**

- Build the floating joystick, primary action, AUTO, CAM, STOP, minimap and tactical map,
  objective pill, Vision toggle, speed gauge, toasts, contact flash, haptics, desktop keys
  and gamepad, all wired to the existing control path (cmd_vel arbiter semantics).
- Input tests (Playwright with touch): one-finger drive, a second finger on STOP while
  driving, joystick nudge, minimap goal set, gamepad (mocked), a keyboard-only
  playthrough.
- Measure latency: touch-to-motion must not get worse than M5's.

**G1.4 Cameras** — Chase (spring-damped, look-ahead, wall pull-in), tactical and orbit;
smooth transitions, no clipping through walls in 20 scripted paths.

**G1.5 New worlds**

- Depot visuals generated from World Spec v3: the kit meshes, procedural textures, baked
  AO and light, instanced props, decals, actors on their collision bodies.
- Proving Ground restyle.
- Quality tiers and budgets from §1.1.
- The decorative-honesty test from §0.5.
- The Gazebo SDF still comes from the same spec. Check that the generated SDF is
  unchanged, or changed only in visual elements, and that gz sdf -k passes where
  available (otherwise laptop).

**G1.6 Fetch Rush, playable**

- Wire the M6 rules and Grasp Assist into Play on the Depot: orders, drop zones, timer,
  stars, the planner ghost (toggle), contacts, and the results screen.
- Show Grasp Assist's stages in the world (target glow, approach ring, arm reach), with
  Vision showing the detail.
- Determinism: a played session replays to the same hashes from spec, seed and input log
  in CPython and in Pyodide in Node. If the two differ, see G1.8; don't hide it.

**G1.7 Robot vision and Compare restyle**

- Holographic scanner style for LiDAR, costmap layers (lethal, inscribed, inflation
  gradient) and plans, readable on the dark floor and colour-blind safe.
- Compare in the new visual language: two- and four-pane layouts, hover or tap inspect,
  the results strip. Check its correctness tests from M5 still pass.

**G1.8 M5 carry-overs** (Gautham's answer to Codex's question: yes, authorized)

- The rasterization discrepancy.
  - Find why LiDAR rasterization gives different obstacle costs in CPython and Pyodide
    (first numeric difference at tick 1).
  - Prime suspects: floor or round at cell boundaries, float-to-int conversion of
    negative values, math against NumPy-free paths, and sum order.
  - Fix it so both runtimes agree, bumping the state-hash version as invariant 5
    requires. Never edit old goldens in place; add v3 goldens and keep v2 replayable.
  - Then add the native-vs-Pyodide CI gate: global families exact, continuous families
    1e-9.
- Update isolation.
  - Version every runtime, data and asset URL by build ID or content hash.
  - A new version waits, with a "New version ready" notice offering Save run and Reload.
    There are no forced reloads mid-run, and old caches are deleted only when no page of
    that build is open.
  - The A/B probe must report openDocumentMixed: false; add it as a CI regression test.

**G1.9 Performance**

- Emulated Nothing Phone (1) (4× CPU throttle): Play in the Depot at the medium tier must
  hold 60 fps median over 10 minutes. Record the minimum and p95 frame time. Also record
  the title and loading timings.
- Desktop: run the same checks with the cloud's software GPU, labelled as such.
- Check: title-critical JS ≤ 350 kB gzip; Depot assets within budget; no console errors;
  no WebGL context loss in a 30-minute emulated soak.
- Laptop: real GPU fps on both GPUs; the real Nothing Phone (1) over USB/CDP when
  `adb devices` lists it, including a 10-minute heat run; choosing the default tier.

**G1.10 Close**

- Capture after screenshots matching G1.0, and write a side-by-side
  docs/v2/g1/BEFORE_AFTER.md.
- Rerun every suite plus v1 hashes, the four-engine v2 comparison, links and URLs.
- Write docs/v2/g1/G1_RESULTS.md with every number and its conditions.
- Push, then open a draft PR into main: "G1 · Game Look". Don't merge, don't deploy.

## 3. Stop and report if

- A model or golden hash changes for any reason other than G1.8's intended, versioned fix.
- Some art would need a non-CC0 or unlicensed asset.
- A HUD element would need a quantity the model doesn't have.
- The Depot can't hold 60 fps at medium on the emulated phone after two optimization
  passes. Report what costs the most; don't silently cut the art.

## 4. Final report (end of every session; make G1_STATUS.md match)

```
Checkpoints completed (G1.x):
Branch, start SHA → end SHA, pushed, clean; merged-in branches and SHAs:
Environment: cloud or laptop (CPU, GPU or software renderer)
Per checkpoint: what changed | evidence | screenshots
Tests: suite → passed / failed / skipped (before vs after)
Hashes: v1 unchanged? v2 replayable? v3 introduced (why)? CPython vs Pyodide parity per family
Performance: emulated phone fps (median / min / p95), title and loading stages, asset sizes, draw calls, triangles; laptop and real-phone results or "pending: laptop"
Gautham, look at these: mockups and screenshots (paths)
Laptop items pending:
Questions for Gautham:
Next step:
```
