# ADR 0100 — World Spec v3: a level kit lowered onto v2's primitives

- **Status:** accepted for the M6 foundations branch, 2026-10-17 (M6F.1). Numbered
  from 0100 so it cannot collide with M5's ADRs (parallel work, `docs/v2/m6/PARALLEL_PROMPT.md`).
- **Evidence class:** MODEL (the World Spec, the Arena model).
- **Evidence:** `coco_lab/test/test_worldspec_v3.py`;
  `coco_lab/test/fixtures/m6f/prechange_v1v2.json` (made at `0d1f37f`, before any
  v3 code, by `tools/m6/make_prechange_fixture.py`).

## Context

README §5.1 and invariant 12: from M6 every level is authored once, as a World
Spec, and compiles to the browser world, a Gazebo SDF and a Nav2 map. The COCO
Depot (README §5.9) is about 48 × 32 m with racks, doors, a mezzanine, docks,
objects and moving forklifts and walkers. Writing it as v2's flat list of boxes
and wedges would be a few hundred hand-placed rectangles with no meaning attached:
nothing would know that two boxes are a wall with a door, that a strip must stay
clear as an aisle, or that a box is a bench an object stands on.

The constraint (the M6F prompt's stop condition): every v1 and v2 world still
loads and produces byte-identical model state, golden traces and flat-scene hashes.

## Options

| | Design | For | Against |
|---|---|---|---|
| **A. A kit lowered onto v2's primitives** (chosen) | v3 = the robot, start, arena and bounds blocks as before, plus `kit` (typed elements) and `catalog`. Validation, then **lowering** to v2's `boxes` and `elevation`, which the canonical form carries as derived fields. | Every consumer that reads `boxes`/`elevation` (the rasteriser, `coco_lab.terrain`, the LiDAR, the SDF generator) works unchanged; v1/v2 code paths are not edited at all. The kit carries meaning the validator can check (aisles, doors, supports, lanes). | Two levels of description in one canonical form (authored kit + derived primitives); idempotence has to be enforced (it is: derived fields are recomputed and compared). |
| B. Extend v2 in place (new optional keys) | `boxes` gain optional fields; new top-level lists | One format | Touches v2's validator, the one that produces every existing hash; a v2 file would no longer mean exactly one thing to old readers; no place for meaning (a door is still two boxes). |
| C. A separate level format compiled to a v2 file | The Depot authored elsewhere, a v2 file generated and committed | No new version | The game's world would be a v2 file whose structure (doors, aisles, objects, actors) is lost; Grasp Assist, the games and the generators need that structure at run time. |

## Decision

**A.**

- `spec_version: coco.world_spec.v3`. Required: `id`, `title`, `frame` (`world`),
  `world_to_map`, `bounds`, `robot`, `start`, `arena`, `kit`. Optional: `catalog`,
  `sources`, `notes`. The v1/v2 `ramps` block does not exist in v3 (it only described
  the COCO arena's four bays; ramps are kit elements).
- Kit element kinds: `wall` (axis-aligned, with door openings cut by `door` elements),
  `door`, `rack` (shelves and required aisles), `bench`, `pallet`, `box` (a raw v2 box,
  for converting v2 worlds), `ramp` (an axis-aligned wedge, optionally `onto` a
  platform), `platform` (a mezzanine), `zone` (dock, drop, pickup, start, region),
  `object` (a catalog item on the floor, a bench, a rack shelf, a pallet or a
  platform), `actor` (a forklift or walker lane: path, `loop` or `pingpong`, speed,
  footprint, height, phase).
- **Lowering** (`coco_lab.worldspec_v3.lower`): solids → v2 boxes standing on the
  floor (`z = height / 2`); walls split at their doors into `<id>#<n>` boxes; ramps →
  wedges; platforms → platforms. The canonical form carries the lowered `boxes` and
  `elevation`; re-normalising recomputes and compares them, so `normalize` is
  idempotent and a derived box cannot be hand-edited.
- **Registration**, the only edits to existing files: `worldspec.normalize` hands a
  v3 spec to `worldspec_v3.normalize_v3` *before* any v1/v2 code runs;
  `worldspec.TERRAIN_SPEC_VERSIONS = (v2, v3)` replaces the two `== v2` checks
  (`arena_map`, `Arena.__init__`); the Arena's legacy gated grasp refuses on a v3
  level (it holds the COCO arena's four targets; v3 picks with Grasp Assist).
- **Validation refuses, with the reason**, what the two tiers would disagree about:
  a solid at or below the LiDAR beam (`scan_height`: the Stack's 2D scan cannot see
  it, the model's map would hold it); a door or rack aisle narrower than
  `passable_width = 2 × (robot.radius + arena.resolution)` (the plan map inflates by
  the radius; the rasteriser can grow a solid by a cell); an aisle another solid
  stands in; a ramp the terrain model cannot follow (yaw other than 0 or π) or that
  does not meet the platform it claims to climb onto; an object inside a solid or off
  its support; an actor lane whose footprint passes through a solid. Every threshold
  is derived from the spec's own robot and arena blocks.
- **Actors are kinematic functions of time** (`actor_pose(actor, t)`), never
  simulated: the same pose in the model, in the game rules and (driven by
  `set_pose`) in Gazebo, where they are models with collision bodies (M6F.2).

## Consequences

- v1 and v2 are untouched: the pre-change fixture's canonical bytes, maps and 12
  seeded sessions (hash v1 and v2), and the first 10 committed M1 determinism sessions'
  Pyodide hashes, all replay byte for byte through the v3 reader (tested).
- `from_v2` writes any v2 world as kit elements; lowering gives back the same boxes,
  elevation and maps, and the Arena drives it tick for tick identically under hash
  v1. Hash v2 (ADR 0008) commits to the canonical spec, so the same geometry spelled
  as v3 is, correctly, a different world there.
- The `box` kinds stay v2's four (`wall`, `obstacle`, `landmark`, `guard`) so the
  existing renderer and converters read lowered v3 boxes without change; the kit
  element a box came from is its id (or `<wall id>#<n>`).
- Known limits: walls, racks, benches and pallets are solid footprints (a bench's
  legs and a rack's open bays are not modelled; the 2D LiDAR at 0.2135 m meets the
  solid). Ramps must be axis-aligned. Actors are not yet in the Arena's LiDAR or
  contact (they are in the game rules, M6F.6); that is M6 UI-phase work.
