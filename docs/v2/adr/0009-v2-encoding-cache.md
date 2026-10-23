# ADR 0009 · Byte-preserving v2 state encoding

Date: 2026-10-17. Scope: M5.7 Compare responsiveness. Evidence class: MODEL.

## Problem

The controlled Pyodide-in-Node profile found state encoding dominating the
localization comparison, not MCL updates. See the before/after profiles in
`docs/v2/data/m5/compare/pyodide-profile-bytes.json` and
`pyodide-profile-cached.json`, with actual host, power and driver conditions.
Failed earlier browser captures remain as functional diagnostics; their
battery/software-rendering timings are not acceptance measurements.

## Decision

Keep the v2 canonical bytes and every covered field exactly as ADR 0008
specified. No hash-version or model-behaviour change. Optimize encoding only:

- Exact-float vectors are fingerprinted in full on every call, including type
  and IEEE signed-zero distinctions, before reusing their canonical JSON.
- A process-local content cache has at most eight entries; no persistence.
- Large unique integer-cell tuples use native JSON after registering every
  tuple's traversal-path alias. Repeated or previously seen identities use
  the original recursive path.
- Temporary raw-fragment tokens never enter the output; collision detection
  also handles a real model string equal to a token.
- `memo_vectors=False` exercises the original recursive encoding as a byte
  comparison oracle. Mutations, aliases, type changes, nonfinite values and
  signed zero must remain covered.

This is not a faster second planner/filter, a different hash, or an exemption
for supposedly immutable caches. Every float's current contents are checked;
changing a cache entry still changes the hash.

## Verification

`coco_lab/test/test_state_v2_encoding.py` checks byte equality against the
unoptimized path, mutation/type/alias coverage, token collisions, the bounded
cache, and eight saved pre-optimization MCL/EKF hashes. The reference hashes
were captured before editing the encoder. Pyodide's loop integration also
checks optimized/reference byte equality. Existing golden/v1 tests and the
checkpoint suites remain required before closure.
