# G1 · Game Look — status

Prompt: [`G1_PROMPT.md`](G1_PROMPT.md). Art direction: [`ART_DIRECTION.md`](ART_DIRECTION.md).

## Now

- **Current checkpoint:** G1.0 Baseline — done.
- **Next step:** G1.1 (mockups rendered to PNG), then G1.2 game shell.

## Setup facts

- PR #25 is **open, not merged** → branched from `origin/v2/m5-focus` (`ddc3718`), then
  merged `origin/v2/m6-foundations` (`984b2cf`) once (merge commit `b9b42d4`, no conflicts).
- Branch: the session's designated branch **`claude/serene-davinci-v9y796`** (this cloud
  session may only push there). The prompt names `v2/g1-game-look`; Gautham can rename the
  branch or open the PR from it as he prefers. No force-push; nothing merged into main.
- Environment: cloud container (Xeon 2.1 GHz × 4, SwiftShader, no GPU, no ROS, no phone).

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| G1.0 Baseline | done | [`data/baseline/BASELINE.md`](data/baseline/BASELINE.md), [`screens/before/`](screens/before/) |

## Gautham: look at these

- Before screenshots: `docs/v2/g1/screens/before/*.png`.

## Laptop items pending

- ROS package suites (`scripts/run_all_package_tests.sh`): not runnable in the cloud.
- Anything needing a real GPU, `gz`, the Nothing Phone (1) over USB.

## Questions for Gautham

- None yet.
