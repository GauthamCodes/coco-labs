# Held-out secret commitments (ADR 0014, commit–reveal)

Each row is `sha256(SECRET)` for a value of the repository secret `COCO_HELDOUT_SECRET` that the trusted
workflow `leaderboard-results.yml` (job `heldout`) uses. `SECRET` is exactly the stored string: 64 lowercase hex
digits (32 random bytes), no newline; the hash is over its ASCII bytes. To audit a revealed secret:

```bash
printf '%s' "$REVEALED" | sha256sum      # must equal the commitment below
```

The HMAC key that seeds a held-out set is `bytes.fromhex(SECRET)` (`tools/r3/heldout.py seed_of`), so a revealed
secret regenerates every past held-out set and its digest:
`COCO_HELDOUT_SECRET=$REVEALED tools/r3/heldout.py generate SUITE --head HEAD_SHA --out FILE`.

| # | set | commitment sha256(SECRET) | in use | revealed |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-10 13:19:42 UTC | `e3195c2f291c234d15627273568841082b63727b11d602d4b85afa110c52ebd7` | yes | — |

How #1 was made (R4 Part A, 2026-11-10): one Python process generated `secrets.token_hex(32)`, passed it on stdin
to `gh secret set COCO_HELDOUT_SECRET -R GauthamCodes/coco-labs` (its output discarded) and printed only
`hashlib.sha256(secret.encode()).hexdigest()`. The value was never printed, logged, written to a file or shown to
the agent. Rotation (yearly, or at once on any suspicion): publish the old value in the `revealed` column, set a
new one the same way, add its row.
