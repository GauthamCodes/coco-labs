# Case Files (M3.3)

Every recorded full-stack run, inspectable in the Arena viewer beside the
Arena model. A Case File is evidence class **STACK**: the full ROS 2 stack in
Gazebo, recorded. No physical robot exists.

- **List:** `?view=casefiles`
- **Group:** `?view=casefiles&case=<group>`
- **One recording beside the model:** `?view=casefiles&case=<group>&file=<id>`
- **The recording alone:** `?view=arena&casefile=<id>`

## Where everything is

| What | Where |
|---|---|
| The text: groups, explanations, unresolved questions, links | `lab_web/casefiles/cases.yaml` |
| The files: 100 run files, zstd, indexed | `lab_web/casefiles/<id>.mcap` |
| The index: bytes, sha256, run id, source citation | `lab_web/casefiles/index.json` |
| Storage decision | [ADR 0005](adr/0005-case-file-storage.md) |
| Conversion | `coco_lab_ros/coco_lab_ros/adapter.py` ([ADAPTER.md](ADAPTER.md)) |
| Build, local (needs ROS and `~/coco_lab_runs`) | `lab_web/tools/build_casefiles.py`, then `lab_web/tools/pack_casefiles.mjs` |
| The CI check and the site's text | `lab_web/tools/casefiles.py`, run by `build_catalog.py`, tested by `test_casefiles.py` |
| Viewer | `lab_web/src/arena/replay_case.ts` |
| Page | `lab_web/src/casefiles/CaseFilesApp.tsx` |
| Browser checks | `lab_web/tools/perf/casefile_check.mjs`, `casefile_compare_check.mjs` |

## The inventory

| Group | Case Files | Source bags | Cited checksum checked against | Window |
|---|---|---|---|---|
| `lab1-runs` | 3 (A\*, Dijkstra, greedy) | `lab1c/run_*/bag` | `docs/data/lab1c/runs.json`, `coco_lab_ros.export.dir_sha256`: 3 / 3 | the whole bag |
| `astar-myth` | the three above, plus the committed conformance data | — | — | — |
| `lab2-kidnap` | 23: 20 valid + 3 void, labelled VOID | `lab2/kidnap_*/bag` | none committed; the manifest cites every file | the whole bag |
| `lab2-rl-tour` | 1 | `lab2/fidelity_1/bag` + `lab2/rlpd_fidelity_1/rl_bag`, merged on simulation time | none committed | the tour's own window in `docs/data/lab2/ekf_drift.json` (191.72–632.16 s) |
| `lab3-slam` | 2 tours, plus the backends' scores from `docs/data/lab3/results.json` | `lab3/drives/{s1,1}_tour/bag` | none committed for the derived tour bags | the whole bag |
| `lab4-search` | 17: 16 + the void B3 attempt | `lab4/matrix/<run>/bag` | `docs/data/lab4/replay/p05_matrix/manifest.json`, `p05_evidence._sha_dir`: 16 / 16 | log time from the bag's start to its first terminal state + 2 s, the rule of `docs/data/p05_bagtimes.py` (a recorder could outlive its run) |
| `lab5-move` | 54 | `lab5/matrix/<run>/bag` | `docs/data/lab5/drive/*/manifest.json`, `bag_0.mcap`: 54 / 54 | the run's recorded window (FollowPath request to end) ± 5 s. A mislocalised run aborts within 8 ms, so its window alone is empty; its Case File starts 3 s before the recorded `/initialpose` that told AMCL the wrong pose (M3.4), so it holds that moment as well as the abort. |
| `run15` | the nine Lab 5 `mislocalised_*` runs | — | — | — |

**Totals:** 100 Case Files, **41,486,529 B** (41,438,100 B at M3.3) (ADR 0005 budget: 20 MB each,
150 MB in all). The largest is `lab2_rl_fidelity_1_tour` at 2,780,072 B.

**Not a recording, and said so:**
- **Run 15** itself was never recorded as a bag; its Case File is the
  nine-run reproduction.
- **The A\* myth** is the conformance sweep's committed JSON beside the
  three Lab 1 runs.
- **The SLAM backends' maps** were scored offline and kept as `record.json`,
  not bags. Their scores are shown as Lab 3 recorded them.

All three are the owner's rulings of 2026-10-10 (STATUS plan-change log).

## What each Case File shows

- **The recording, played:**
  - the robot where the stack believed it was (AMCL), with ground truth
    beside it
  - the recorded scans
  - the global plans
  - the controller's chosen trajectory and commands
  - the mission's transitions
  - the stack's own estimators
  - the annotations
  - every tick a seek away (the whole recording is loaded, then played)
- **Generated facts:** a few sentences from the committed data that scored
  that run (outcome, order searched, tracking error, recovery), each
  citing its file.
- **The group's explanation:** every sentence with its learner label and
  evidence, which must resolve or the build fails.
- **The unresolved questions,** labelled UNRESOLVED.
- **Links to `docs/RESULTS.md`.**
- **The model beside it, MODEL:** the Arena on the same scenario, with the
  "model gap" chips from `FIDELITY_v1.md`:
  - Lab 5: the matching teaching controller (DWB → DWA, MPPI → MPPI, RPP →
    RPP) on the same scenario
  - Lab 4: the same colour with the target in the same bay
  - Lab 2: MCL with injection, kidnapped to the same target
  - Lab 1: the same goal

## Rebuilding

```
py.sh lab_web/tools/build_casefiles.py OUT [--group G ...] [--only ID ...]   # needs ROS and the bags
node tools/pack_casefiles.mjs OUT                                              # from lab_web
python3 lab_web/tools/casefiles.py                                             # the check CI runs
```

`build_casefiles.py` stops on a missing recording or a checksum that is not
the one a committed manifest cites (M3 prompt B.5). It never patches one.

## Moments (M3.4)

A Learn beat opens a Case File paused at a **moment**, never at a typed tick.
`lab_web/src/arena/moments.ts` finds two moments in the recording as the
viewer plays it:

- **divergence:** the first tick where the stack's belief is more than
  1.0 m from ground truth. The belief is its map-frame estimate (AMCL), or,
  when the recording has none, the start of each recorded global plan.
- **refusal:** the first recorded give-up: `/lab/status`
  `follow_failed`, or a mission ABORT.

`lab_web/tools/casefile_moments.mjs` writes them to
`docs/v2/data/m3/m34/moments.json`. Two checks keep that file honest:

- `lab_web/test/casefile_moments.test.ts` re-derives every entry from the
  committed Case Files;
- `lab_web/tools/missions.py` refuses a beat whose `tick` is not its
  `moment`'s.

**Lab 4 recorded no belief** (no `/amcl_pose`, no plans), so a Lab 4 Case
File has a refusal moment and no divergence moment. It says so rather than
inventing one.
