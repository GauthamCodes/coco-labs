# ADR 0007 — World Spec v2: elevation as ramp primitives, not a heightfield

- **Status:** accepted, 2026-10-11 (M4.2, drafted in M4.1).
- **Evidence class:** MODEL (the World Spec, the Arena model). The reference
  geometry is the Gazebo world the recordings ran (STACK).
- **Evidence:** `lab_web/public/assets3d/arena.json` (the converted SDF's
  footprints); the agreement check in CI (`lab_web/tools/test_worldspec_sdf.py`).

## Context

README §7 M4.2: "World Spec v2 with elevation, and the World Spec ↔ SDF
agreement check in CI". M4.3's kinematic terrain following reads height and
pitch from the World Spec, so COCO visibly climbs the ramp onto the
platform (README §5.1). The prompt: "Choose a representation, a heightfield
or ramp primitives, and record it in an ADR. … The recorded SDF world is
the reference. Fix the World Spec, never the SDF."

What is elevated in the recorded world (`coco_navigation.world` + the
`traverse:=true` spawns, `convert_world.py`): in each of the four bays, an
up-wedge (a right triangular prism: 2.0 m run, 2.5 m wide, rise
2·tan 18° = 0.6498 m), a flat platform box (1.2 × 2.5 × 0.6498 m) at the
crest, and a mirrored down-wedge. Everything else stands on the ground.
World Spec v1 already carries these numbers in `ramps` (foot 1.0, run 2.0,
angle 18°, platform 1.2, width 2.5, centres ±2, ±6 m), and they equal the
launch file's constants exactly (checked in M4.1).

## Options

| | Representation | For | Against |
|---|---|---|---|
| **A. Ramp primitives** (chosen) | A list of solids with analytic tops: `wedge` (foot, yaw, run, rise, width) and `platform` (centre, size). Height h(x, y) is the highest top under the point. | Exactly the SDF's geometry: the agreement check compares like with like, to 1 mm. h, the slope and the edges are exact and cheap in Pyodide, deterministic in every engine (a few multiplications, no interpolation). The crest and the platform edge are where the robot's pitch changes; they stay sharp. A few hundred bytes. | Only solids of these kinds; a new shape needs a new primitive (a second world is a non-goal in M4). |
| B. Heightfield | A grid of heights (e.g. 0.05 m cells) over the arena | Any terrain | Discretises the crest and the side drops (the 0.65 m vertical faces become 0.05 m-wide slopes); its interpolation is another float path to keep identical across four engines; ~170 k samples for the arena; the agreement check becomes a sampling tolerance, not a geometric one. |

## Decision

**A, ramp primitives.**

- World Spec **v2** = v1's fields unchanged, plus `elevation`: a list of
  `{id, kind: wedge | platform, …}` in the Gazebo world frame. The four
  bays' up-wedges, platforms and down-wedges are generated from the same
  `ramps` block the v1 generator already reads, so the two cannot drift.
- **The flat scenes do not change.** The v1 file (`worlds/coco_arena_v1.yaml`)
  and everything hashed from it stay byte-identical: every M1–M3 session,
  golden trace, Play level (the map challenge names the v1 spec's hash) and
  share link. Terrain sessions name the v2 spec. (README §7 M4 stop
  condition: "Flat-scene hashes change.")
- **Agreement with the SDF, in CI:** every one of the 70 boxes' footprint
  (centre, size, yaw), centre height and height, and every wedge's foot,
  yaw, run, width and rise and every platform's centre and size, against
  `arena.json` (the converted recorded world), within **1 mm**. On a
  disagreement the World Spec is fixed, never the SDF.
- **Kinematic terrain following (M4.3)** reads z = h(x, y) at the
  wheels' contact points and takes pitch and roll from them; nothing
  simulates tipping, slip or contact forces (README §3 invariant 10).

## Consequences

- One more primitive kind is all a new elevated solid costs; a different
  kind of world (a second world) would revisit this ADR.
- The heightfield option stays open for a world that needs it; the
  `elevation` list can gain a `heightfield` kind additively.
