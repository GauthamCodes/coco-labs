# R3.3 · ADR 0014 hostile tests — TESTED (laptop, docker, the workflow's exact container flags)

`tools/r3/hostile_check.py --out docs/v2/r3/data/heldout` → [`hostile.json`](hostile.json): **PASS**.
A fresh random secret (never written to disk or printed; only its sha256 is in the JSON) generated a
depot-narrow-30 held-out file exactly as the trusted workflow does; the verifier image was built from this
tree; every container ran with `--network none --read-only --cap-drop ALL --security-opt
no-new-privileges --user 65534:65534`, CPU/memory/pid limits and three mounts.

| attack | how | result |
| --- | --- | --- |
| find the secret (T2) | `probe.py` as a guard-escaped submission: the environment, `/proc/self/environ`, `/proc/1/*`, every readable file (6,677 read) searched for 64-hex strings | **not found** anywhere; not in any output |
| network (T3) | TCP to 1.1.1.1:443 and 140.82.112.3:443; DNS for github.com | **ENETUNREACH**; DNS failed |
| escalate | the docker socket; the uid | no socket; uid 65534 |
| exfiltrate through outputs (T4) | the scenarios copied to `/out/leak.json`, `probe.json` and stdout | none of these is published (the trusted step reads only `heldout_runs.json`, as typed numbers, and never prints the container's output) |
| exfiltrate through the numbers (T5) | a falsified run whose `path_ratio` is a scenario's start x and whose status holds coordinates | the status is never published; the median **is**: it came out as 13.6 (one coordinate, rounded to 3 significant digits) — the residual ADR 0014 states, observed |
| read the environment from `algorithm.py` | `import os` | refused by the guard (`GuardError`) |
| read the held-out file from `algorithm.py` | `open(...)` | `open` is not a builtin: every run errors, 0/10, nothing out |
| memorise (T6) | a planner that only answers scenarios it has "seen" (a straight line otherwise) | 0/10 on the held-out draw: the per-head set is unknown in advance |

**Verdict:** the design holds against every attack tried; the stated residual (a submission that escapes
both the guard and the container's Python could publish about one rounded number per metric per push,
describing a set that is never used again) was reproduced and is accepted in ADR 0014. ADR 0014 is
**accepted**.

Done 2026-11-10 (R4 Part A): the repository secret `COCO_HELDOUT_SECRET` is set and its commitment is in
[`HELDOUT_SECRET_COMMITMENTS.md`](../../HELDOUT_SECRET_COMMITMENTS.md); first CI run with it and three more hostile
runs in [`docs/v2/r4/data/secret/`](../../../r4/data/secret/README.md) (which also records that this run's
"no coordinate in the published text" passed only by formatting: the accepted T5 residual was 13.6).
