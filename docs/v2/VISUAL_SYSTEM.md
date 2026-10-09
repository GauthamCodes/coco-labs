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
