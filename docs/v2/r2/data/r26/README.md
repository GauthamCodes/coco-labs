# R2.6 · The verified leaderboard — MODEL / TESTED

No server: GitHub pull requests, two workflows, and committed results. Rules for submitters:
[`leaderboard/CONTRIBUTING.md`](../../../../../leaderboard/CONTRIBUTING.md). Threat model:
[ADR 0012](../../../adr/0012-running-strangers-code.md) §3.

| Piece | File | What it does |
| --- | --- | --- |
| Submission | `leaderboard/submissions/<suite>/<name>/{algorithm.py, meta.yaml, summary.json}` | the file unchanged; author, display name, description, licence (MIT or Apache-2.0), optional paper; the claim (written by `tools/r2/leaderboard.py claim`) |
| Verifier | `tools/r2/leaderboard.py verify` in `tools/r2/verifier.Dockerfile` | public + held-out scenarios, every run twice (determinism), contract, claim; writes `result.json` (`coco.leaderboard.entry.v1`) and `report.md` |
| Untrusted job | `.github/workflows/leaderboard-verify.yml` | `pull_request` only, `contents: read`, no secrets; the BASE branch's verifier and coco_lab judge; refuses a PR touching anything but its submission files; `docker run --network none --read-only --cap-drop ALL --security-opt no-new-privileges --user 65534 --cpus 2 --memory 4g --pids-limit 256`, 140 min; uploads an artifact, writes nothing |
| Trusted writer | `.github/workflows/leaderboard-results.yml` + `tools/r2/leaderboard_writer.py` | `workflow_run` from the default branch; never runs PR code; validates every field of the artifact, re-checks the PR's head and files through the API, regenerates the comment from the numbers (mentions, links and markup made inert), labels `verified` / `not-verified`, commits `result.json` to a same-repository PR's branch |
| Re-verify | `.github/workflows/leaderboard-reverify.yml` | on a push to main touching coco_lab, worlds, the verifier or the leaderboard: every committed entry re-run in the same sandbox and compared (machine fields aside); a moved number fails the job, naming the entry |
| Page | Workbench → Leaderboard (`Leaderboard.tsx`; `leaderboard/index.json` from `tools/r2/leaderboard.py index`) | one table per suite and family, ranked by deterministic metrics only (success rate with Wilson 95% → median path ÷ grid-optimal → median clearance → self-reported expansions; controllers: success → time → clearance; localisers: success → final error); compute time per device, never ranked; each entry: code, reproduce in the Studio (consent first), the worst run's replay, its failures, public beside held-out, MODEL beside STACK where it ran in Gazebo |

**Held-out scenarios** (§1.5): drawn by each suite's own generator with seed `sha256(salt | suite | merge-base)`.
**Stated limitation:** the salt is committed (no secrets are possible in a fork-safe `pull_request` job), so anyone who
knows a PR's merge-base can compute its held-out set beforehand; it catches overfitting by habit or chance, not a
determined cheat. Review and the no-hard-coding rule cover the rest. A secret-free scheme cannot do better.

**Versions** in every entry: suite and suite version, model hash version (3), experiment version (1), API version (1),
verifier version (1); a change re-verifies everything (above).

## Reference entries (the built-ins, as the Workbench runs them)

Written by `tools/r2/leaderboard.py builtin` (held-out at merge-base `reference`): see `leaderboard/results/`. Planner
boards for arena-nav-50, depot-nav-100 and depot-narrow-30. Controller and localiser reference entries are not
generated in R2 (MPPI and MCL take hours per board on this laptop): those boards rank submissions only until they are.

## Gautham's submission: Lazy Theta* on depot-nav-100

`leaderboard/submissions/depot-nav-100/theta_star/` (written through the API with Claude Code for Gautham; MIT). Locally,
the verifier gives **VERIFIED**: public 100/100 (Wilson 95% 0.963–1.000), median path 0.978 × grid-optimal (any-angle
beats the 8-connected optimum), median min clearance 0.033 m (it takes corners close: the trade-off is visible), held-out
20/20; deterministic; 0 contract problems; claim digest matches. The end-to-end proof:

| Step | Result |
| --- | --- |
| The pull request | [#31](https://github.com/GauthamCodes/coco-labs/pull/31) `leaderboard/theta-star` → `v2/r2-byoa`: exactly the three submission files (checked through the API the writer uses), open, left for Gautham |
| Leaderboard verify (CI, sandboxed) | run [41905826181](https://github.com/GauthamCodes/coco-labs/actions/runs/41905826181): **pass**, 5 m 44 s on GitHub's AMD EPYC 7763; artifact [`theta_star_ci_result.json`](theta_star_ci_result.json): **VERIFIED**, public 100/100, held-out (merge-base `c5cfc50`) 20/20 |
| The same in three places | public results **byte-identical** (digest `ca9216a0d0d7435e…`) natively on the laptop, in the laptop's sandbox container ([`theta_star_sandbox_result.json`](theta_star_sandbox_result.json); no route out, no DNS, uid 65534: [`sandbox_probe.txt`](sandbox_probe.txt)) and in CI |
| Leaderboard results (trusted writer) | **not yet run**: a `workflow_run` workflow runs only from the default branch, so it acts once R2 is merged into main (then re-run the PR's checks; retarget #31 to main). Dry run of its validation and comment on the CI artifact, nothing posted: [`theta_star_writer_comment.md`](theta_star_writer_comment.md) |
