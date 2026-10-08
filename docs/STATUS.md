# COCO Lab — status

Where the work stands. [`README.md`](../README.md) (the master plan) is the
authority; this file records position, open questions and plan changes
only. Read order for agents (README §9): `README.md`, this file,
`CLAUDE.md`, `PROJECT_STATE.md`.

## Position

| | |
|---|---|
| Repository | `GauthamCodes/coco-labs`; canonical checkout `~/coco_labs_ws/src/coco-labs` ([`v2/CHECKOUTS.md`](v2/CHECKOUTS.md)) |
| v1 | **Frozen** at tag `coco-lab-v1-final` = `3571169` |
| M0 | **Closed 2026-10-08**: PR #19 merged into `main` as `9f58b83` (merge commit, owner's one-off permission); independent review [`v2/data/m0/REVIEW_2026-10-08.md`](v2/data/m0/REVIEW_2026-10-08.md), its findings resolved below; public site after the Pages deploy: 0 console errors, 0 page errors in all six views, Live shows the offline state ([`v2/data/m0/exit/public_after_merge.json`](v2/data/m0/exit/public_after_merge.json)) |
| Branch | `v2/m1-arena-core` (from `main` = `9f58b83`), worked in the worktree `.claude/worktrees/v2-m1-arena-core`, overlay `~/coco_lab_m1_ws` |
| Milestone | **M1 · Glass-box Arena core** ([`v2/M1_PROMPT.md`](v2/M1_PROMPT.md)) |
| Checkpoint | B.1 preflight done; **next: M1.1 `coco_schemas`, starting with the event-transport measurement (ADR 0001)** |
| Merge to `main` | M1 opens a PR when every agent-measurable criterion passes; it is **not** merged by the agent |
| Pending Gautham | Phone baseline ([`v2/PHONE_BASELINE.md`](v2/PHONE_BASELINE.md)); M1 phone performance, phone cold start and usability (README §7, M1) |

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
  byte-identical to the owner's file (sha256 `4b003e50…a2ab6`;
  replaced on 2026-10-08 by the gripper-corrected plan, sha256
  `23214733…175935c`, see the plan-change log). Archived
  to `docs/archive/v1/`: `README_v1.md`, `ROADMAP.md`, `LAB_PHASES.md`,
  `CLAUDE_v1_rules.md`. New: `docs/ROADMAP.md` (pointer + v1 history),
  this file, `docs/IDEAS.md`; `PROJECT_STATE.md` and `CLAUDE.md` updated.
- **M0.5 Remove (2026-10-08).** No code or config exists for Isaac inside
  COCO Lab, the VLM layer or browser policy training; **0 files deleted**.
  The robot project's design sections for the VLM layer and policy
  training are marked out of scope in place; the robot-stack Isaac adapter
  (`coco_sim`) and the Isaac evidence are kept (frozen package; evidence).
  Old themes rewritten in `docs/ROADMAP.md`. Evidence:
  [`docs/v2/data/m0/REMOVALS.md`](v2/data/m0/REMOVALS.md).
- **M0.6 Honesty fixes (2026-10-08, copy only).** Site: the Live tab, its
  header and its mode badge read "Live Stack (simulated)" (local /
  scheduled demo), with a line saying it is a scheduled demo of the
  simulated stack and that no physical robot exists; Lab 4's "The real
  robot (Replay)" tab reads "The full ROS 2 stack (simulated) — Replay";
  the Lab 4 demo recorder's caption likewise. Docs: `docs/live/LIVE.md`
  title and `PROJECT_STATE.md` reworded with the old text recorded;
  correction notes at the top of `docs/labs/LAB1_PLAN.md`,
  `LAB4_SEARCH.md`, `LAB5_MOVE.md` and `docs/releases/lab4-v1.0.md`
  (bodies untouched). No "two-finger" wording exists outside the archive
  and frozen code comments. `lab_web/test/live.test.ts` updated for the
  new label; vitest 308 / 0 / 0.
- **M0.7 Freeze the robot-stack packages (2026-10-08).** `FROZEN.md` in
  each of the nine: `coco_config`, `coco_mission`, `coco_moveit_config`,
  `coco_perception`, `coco_rl`, `coco_sim`, `coco_web`, `custom_teleop`,
  `gazebo_models` — kept, no new features, decision G3 pending; nothing
  deleted. `coco_lab`, `coco_lab_ros` and `lab_web` are COCO Lab's own and
  are not frozen. `coco_web`'s `platform_server` is unfrozen by plan at
  M4–M5 (README §4).
- **M0.8 Deprecation notes (2026-10-08).** [`docs/v2/DEPRECATIONS.md`](v2/DEPRECATIONS.md):
  Canvas 2D rendering → Three.js (M1); per-lab formats → one MCAP
  envelope (M1–M2); public Tailscale Live → cloud sessions (M5, gated);
  six views → one Arena app (end of M2); races → Sandbox compare; replays
  and exhibits → Case Files (M3). Each stays working until its
  replacement ships; nothing deleted. Banner in `lab_web/README.md`.
