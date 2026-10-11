# M4 prompt — Part B: Milestone M4 · 3D Arena

Saved verbatim in substance from the owner's prompt of 2026-10-11 (Part B,
with its git section and final-report template). Part A of that prompt
closed M3 (`docs/v2/reviews/M3_REVIEW.md`). The authority is `README.md`
revision 2: where this prompt and the README differ, the README wins.

---

PART B — Milestone M4 · 3D Arena

The M4 goal (README section 7): a visitor opens the site and is inside COCO's arena in 3D. They:

- drive with keys or touch
- hand over to autonomy
- watch every algorithm compute in the world
- drop to top-down to inspect
- race the planner's ghost
- open a Case File in the same world

Everything stays deterministic, measured, honest about being kinematic, and fast on a phone. M4 is the content of the public v2.0 launch, which Gautham publishes after M4 merges and his rows pass.

The checkpoints, acceptance criteria, scope fence and stop conditions are README section 7, M4. This prompt adds only operational detail. Where they differ, the README wins.

## B.0 Setup (M4.0)

- Fast-forward main (--ff-only). If the checkout has local changes, stop and ask.
- Create branch v2/m4-3d-arena.
- Copy ~/Downloads/README.md to the repo root, byte for byte. Check that it begins with `# COCO Lab v2 — Master Plan: the 3D Glass-box Arena` and confirm with cmp. Update the sha256 in STATUS.md.
- Add dated plan-change log entries for D1–D6 to docs/STATUS.md. Then:
  - In docs/STATUS.md, set M3 to closed — agent-measurable criteria, with the merge SHA. List the pending Gautham rows: the phone baseline now, and the consolidated usability test at the end of M4.
  - Update docs/ROADMAP.md (renumbering: cloud batch is M5, interactive sessions M6, hardware M7), PROJECT_STATE.md and docs/v2/DEPRECATIONS.md to match.
  - Update CLAUDE.md with the README's new invariants 9–11, integrity rules 7–8, and agent rules 6–7.
  - Add the README's M4 non-goals to docs/IDEAS.md where they are ideas: gamepad, a second world, perception on pixels, and the four later challenges.
- Save Part B of this prompt as docs/v2/M4_PROMPT.md.
- Run the three suites as the M4 baseline. Record them with the toolchain, power state and driver.

Prefix commits [M4.x]. Update STATUS.md at the end of every checkpoint with:

- what was done
- the evidence file
- screenshots awaiting review
- the exact next step

Continue between checkpoints without asking, unless a stop condition fires.

## B.1 Operational notes per checkpoint

**M4.1 Feasibility gate.**

- Find the sources. Locate COCO's arena SDF world and the robot URDF and meshes (most likely in the frozen gazebo_models and coco_config packages). They are read-only; converted outputs live in the website's asset tree.
- Identify the world the recordings used. From bag metadata and launch files, identify which SDF world the Case File recordings were made in, and convert that one first. Record any variants (for example, the Lab 5 scenario worlds) for M4.7.
- The first conversion may be rough. M4.2 makes it production-quality.
- Weak-device emulation. Measure on:
  - the RTX 4050
  - the laptop's Intel integrated GPU (force the browser onto it)
  - Chromium with 4× and 6× CPU throttling at a phone viewport and device-pixel ratio

  Label emulation results "emulated", never "phone".
- Phone preview (permission 4). tools/preview_phone.sh builds the production preview and exposes it through Tailscale Funnel so Gautham can open it on mobile data. Constraints:
  - static files only
  - a port or path that cannot collide with Live's /ws and /healthz
  - it turns itself off after 2 hours
  - it prints the URL
  - it is recorded in STATUS.md

  If Funnel isn't available, fall back to a LAN preview and note that cold start on mobile data cannot be measured that way.
- Write docs/v2/PHONE_GATE_M4.md. It tells Gautham exactly what to measure (fps with ?perf over 10 minutes, cold start, touch feel) and where to record it in STATUS.md.
- Three reference screenshots in docs/v2/data/m4/screens/reference/:
  - follow camera driving toward the ramp with the planner's frontier on the floor
  - a wide orbit of the whole arena
  - the robot-eye view

  List them in STATUS.md for Gautham's approval.
- Do not wait for the gate. Add a config flag for the phone default (3d or topdown), set to 3d. Whenever Gautham records phone results, apply D1: if they fail, set it to topdown for phones.

**M4.2 Asset pipeline.**

- Choose the conversion tooling, and record the choice in docs/v2/adr/0006-asset-pipeline.md. Prefer tools that run headless in CI and are pinned.
- The asset manifest (docs/v2/ASSETS.md plus a machine-readable file) gives each asset's source, licence, checksum and size. COCO's own CAD meshes are licensed as Gautham's own work. Third-party assets must be CC0 or equivalent.
- CI fails if the first-scene download exceeds 5 MB or the robot exceeds 1.5 MB.
- World Spec v2 adds elevation. Choose a representation, a heightfield or ramp primitives, and record it in an ADR.
- The World Spec ↔ SDF agreement check in CI compares every obstacle footprint and the ramp and platform geometry within a stated tolerance. The recorded SDF world is the reference. Fix the World Spec, never the SDF.

