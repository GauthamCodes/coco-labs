# M5.6 · Play

Implementation base c5afb3d, branch v2/m5-focus. Evidence class TESTED / MODEL,
or recorded STACK where labelled. Checkpoint implementation and closure checks complete.
No performance-budget or real-phone pass is claimed here.

## Change

Full-screen corner HUD: objective/clock, the robot's known occupancy map (or
its emitted built-map keyframe), speed, wheels and command source, action
buttons, evidence badge and fading notices. Detailed controls and planner
inspection remain in the game menu through Settings. Desktop has no joystick,
including in that menu. Planar recordings retain their missing-height label.

Follow uses a sprung 5.2 m / 40° boom, shortened before warehouse surfaces.
Tall display meshes scale to half height by default in Play, retaining real
cap faces, shaded sides and edges. Model geometry and hashes do not change.
LiDAR displays a translucent fan and hit points; individual rays are confined
to Compare Inspect. X cycles off, scan, planner frontier/heatmap, static costmap
and model-emitted localization particles. Inactive localization is labelled;
rendering never turns an estimator on or modifies the run. M5.7 adds the
costmap layer family and completes that overlay's richer data.

Six existing games have cards, stars and saved bests; Free roam remains.
Scorecards retain all real metrics, public thresholds, evidence and sharing;
robot drives show the scored path against the reference ghost on its map.
Replay seeks the existing timeline rather than simulating another run. Shared
decision scores display their submitted choices. The first-drive tutorial uses
a real drive, real goal/planning and vision; completion/skip is remembered.
Skipping lives in Settings or Escape, keeping the tutorial within Focus too.

Phone controls respect safe areas, use a 128 px joystick and thumb arc, and
request fullscreen/landscape on game start. Portrait games show a rotate card.
The installed app can rotate again when leaving Play. Pointer surfaces prevent
page gestures/selection. Hidden rendering pauses without advancing the model
clock on return. Phone rendering caps at 60, optional 120; automatic quality
starts medium (DPR cap 1.5), high 2, low 1. Persistent known-visible stalls now
participate in the existing quality controller. Haptics are optional and fail
silently. Original Apache-2.0 icon and manifest are in DESIGN_ASSETS.json.

## Verification

- Before: packages 3534 / web 466 / tools 195. Packages remain 3534 and tools
  195 passing; web has 477 tests after phone route regression. Final web log:
  `vitest-closure.txt`; typecheck/build/dist logs accompany it.
- `links-cli-verified.json`: 166/166 old and newly generated Play links match
  under their own hash versions; the latest driven-map delta also matches (1/1).
  The four Arena run versions/specs also pass
  their existing browser verifier in the URL suite.
- `closure-urls.txt`: 50 forms plus six archive views, zero errors.
- `challenges-review.txt`: all 15 tested challenge levels valid and reproduced;
  reference answers retain their expected stars; driven map score remains real.
- `replays-review.txt`: five recordings, zero errors.
- `closure-canvas.txt`: five zero-difference scenes against the intentional Play
  baseline. Four original canvases remain unchanged. Attract now uses the
  full-screen 1000×900 canvas and vision-off display. Previous PNGs/JSON are
  preserved under `screens/pre-play-hud/`, with original checksums. No MCAP
  golden trace, Python model, World Spec or v1 state hash changed.
- `defect-regression.txt`: six actual follow/orbit floor clicks land within one
  cell; race forbidden inputs absent in desktop and both emulated orientations.
- Functional interactions check frozen hash/input log across vision and walls,
  actual scan hits, menu focus, historical replay and hidden pause. Final run
  additionally checks tutorial completion and reload through real controls.
- `closure-free.txt`: 7 / 7 / 8 / 1 controls in desktop / compact / emulated
  phone landscape / portrait, including world and joystick. No counting
  exemptions; no page scroll. `closure-games.txt`: 24 additional game/menu
  layouts pass, with phone targets >=48 CSS px. `closure-scorecards.txt`:
  four scorecards reproduce their hash, contain focus and reopen after replay.
- `closure-interactions/interactions.json`: real drive → goal/search → X
  completes the tutorial and stays complete after reload. Settings skipping,
  no desktop-menu joystick, frozen model hash/log, actual scan hits, modal
  focus, timeline replay and hidden pause all pass with zero console errors.
- Final layout/capture index: `../screens/play/README.md`. Soft review pending.

## Conditions, owner rows and next step

Node 24.21.0; Python 3.12.3 pinned workspace venv. Functional suites are not performance runs.
Initial captures record balanced/AC; some resumed 2026-10-17 checks record
balanced on battery (nonstandard), and final closure captures record balanced/AC.
Reported NVIDIA driver 580.178.04; actual renderer is retained in layout data.
Software GL, CPU 4× proxy and emulated viewports are not Adreno measurements.
All diagnostic timing in test logs is excluded from performance acceptance.
Those budgets and overlay-visible first-computation instrumentation remain for M5.11 on balanced/AC. Original power profile unchanged.

Nothing Phone (1) remains absent in ADB. Real Phone criterion stays pending USB;
60/optional120 and automatic tiers are provisional pending its real heat run.
The blank notes stay unchanged; no pre-design observations or owner feedback.
Five-person usability is Gautham-owned and gates launch only.

No whole files moved/removed. Minimap drawing was extracted into its own source
module; prior visual baselines were copied before the intentional update.
No new ADR, plan decision, parked idea or stop condition. Failed/interrupted
artifacts are retained: initial modal focus, stale local assets after rebuild,
daemon interruption and the corrected rotate-card target. Next: M5.7 Compare.