- **M0 exit checks (2026-10-08).** On `9480faa`: packages 3,081 / 0 / 0,
  vitest 308 / 0 / 0, tools 117 / 0 / 0 (equal to M0.1); production build
  clean; plan, localise, map, search, move load with 0 console errors;
  live logs only the refused-socket network errors it logged in v1 (no
  Stack running); honesty copy visible at 1400 and 390 px, no "real
  robot" on screen. Evidence: [`docs/v2/data/m0/EXIT.md`](v2/data/m0/EXIT.md).
  **M0 is not closed**: it closes after Gautham approves the merge and a
  fresh review session verifies the report (README §9.9).

- **Independent review (2026-10-08, README §9.9): done.** A fresh
  session that did not do the work checked PR #19 at `c70f447`; report
  saved verbatim as [`v2/data/m0/REVIEW_2026-10-08.md`](v2/data/m0/REVIEW_2026-10-08.md).
  Verdicts: tag, releases, README, archive, nothing deleted, RESULTS
  append-only, required files, baseline numbers (recomputed exactly),
  tests (3,081 / 308 / 117), CI, recordings (3/3), lab5 fast-forward and
  checkpoint discipline **VERIFIED**; views load **VERIFIED, Live
  excepted**; honesty copy **NOT VERIFIED (partly fixed)**.
  Recommendation: **MERGE AFTER FIXES**. What the "exit checks passed"
  line above used to claim was not true: Live still logged console
  errors, so README §7's "every current public view still loads with no
  console errors" was not met.
- **M0 review fixes (2026-10-08, `[M0-fix]` commits).** Each finding and
  how it was resolved:

  | Review finding | Resolution | Evidence |
  |---|---|---|
  | Exit criterion not met: Live logged `ws://localhost:8080` connection-refused errors | **A.2 quiet Live probe.** Measured first: in Chromium a fetch to a dead endpoint is itself a console error (refused port, unresolvable host, opaque `no-cors` alike), so the page now contacts only what was asked for: a `?live=` link, Connect or Watch (`/healthz` first, backoff 2 s doubling to 30 s, socket only after an answer), and the scheduled demo's endpoint only while a demo is on. All six views: **0 console errors, 0 page errors**; Live opens 0 sockets on load; recovery against a stand-in server connects with 1 socket | `v2/data/m0/exit/console_after_fix.json`, `probe_noise.json` |
  | STATUS.md said "exit checks passed" (overstated) | Replaced by the Checkpoint row above and this entry | this file |
  | "All four CI jobs passed" | Three passed; the Pages deploy is **skipped** on PR runs (it runs on `main` only) | PR #19 checks |
  | Correction notes claimed for the lab4 release notes, but only the repo copy was corrected; lab1-v1.0's "a real robot used" not mentioned; live-v1.0 title says "the real robot" | **A.4**: the three published texts edited, wording only, under a one-off owner permission; tags, targets, flags and assets re-read identical | `v2/data/m0/releases_before/`, `releases_after/`, `releases_diff.txt` |
  | `docs/RESULTS.md:8568` "The real robot chose…" has no note; `docs/history/ROADMAP_LAB_2026-09-28.md` has no header | **A.3**: appended dated correction note in RESULTS.md (line untouched); correction header on the roadmap (body untouched). Repo search: 68 hits, 0 needing a fix; rendered site shows no "real robot" | `v2/data/m0/exit/copycheck_after_fix.json` |
  | Gripper described two ways (plan: magnet only; robot-stack record: fingers and a magnet) | **A.1**: owner's corrected plan installed (plan-change log); four M0-written lines now say "two fingers and a magnet; the magnet holds the object" | README sha256 `23214733…175935c` |
  | "Two exit criteria aren't fully met" counted the phone baseline | The phone baseline is **not** an M0 exit criterion: M0.3 asks for the method and the script, which exist. The measurement itself is **pending Gautham** ([`v2/PHONE_BASELINE.md`](v2/PHONE_BASELINE.md)) | — |
  | "Worktree clean" not checkable by the reviewer | The fix session ran `git status` before every commit in the same worktree; the remote branch head is the pushed end SHA | `git log` |
  | Merging lands lab5's two docs-only commits on `main` | Expected under M0.1; no action | START_STATE.md |
  | `~/coco_labs_ws/src/coco-labs` is a stale clone while `CLAUDE.md` and the scripts default to it | **Resolved by M1 step B.1**: that checkout is fast-forwarded to the merged `main` and becomes canonical (plan-change log, 2026-10-08) | `v2/CHECKOUTS.md` (M1) |

