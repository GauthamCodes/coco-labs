# COCO-Bench leaderboard (R2)

- `submissions/<suite>/<name>/` — submitted algorithm files with `meta.yaml` and their claimed
  `summary.json` ([how to submit](CONTRIBUTING.md)).
- `results/<suite>/<name>/result.json` — verified results (`coco.leaderboard.entry.v1`): written
  by the verifier (`tools/r2/leaderboard.py`) and, for submissions, committed only by the trusted
  `leaderboard-results` workflow or a maintainer from its artifact. The built-in reference
  entries were written by `tools/r2/leaderboard.py builtin` (R2.6).
- The page: Workbench → Leaderboard (built from `results/` by `tools/r2/leaderboard.py index`).

Security model and the held-out scheme: [ADR 0012](../docs/v2/adr/0012-running-strangers-code.md).
