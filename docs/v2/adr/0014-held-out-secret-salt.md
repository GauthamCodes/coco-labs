# ADR 0014 · Held-out scenarios from a secret salt, generated outside the sandbox

- **Status:** **accepted** 2026-11-07 (R3.3), after the threat analysis below and the hostile tests in the
  real container passed ([`docs/v2/r3/data/heldout/`](../r3/data/heldout/README.md)); residual T5 observed as stated.
- **Supersedes in part:** ADR 0012's held-out paragraph (R2.6: the salt is committed, so anyone who knows a
  PR's merge-base can compute its held-out set). R2's scheme stays as the *public-salt* held-out check for
  local runs and for any repository without the secret.
- **Owner instruction (R3 prompt B1):** the trusted workflow generates the held-out scenarios with a secret
  salt outside the sandbox and passes only the scenario file into the no-network, unprivileged container;
  the secret never enters the container's environment or filesystem; security-review the design first and test
  it with hostile submissions that try to exfiltrate or memorise the held-out scenarios; if it cannot be done
  safely, keep R2's scheme and its stated limitation.

## Decision

1. **Seed.** `seed = int(HMAC-SHA256(key = SECRET, msg = "coco-bench.held-out.v1|" + suite + "|" + head_sha)[:13], 16)`
   (53 bits, as every experiment seed). `head_sha` is the pull request's head commit, so **every push gets a
   fresh, unpredictable held-out set**: a set, once seen, is never used again.
2. **Where the secret lives.** A repository secret `COCO_HELDOUT_SECRET` (32 random bytes, hex), readable only by
   the trusted workflow `leaderboard-heldout.yml` (`workflow_run` after "Leaderboard verify" succeeds; runs the
   **default branch's** file; never `pull_request_target`). It is referenced in exactly one step's `env:`, the
   step that runs `tools/r3/heldout.py generate` (default-branch code, never PR code) and writes
   `heldout/<suite>.json` (scenarios only: ids, starts, goals, seeds; mode 0444). The step ends before any
   untrusted code starts; later steps' environments do not contain it.
3. **Running the submission.** The same container as R2.6 (`--network none --read-only --cap-drop ALL
   --security-opt no-new-privileges --user 65534:65534`, CPU/memory/pid limits, a timeout) with exactly three
   mounts: the submission (read-only), the scenario file (read-only), an empty output directory. No environment
   variables are passed (`docker run` passes none unless `-e`); the workspace, `$RUNNER_TEMP`, the runner's home and
   the docker socket are not mounted. The container's stdout/stderr go to a file the trusted step **never prints
   or uploads**.
4. **What leaves.** The trusted step reads only `out/heldout.json`, validates it as data (the schema's numeric
   fields, nothing else), and publishes per suite **only aggregates**: `n`, successes, the Wilson 95 % interval,
   and the medians of `path_ratio` and `min_clearance_m` **rounded to 3 significant digits**. Never per-scenario
   ids, coordinates, paths, chains or logs. The comment states the held-out digest (sha256 of the scenario file)
   so the set can be audited when the secret is revealed (6).
5. **The PR workflow is unchanged** for the public scenarios (R2.6, sandboxed, artifact, trusted writer) and keeps
   R2's public-salt held-out run as a smoke check; the `verified` label now needs both: public verification and
   the secret held-out run (the writer reads both artifacts).
6. **Rotation and audit (commit–reveal).** `docs/v2/r3/HELDOUT_SECRET_COMMITMENTS.md` lists `sha256(SECRET)` for each
   secret in use. On rotation (yearly, or at once on any suspicion) the old secret is **published** there, so every
   past held-out set and its digest can be regenerated and checked by anyone; results stay auditable.

## Threat analysis

| # | Threat (attacker = a submission author) | Mitigation | Residual |
| --- | --- | --- | --- |
| T1 | Compute the held-out set ahead of time (R2's weakness) | HMAC with a secret; per-head sets | Needs the secret (T2) |
| T2 | Read the secret from inside the sandbox (env, files, `/proc`) | never in the container's env or mounts; generated in an earlier step; not in later steps' env | A container **escape** to the runner host could read the runner's memory. Bar: a kernel/runtime exploit from an unprivileged, capability-less, no-new-privileges, read-only container. On suspicion: rotate (6). |
| T3 | Exfiltrate the held-out scenarios over the network | `--network none` (R2.6: ENETUNREACH, no DNS) | none known |
| T4 | Exfiltrate through outputs (a file in `/out`, stdout/stderr into the public job log) | only `out/heldout.json` read, as typed numbers; container output never printed or uploaded | the published aggregates (4) are ≤ ~5 numbers of 3 significant digits per suite per push |
| T5 | Exfiltrate through the published numbers (falsified metrics after a guard escape) | rounding (≈ 30 bits per suite per push) and **per-head sets**: what leaks describes a set never used again | none useful: memorising a used set gains nothing |
| T6 | Memorise: hard-code scenario answers | sets are fresh per push and unknown before; CONTRIBUTING forbids hard-coding; review | none |
| T7 | Learn the generator's distribution from the public suite and overfit to it | inherent to any held-out set from the same generator; this is what "held-out" measures | stated limitation |
| T8 | Run PR code with the trusted workflow's token | the trusted workflow never checks out or imports PR code outside the container; `permissions: contents: read, pull-requests: write` only in the commenting job, which runs no untrusted code; the running job has `contents: read` and no token mounted | none known |
| T9 | Make the trusted step crash or hang to get a partial result | timeouts; a missing/invalid output is "not verified", never partial credit | none |
| T10 | A malicious maintainer | out of scope (they hold the secret); commit–reveal makes past results checkable | stated |

## Consequences

- A submission is `verified` only after both workflows pass; fork PRs work (the secret is used only by the
  `workflow_run` job in the base repository).
- The held-out set differs per push, so held-out numbers of two pushes are two samples of the same generator,
  reported with N and intervals, never compared as if paired.
- Local runs (`leaderboard.py verify`) keep R2's public-salt held-out set and say so.
- Tests: `lab_web/tools/test_r3_heldout.py` (generation, determinism, the HMAC, what leaves) and
  `tools/r3/hostile/` (submissions that try T2–T6), run locally in the real container and in CI; results in
  `docs/v2/r3/data/heldout/`.
