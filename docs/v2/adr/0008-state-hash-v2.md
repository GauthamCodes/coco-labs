# ADR 0008 — Behavioural state hash v2

Date: 2026-10-14. Evidence class MODEL. Scope M5.1.

## Audit

V1 is preserved byte for byte. Its layout hashes the waypoint count/index,
but not waypoint contents or the held teleop command. M4's hand-back goal,
command ownership and user-teleop flag were omitted. The deferred subsystem
goal can affect the next tick. Constructor sensor sampling and immutable
world configuration were external assumptions rather than hash inputs.

Subsystem layouts have further gaps: Localise omitted filter parameters,
anchors and cached estimates used by planning; Map omitted occupancy grids,
FastSLAM's per-particle maps, EKF covariance, and pose-graph edge content;
Move omitted controller parameters, full trackers, actor configuration and
progress position; Mission omitted progress position and truth override.
These can influence future outputs while v1 bytes remain equal.

## Decision

V2 uses a separate domain and chain seed, an immutable world/sensor digest,
and a canonical recursive snapshot of mutable model fields and nested
subsystems. Object aliases are traversal paths, never memory addresses.
Floats are IEEE-754 hex strings, preserving small behavioural differences.
Unknown state object types fail loudly rather than silently omitting state.
The snapshot includes held commands, goals, hand-back, waypoints, subsystem
configuration, full filter/map/controller state and RNGs.

Immutable world derivatives are anchored by normalized spec/sensor input;
the planning map is derived from it and the hashed plan_clearance. Cameras,
rendering, transport callbacks and transient search iterators/snapshots are
excluded. Hashes are taken at completed tick boundaries, not during search.
`state_v2.EXCLUDED` lists root-only exclusions; nested engine grids and
parameters are included. New mutable model fields are included by default.

The default Arena constructor remains v1 for old tools and fixtures. New
live pages explicitly use v2; old links lacking hv use v1. Run links record
hv. Challenge links can record hv and keep their independently versioned
score format; their score is metrics, not an Arena state chain. Their v1
results must remain unchanged. No physics/model behaviour changes.

## Validation

`test_state_hash_v2.py` tests formerly omitted fields and equal motion
across versions. Existing golden and flat-scene fixtures are never edited.
`link_bounds.test.ts` covers z, s, identifiers, run size/ticks/input count,
compression bombs and the crafted 10^12 first tick. Four-engine v2 corpus
and committed-link verification are recorded under data/m5/defects when
run; this ADR alone does not assert those measurements passed.

## Historical challenge-score JSON

The all-committed-link check identified 11 M3.5 hashes made before M3.6
normalized integral floats (1.0 → 1). `v1-mismatch-baseline.json` proves
baseline c11bf9e and M5 yield identical current hashes for those inputs;
all 11 match the original raw-JSON hash. This is pre-existing, not a v1
state-hash or golden-trace change. `verification_hashes` computes both
specified layouts in Python before JavaScript loses integral-float types.
V1 links may verify that older layout; v2 links accept the current layout
only. Scores and canonical result hashes remain unchanged. Verification
metadata lives in the worker reply/CLI evidence, outside the scored result.
