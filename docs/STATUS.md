# COCO Lab — status

Where the work stands. [`README.md`](../README.md) (the master plan) is the
authority; this file records position, open questions and plan changes
only. Read order for agents (README §9): `README.md`, this file,
`CLAUDE.md`, `PROJECT_STATE.md`.

## Position

| | |
|---|---|
| Repository | `GauthamCodes/coco-labs` (remote `labs` in the working checkout; see [`v2/data/m0/START_STATE.md`](v2/data/m0/START_STATE.md)) |
| v1 | **Frozen** at tag `coco-lab-v1-final` = `3571169` (coco-labs `main` = `2b6f8ad` fast-forwarded to `lab5`) |
| Branch | `v2/m0-transition` (from `3571169`) |
| Current SHA | the head of `v2/m0-transition`; each checkpoint commit is listed below |
| Milestone | **M0 · Transition** |
| Checkpoint | M0.4 Install the plan — done |
| Merge to `main` | not merged; owner's approval required (README §3, integrity rule 5) |

## Checkpoint log

- **M0.1 Verify (2026-10-08).** `main` = `2b6f8ad`, `lab5` = `3571169`;
  `lab5` strictly ahead by 2 documentation-only commits. Tests at
  `3571169`: packages 3,081 / 0 / 0, `lab_web` vitest 308 / 0 / 0, build
  tools 117 / 0 / 0. Evidence: [`docs/v2/data/m0/START_STATE.md`](v2/data/m0/START_STATE.md).
- **M0.2 Freeze v1 (2026-10-08).** Annotated tag `coco-lab-v1-final` on
  `3571169`. All six releases exist and are published; five carry their
  demo video, `live-v1.0` has none by design. The three recordings
  `docs/RESULTS.md` cites by checksum resolve in `~/coco_lab_runs/`
  (3/3). Evidence: [`docs/v2/data/m0/FREEZE.md`](v2/data/m0/FREEZE.md).
- **M0.3 Baseline (2026-10-08).** Laptop, Playwright, local production
  build, 5 fresh browsers each: Pyodide cold first edit median 12,857 ms
  (6,567–42,882), warm edit median 1,445 ms (1,265–1,686), every playing
  view at 60 fps rAF with 0 long tasks; `dist/` 23,010,799 B, Pyodide
  6,358,909 B. Phone: method written, **not yet measured**. Evidence:
  [`docs/v2/BASELINE.md`](v2/BASELINE.md),
  [`docs/v2/PHONE_BASELINE.md`](v2/PHONE_BASELINE.md), `docs/RESULTS.md`
  "COCO Lab v2 · M0 baseline".
- **M0.4 Install the plan (2026-10-08).** `README.md` = the master plan,
  byte-identical to the owner's file (sha256 `4b003e50…a2ab6`). Archived
  to `docs/archive/v1/`: `README_v1.md`, `ROADMAP.md`, `LAB_PHASES.md`,
  `CLAUDE_v1_rules.md`. New: `docs/ROADMAP.md` (pointer + v1 history),
  this file, `docs/IDEAS.md`; `PROJECT_STATE.md` and `CLAUDE.md` updated.

## Capabilities (README §2), with evidence class

Classes as README §3 defines them: MODEL, STACK, REMOTE, HARDWARE (none
exist), UNRESOLVED, CONCEPT.

| Capability / result | Class | Caveat | Evidence |
|---|---|---|---|
| Smac and `coco_lab` find the same optimal cost on 36/36 pairs | STACK + MODEL | — | `docs/RESULTS.md` Phase 1C; `docs/data/lab1c/conformance/` |
| Sketch LiDAR against Gazebo: 86.7% of beams within 5 cm | MODEL vs STACK | Turns diverge (no wheel slip) | `docs/labs/LAB2_LOCALISE.md`; `docs/data/lab2/fidelity/` |
| Kidnapping, model: 18/20 with injection vs 0/20 without | MODEL | — | `docs/labs/LAB2_LOCALISE.md` |
| Kidnapping, Stack: 2/10 vs 0/10 (Fisher p = 0.237) | UNRESOLVED | — | `docs/data/lab2/kidnap_ab.json` |
| Loop closure damaged maps on both real SLAM backends | STACK | Cause unattributed | `docs/labs/LAB3_MAP.md` |
| Search: 14/16 complete, 39/39 looks correct | STACK | All 16 replay byte for byte through `coco_lab` | `docs/labs/LAB4_SEARCH.md` |
| Lab 5: 54 runs, 0 void | STACK | DWB 0/5 at the hairpin; nobody swerved head-on | `docs/labs/LAB5_MOVE.md` |
| Run 15 mechanism reproduced 9/9 | STACK | Exact "0 of 819" not reproduced | `docs/labs/LAB5_MOVE.md` |
| D\* Lite less work than A\* in 191/200 teaching worlds | MODEL | 2.9× *more* work on one real costmap | `docs/RESULTS.md` Phase 6 |
| Latched STOP; drive command p50 4.6 ms; STOP 6.2 ms | STACK | Local network | `docs/live/LIVE.md` |
| Phone on mobile data drove the robot; RTT about 282–293 ms; disconnect stop about 0.54 s | REMOTE | Robot simulated | `docs/live/PART_C_REPORT.md` |
| v1 site baseline (cold start, warm edit, frame rate, sizes) — laptop | MODEL | Phone not yet measured | `docs/v2/BASELINE.md` |

**Unresolved, kept labelled** (README §2): DWB's hairpin stall; why no
controller swerved; D\* Lite's extra work on the real costmap; loop-closure
damage; exact Run 15; recovery from confident AMCL divergence; the
collision-monitor residual; untested remote behaviours (phone STOP, second
spectator, mid-mission preemption, remote mission completion, idle and
session caps, the cause of the disconnect, the stale Nav2 "executing"
label).

## Open questions (README §8) and the defaults in force

| ID | Decision | Default until Gautham decides |
|---|---|---|
| G1 | Primary audience | Learners first |
| G2 | Priority against the robot project and job hunt | Not an agent decision; agents respect announced robot batch windows |
| G3 | Canonical robot stack | The robot repo is canonical; `coco-labs` robot packages are frozen, not deleted |
| G4 | Monthly cloud budget | Zero; no cloud resources are created before M4 and an explicit budget |
| G5 | Will a physical robot exist within a year? | Assume no; no "real robot" wording anywhere |
| G6 | License and outside contributions | Unchanged from the current repo |

## Plan-change log

Changes to `README.md` happen only at a milestone boundary, by Gautham,
as a dated entry here (README §0).

| Date | Change | By |
|---|---|---|
| — | (none yet) | — |
