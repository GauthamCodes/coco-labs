# Visual design system v1 (M1.6)

README §5.3: a visual design system with fixed colour semantics per layer.
Code: [`lab_web/src/arena/render/palette.ts`](../../lab_web/src/arena/render/palette.ts)
(the only place colours live) and
[`render/Renderer.ts`](../../lab_web/src/arena/render/Renderer.ts).

## Rules

1. **One colour per layer, everywhere.** A layer never borrows another's
   colour; a new layer gets a new colour here first.
2. **Truth is always an outline**, never a fill (dashed). Nothing a learner
   might mistake for the model's belief is ever solid in the truth colour.
3. **Uncertainty is always translucent** (M2: covariance, particles).
4. **Heat is viridis**: perceptually uniform, ordered, readable in greyscale
   and by the common colour-vision deficiencies. It is used for one thing
   in M1: the expansion order (end-of-run heatmap).
5. **Two themes, same meaning.** Light and dark swap values, never roles.
   `?theme=light|dark` overrides the system preference.
6. **The evidence badge is always visible** (MODEL in the Arena).

## Layers (bottom to top)

| Layer | Meaning | Light | Dark | Drawn as |
|---|---|---|---|---|
| free | traversable cell | `#fbfbfa` | `#1d1d22` | grid data texture |
| occupied | wall, obstacle | `#3a3a40` | `#b9b9c2` | grid data texture |
| unknown | not seen; non-traversable | `#c9c9cc` | `#3a3a42` | grid data texture |
| closed set | expanded by the search | `#4b6fc4` at 42 % | `#6f8ff0` at 45 % | per-cell state texture, tinted |
| heatmap | expansion ORDER, first → last | viridis | viridis | per-cell state texture (24-bit order) |
| frontier | pushed, not yet expanded | `#e66100` | `#ff9a3c` | instanced squares |
| path | the chosen path | `#c4125a` | `#ff5c9a` | line |
| LiDAR | the robot's beams | `#0f8b8d` at 55 % | `#36c5c7` at 50 % | merged line segments (one buffer) |
| footprint | the collision radius the planner inflates by | `#6b6b75`, dashed | `#9a9aa6`, dashed | line loop |
| robot | COCO's chassis outline (Gazebo mesh) + heading | `#2b2b33` + `#ffd23f` | `#e8e8ee` + `#ffd23f` | filled shape |
| truth | ground truth pose | `#1a9641`, dashed outline | `#4fd27a`, dashed outline | line loop |
| goal | the goal | `#c4125a` | `#ff5c9a` | ring |
| inspected cell | the picked cell | `#111111` | `#ffffff` | square outline |

## M2 layers: the lenses (M2.2)

Every lens's layers, fixed here first (code: `palette.ts`; the layers and
their roles: `lab_web/src/arena/lens/registry.ts`; the primitives:
`render/lensLayers.ts`). `test/lens_registry.test.ts` holds every lens to
the rules: a palette key per layer in both themes, unique ids, no layer in
the truth colour, and every **uncertainty** layer translucent (its
`…Alpha` < 1; the ellipse primitive refuses an opaque alpha).

| Lens | Layer | Role | Light | Dark | Drawn as |
|---|---|---|---|---|---|
| Localise | particles | uncertainty | `#7b3294` at 35 % | `#c2a5cf` at 40 % | instanced discs, size = weight |
| Localise | estimate | computation | `#5e3c99` | `#b8a6e6` | pose arrow |
| Localise | covariance | uncertainty | `#b2abd2` at 30 % | `#8073ac` at 35 % | filled 95 % ellipse + outline |
| Localise | odometry | computation | `#8c510a` | `#dfc27d` | pose arrow |
| Map | built map | computation | `#f4f4f0` → `#252529` | `#26262c` → `#e0e0e8` | log-odds texture; unknown (l = 0) clear |
| Map | SLAM pose | computation | estimate's colour | estimate's colour | pose arrow + trajectory |
| Map | landmarks | uncertainty | `#d01c8b` at 45 % | `#f1b6da` at 50 % | discs + 95 % ellipses; the sensor labelled **IDEALISED** |
| Map | SLAM particles | uncertainty | particles' colour | particles' colour | instanced discs |
| Map | pose graph | computation | nodes `#01665e`, edges `#80cdc1`, loops `#c51b7d` | `#5ab4ac`, `#2a7f78`, `#f1b6da` | points + line set |
| Move | chosen | computation | `#fdae61` | `#fee090` | thick line |
| Move | candidates | computation | `#2c7bb6` at 35 %, shaded by cost | `#64b0e6` at 35 % | merged line set |
| Move | rejected | computation | `#d7191c` at 25 % | `#ff6b6b` at 25 % | merged line set; the reason on hover |
| Move | local window | computation | `#545454`, dashed | `#9a9aa6`, dashed | square |
| Move | lookahead | computation | `#a6611a` | `#e6b36a` | disc |
| Move | actors | world | `#b35806` | `#f1a340` | discs at their collision radius |
| Decide | belief | computation | `#e08214`, alpha = P × 55 % | `#fdb863`, alpha = P × 50 % | filled bay polygons |
| Decide | detections | computation | `#008837` | `#5aae61` | marker; the detection probability labelled |
| Decide | bays | world | `#6a6a74` | `#8a8a96` | outlines |

**Uncertainty is always translucent** (rule 3, now enforced in code and
tests); **truth stays the M1 renderer's dashed outline**, drawn by no lens.
Belief and estimate are solid only where they are a single best guess (an
arrow), never where they are a distribution.

## Lenses, levels and Focus (M2.2)

- **One lens per family of computation**: Plan, Localise, Map, Move,
  Decide. A lens lays out and aggregates what coco_lab emitted; it never
  computes the algorithm (README §5.2).
- **Watch** shows at most two computation layers (tested); **Explain**
  adds a layer or two, value labels on hover and a short caption at each
  key event (`lens/captions.ts`); **Inspect** shows every layer, the
  inspector (one template per family), the event log and metric charts.
  Charts appear only at Inspect, or when a mission asks for one.
- **Focus** dims everything outside the lens to 25 % (the world to 50 %);
  the robot and the truth outline are never dimmed.

The frontier's orange and the closed set's blue are a colour-blind-safe
pair (no red/green distinction carries meaning). The goal shares the
path's colour on purpose: the path is the route to that goal.

## The robot

COCO's outline is built from the Gazebo chassis mesh
(`gazebo_models/meshes/base.stl`) at build time by
`lab_web/tools/build_arena_assets.mjs`: the convex hull of its top-down
projection, millimetres to metres, centred on `base_link` (a 0.24 × 0.274 m
octagon). Converting the full Gazebo meshes to glTF (optional in M1) is
not done.

## Techniques (README §5.3)

- **Data textures** for the grid: the occupancy (one byte per cell) and the
  search state (state + 24-bit expansion order per cell), one shader.
- **Instancing** for points (frontier cells).
- **Merged line buffers** for fans and rays (all 480 beams in one buffer).
- **Picking** by cell: the inspector shows the cell's state, expansion
  order, g, h, f, parent and the latest event, all read from the events
  coco_lab emitted (`render/planStore.ts`), never recomputed.

Measured load (laptop, RTX 4050 via ANGLE/OpenGL ES 3.2, headless
Chromium 156): the Arena plus 50,000 instanced points and 20,000 line
segments renders at 60–61 fps (10 s, every second sampled), p95 frame
16.9–17.0 ms (`docs/v2/data/m1/render/fps_stress_gpu.json`). The same load
on Chromium's software rasteriser (SwiftShader) runs at 1–2 fps, which is
why every fps number names the GL renderer.
