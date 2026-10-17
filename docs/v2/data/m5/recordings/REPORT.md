# M5.8 Recordings library

Every static Case File (100) and converted run (65) has its own card: 165 entries,
including distinct representations of a shared source. Search spans IDs, title,
scenario/level, algorithm/controller, outcome, evidence and recorded facts. Four
conjunctive filters and a failures shortcut are available; unknown outcomes remain
“not classified”, void remains separate. The present corpus has 60 failure entries
across both representations, not 60 independent experiments.

Case metadata comes from the committed case index; recorded facts retain their
evidence. Converted outcomes come from the validated trace summary or original
Lab 5 outcome, without changing the MCAP bytes. A card opens the existing viewer;
Case File investigations preserve their original claims, members and references.
The long inline run list becomes a link back to the complete library. No experiment
builder was added. Phone filters use a native modal bottom sheet with keyboard
focus restoration and safe-area padding.

Evidence class: MODEL for tests and model traces; STACK for recorded Gazebo data.
No physical robot exists. No real-phone performance measurement is claimed.

## Verification

- `screens/recordings/frozen/checks.json` (relative to data/m5): all 165 source
  entries present in desktop, compact and both emulated Nothing Phone (1) profiles;
  four filters/search/failures/clear, no horizontal overflow, no recording fetch
  before opening, Case File and converted cards open the actual viewer. Zero errors.
- `vitest-frozen.txt`: 488 passed, including two library regressions.
- `tools.txt`: 205 passed; frozen rerun retained separately.
- `packages.txt`: eleven suites pass, including coco_lab 834; coco_lab_ros failed
  with missing generated-schema imports because the runner lacked the documented
  source PYTHONPATH. `packages-overlay-corrected.txt` reruns it with the canonical
  paths. No model/schema changes were needed.
- `typecheck.txt`, `build-outcomes.txt`, `dist.txt`: pass.

Earlier failures are retained: an incorrect manifest accessor in build-first,
source status follow_failed initially unclassified (fixed and regression-tested),
and vitest starting while catalog regeneration temporarily removed generated
stdlib data. The corrected web run uses the completed, frozen asset tree. Subsequent
builders and tests must be sequenced.

Screenshots: ../../screens/recordings/README.md. All look review remains Gautham's.
Nothing was moved/deleted; every evidence URL remains valid. Next: M5.9 static cache
and optional aggregate counter, then launch drafts and final measurement/PR.
