# R4 Part A · the held-out secret: set, committed, proven (2026-11-10)

## Set without exposure

One Python process (`python3 -I`) made `secrets.token_hex(32)`, gave it on stdin to
`gh secret set COCO_HELDOUT_SECRET -R GauthamCodes/coco-labs` (stdout/stderr discarded) and printed only
`sha256` of the 64-hex-digit string, ADR 0014's `sha256(SECRET)`. The value was never printed, logged, written to a
file or shown to the agent. `gh secret list`: `COCO_HELDOUT_SECRET 2026-11-10T13:19:42Z`.
Commitment: `e3195c2f291c234d15627273568841082b63727b11d602d4b85afa110c52ebd7`
([HELDOUT_SECRET_COMMITMENTS](../../../r3/HELDOUT_SECRET_COMMITMENTS.md)).

## Proof 1 · a verifier run that uses the secret (CI, TESTED)

PR [#38](https://github.com/GauthamCodes/coco-labs/pull/38) (Theta\*'s v1 claim): "Leaderboard verify"
run 42823746868 passed; the trusted "Leaderboard results" run
[42824431748](https://github.com/GauthamCodes/coco-labs/actions/runs/42824431748) ran job `heldout` (step "Generate the
held-out scenarios (the only step that sees the secret)": success; NOT the `heldout/NONE` branch) and `write`.
The PR comment it wrote:

> held-out (secret, ADR 0014; fresh for this head): 20/20 succeeded (Wilson 95% 0.839-1.0); min_clearance_m median
> 0.0328; path_ratio median 0.974

alongside public 100/100 (path_ratio 0.978) and R2's public-salt held-out 20/20. Label `verified`.

## Proof 2 · the attack tests (laptop, docker, the workflow's exact container flags, TESTED)

`tools/r3/hostile_check.py` (each run makes its own fresh throwaway secret; only its sha256 is recorded):

| run | file | verdict | the T5 residual (falsified `path_ratio` median) | coordinates in any other published field |
| --- | --- | --- | --- | --- |
| 1 | [hostile_run1_old_check.json](hostile_run1_old_check.json) | **FAIL** under R3's check | 7.35 = a start x (`7.35`) | — (not computed by the old check) |
| 2 | [hostile_run2.json](hostile_run2.json) | PASS | 8.65 = a coordinate | none |
| 3 | [hostile_run3.json](hostile_run3.json) | PASS | 4.25 = a coordinate | none |

Every other attack held in all three runs: the secret was not in the environment, in any of ~6,678 readable files
or in any sandbox output; no connection, no DNS; no docker socket; uid 65534; the two hostile `algorithm.py`
files (read the scenario file, read the environment) refused by the guard; only the allowed aggregate keys published.

**What run 1 found (negative result, kept).** R3's check failed whenever any 2-decimal coordinate string appears in
the published text. The probe *deliberately* writes a scenario's start x into `path_ratio`: that is ADR 0014's
accepted residual T5 (one number per metric per push, rounded to 3 significant digits, describing a set never used
again). When the coordinate is < 10, 3 significant digits **are** 2 decimals, so it matches exactly (`7.35`); R3's
published residual was 13.6 vs the coordinate `13.6x`, and passed **only by formatting**. Nothing new leaks; the
check was measuring the accepted residual by accident. Smallest honest fix (`tools/r3/hostile_check.py`): the
verdict is over every published field **except** the falsified one; the residual's match is reported
(`residual_equals_a_coordinate`), not hidden. Runs 2–3 show the residual equal to a coordinate both times, as T5 says.