**M4.3 Arena model.**

- Terrain following is pure kinematics from fixed geometry.
- Flat scenes must not change. Run the complete existing golden-trace and determinism suites unchanged. Any byte difference on a flat scene is a stop condition.
- The terrain-session harness adds 100 sessions across all four engines.
- Teleop preempts autonomy. The command-source event follows the arbiter's priority order: STOP > TELEOP > MISSION or PLANNER.
- The grasp action reuses the existing proximity gate.
- Add a terrain section to the fidelity report. If Gazebo recordings of the ramp contain pitch, compare against them; otherwise state that no comparison is possible.

**M4.4 3D renderer.**

- Follow README section 5.3.
- Quality tiers are chosen from measured frame time, with hysteresis and a manual override in settings.
- Fallback to the top-down renderer happens automatically without WebGL 2, or when the low tier can't hold about 24 fps after a settling period. A notice explains it.
- Floor decals reuse the M1 grid textures.

**M4.5 Cameras and controls.**

- Follow README section 5.5.
- Generalise the storage module into one preferences module covering personal bests, key bindings, camera mode, quality tier and the sound toggle. Keep localStorage only, every access inside try, and the guard tests updated.
- Measure control latency with a scripted key press, timing it to the first frame where the robot pose changes, over 100 presses.

**M4.6 Every lens in 3D.**

- Follow README section 5.3.
- Watch is at most two layers.
- Precision tasks open in top-down.
- The timeline works in every camera, including the follow camera during replay.

**M4.7 Case Files in 3D.**

- Check whether the raw bags contain full 3D truth pose (z, roll, pitch). Re-convert wherever they do, and show the "planar recording" chip wherever they don't. Never infer height.
- The total stays within the ADR 0005 budget.
- Each manifest still cites its source bag checksum.
- Shared world assets are cached across Case Files, so the first frame stays at 2 s or less for 100 of 100.

**M4.8 Learn and Play in 3D.**

- Mission YAML gains per-step camera presets. The CI claims check still passes.
- Race the planner's ghost: the ghost is the Arena model following the planner's path with a reference tracker under the same limits, so it is deterministic. The scores are time, path length and contacts, each shown. Star thresholds come from the ghost's own result and are published in docs/v2/CHALLENGES.md. Its links reproduce in all three browsers, and coco verify supports it.

**M4.9 Launch preparation (drafts only):**

- Landing: the landing page becomes 3D attract mode on a light, low-detail scene, so cold start holds.
- Release notes: update docs/releases/v2.0.md, with every number traced to docs/RESULTS.md.
- Demo: update the demo-recording script to shoot 60–90 s in 3D (driving, the frontier spreading, the heatmap, top-down, the ghost race, a Case File) and record it locally.
- Usability test: write docs/v2/USABILITY_TEST_M4.md, the consolidated five-person test from the README criteria.

**M4.10 Measure and close.**

- Measure every agent-owned criterion in the README's M4 table.
- Write docs/v2/M4_RESULTS.md and append the numbers to docs/RESULTS.md.
- Open a pull request into main. Do not merge it.

## B.2 Git

- Work only on v2/m4-3d-arena. Push regularly.
- The pull request stays open for Gautham. The merge permission in this prompt covers PR #22 only.
- No releases, no tags, no manual Pages deploys.

## Never (from the prompt's §0, in force for M4)

- touch the COCO robot project or its worktrees
- use ~/ros2_ws(personal) for COCO Lab work
- delete evidence, tags or releases
- create or edit releases or tags
- use git clean, git reset --hard, force-push, or delete branches
- mark a Gautham-owned row as done

If Gazebo, Isaac or a robot-project batch run is active, don't run heavy jobs; report and wait.

## Final report (end of every session)

Fill in this report and update docs/STATUS.md to match:

```
Part A (first session only): review verdicts summary | Case File fix (method, 100/100 first-frame result) | re-measurement results | PR #22 merge SHA | public-site check
Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements taken (device or emulation, power profile, driver, conditions), against M3:
Acceptance criteria: each → met / not met / pending Gautham, with evidence:
Feasibility gate: emulated results | phone preview URL status | Gautham's results if recorded | phone default flag value
Screenshots awaiting Gautham's review:
Files removed (full list) and why:
Decisions recorded (ADRs) and plan-change log entries:
Deviations from the plan, and why:
Ideas parked in docs/IDEAS.md:
Stop condition hit? which one:
Questions for Gautham:
Next step according to README.md:
```