- **M0-close tests (2026-10-08).** On `33c11dc` (overlay `~/coco_v2_ws`,
  ROS domain 78): packages **3,081 / 0 / 0** (equal to M0.1; per package in
  [`v2/data/m0/exit/packages_after_fix.txt`](v2/data/m0/exit/packages_after_fix.txt)),
  `lab_web` typecheck clean and vitest **320 / 0 / 0** (308 unchanged + 12
  new in `test/live_gate.test.ts`), build tools **117 / 0 / 0**. The package
  run shared the machine with an orphaned e-Yantra `gz sim server` (owner's,
  about one core, not touched); nothing failed. PR #19 CI on `33c11dc`:
  `build-and-test` pass (collected 2,356 tests across 9 suites, 0
  failed), `coco_lab in a plain venv` pass, `lab_web` pass, Pages deploy
  skipped (PR run).

- **M0 closed (2026-10-08).** PR #19 merged at `9f58b83` (`gh pr merge
  --merge`, branch kept) after every M0-close condition held on the final
  head `21d94a8`: packages 3,081 / 0 / 0, vitest 320 / 0 / 0, tools
  117 / 0 / 0; CI `build-and-test`, `coco_lab in a plain venv`, `lab_web`
  pass (Pages deploy skipped on the PR run); 0 console errors in all six
  views; `README.md` byte-identical to the owner's file. The `main` run
  then deployed Pages (success), and the public site was checked:
  [`v2/data/m0/exit/public_after_merge.json`](v2/data/m0/exit/public_after_merge.json).

## M1 checkpoint log

- **B.1 Preflight (2026-10-08).** Canonical checkout
  `~/coco_labs_ws/src/coco-labs`: clean, `origin` = `GauthamCodes/coco-labs`,
  no local-only commits; `main` fast-forwarded `6249e7d` → `9f58b83`
  (contains the PR #19 merge; `coco-lab-v1-final` → `3571169`).
  [`v2/CHECKOUTS.md`](v2/CHECKOUTS.md) written. Overlay `~/coco_labs_ws`
  rebuilt from that checkout; M1 builds its worktree into
  `~/coco_lab_m1_ws`. **Incident:** the session first built into
  `~/coco_m1_ws`, which is the robot project's overlay (`~/coco-isaac-21`);
  with Gautham's approval it was restored the same day by re-running its
  recorded build, and no COCO Lab path remains in it (CHECKOUTS.md).
  **Toolchain:** Node 24.21.0 (`lab_web/.nvmrc`; binary from
  `~/coco_v2_ws/node`), npm lockfile (`npm ci`); Python 3.12.3 test venv
  `~/coco_labs_ws/test_venv` (system site packages: pytest 7.4.4,
  hypothesis 6.98.15, numpy 1.26.4, protobuf 4.21.12; `protoc` 3.21.12);
  Pyodide 314.0.7 (`site.config.ts`; Python 3.14.2 inside, whose lock lists
  protobuf 7.34.1, zstandard 0.25.0, numpy 2.4.6). **M1 baseline** on
  `9f58b83`: packages **3,081 / 0 / 0**, vitest **320 / 0 / 0**, tools
  **117 / 0 / 0**. Next: M1.1.

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

| Date | Change | Reason | By |
|---|---|---|---|
| 2026-10-08 | **Live console errors are fixed, not waived.** The quiet Live probe moves from `docs/IDEAS.md` into M0 (fix A.2), so the M0 exit criterion "no console errors in any view" is met before merging. | Independent review 2026-10-08: the criterion was not met and STATUS.md overstated it. | Gautham (M0-close / M1 prompt §0.1) |
| 2026-10-08 | **Gripper wording corrected.** README §2 correction 2 and M0.6 now read "two fingers and a magnet; the magnet does the holding". README sha256 `4b003e50…a2ab6` → `23214733…175935c`. | The robot-stack record (RESULTS "The magnet fires before the fingers close") shows fingers *and* a magnet; "magnet, not two-finger" was wrong. Raised by the review. | Gautham (prompt §0.2) |
| 2026-10-08 | **One-off permission to edit three published release texts** (`live-v1.0`, `lab1-v1.0`, `lab4-v1.0`): wording only, never assets, tags or targets. | Their "real robot" wording describes the Gazebo stack; agents otherwise never edit releases. | Gautham (prompt §0.3) |
| 2026-10-08 | **One-off permission to merge PR #19** once the fixes are pushed, CI is green and the M0-close conditions hold. Merging deploys Pages. | Closes M0 (README §9.9 review done). | Gautham (prompt §0.4) |
| 2026-10-08 | **Canonical checkout from M1 on is `~/coco_labs_ws/src/coco-labs`**, fast-forwarded to the merged `main`. `~/ros2_ws(personal)` and its worktrees are left untouched and no longer used for COCO Lab. | `CLAUDE.md` and the scripts already default to that path; the review flagged the stale clone as a risk of building the wrong tree. | Gautham (prompt §0.5) |
