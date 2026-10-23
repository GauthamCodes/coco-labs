# G1 art direction — "Night Shift Depot"

Source: `G1_PROMPT.md` §1.1 (Gautham, 2026-10-20). This file turns that brief into rules
an implementation can be checked against. It is presentation only: nothing here enters
the model or the per-tick state hash (README §3 invariant 11), and nothing here may
claim physics the model does not have (invariants 10 and 13).

## 1. The idea in one paragraph

It is night inside a big robot warehouse. The hall is dark and moody, but every light
is crisp and has a reason to be there: LED strips over the aisles, EXIT signs, a dock
light spilling in through a roll-up door. Surfaces look like they belong to a real
place — polished concrete, painted lines, steel racking with loaded pallets — and the
brightest, most saturated things on screen are the ones the player needs: COCO, its
target, the drop zone, the plan, the STOP button.

## 2. Palette (design tokens)

| Token | Hex | Use | Never used for |
| --- | --- | --- | --- |
| `bg` | `#0E1116` | page and void beyond the hall | text |
| `surface-1` | `#1B2230` | HUD glass, cards | — |
| `surface-2` | `#2A3344` | raised cards, button rest state | — |
| `coco` | `#FF7A1A` | COCO's accents, the PLAY button, the primary action ring | danger |
| `sensor` | `#22D3EE` | LiDAR, Robot vision, autonomy LED, AUTO when on | the plan |
| `plan` | `#F43F8E` | the global plan, the minimap path, the planner ghost | obstacles |
| `safe` | `#34D399` | delivered, manual-drive LED, valid target ring | — |
| `danger` | `#EF4444` | STOP, contacts, lethal cost | decoration |
| `hazard` | `#FACC15` | hazard stripes, forklift beacons, inscribed cost band | text on light |

**Colour is never the only carrier of meaning** (colour-blind safety):

| Meaning | Colour | Also carried by |
| --- | --- | --- |
| STOP | red | octagon shape, the word STOP |
| plan | magenta | a solid ribbon with chevrons pointing along it |
| LiDAR | cyan | dotted hit points and a filled fan |
| lethal / inscribed / inflation | red / yellow / gradient | cross-hatch, diagonal stripes, smooth fade |
| target object | glow | a pulsing ring around it and a ▼ marker above |
| drop zone | green when the target | a dashed border that marches, and an arrow icon |
| mode MANUAL / AUTO / STOPPED | green / cyan / red | the word on the mode chip and the LED pattern (solid / chase / blink) |

## 3. Type

- **Chakra Petch** (OFL-1.1, `@fontsource/chakra-petch`, self-hosted): HUD numbers,
  headings, button words. Uppercase with +4 % tracking for button words.
- **Inter** (OFL-1.1, `@fontsource-variable/inter`, self-hosted): small text, tips,
  settings rows.
- All numbers use `font-variant-numeric: tabular-nums`, so the timer and speed do not
  jiggle.
- No third-party font request: both faces ship from the site's own origin and the
  service worker caches them. Licence text, source and checksums go in
  `docs/v2/DESIGN_ASSETS.json`.

## 4. The Depot, element by element

| Element | Treatment | Model truth it must respect |
| --- | --- | --- |
| Floor | Polished concrete: seeded tiling noise, roughness variation, a baked light map giving pools under fixtures and AO along walls and rack feet | the floor is flat except the ramp and deck the spec declares |
| Paint | Lane lines, yellow/black hazard stripes at crossings, big zone numbers ("A1", "DOCK 2"), drop-zone squares | decals ≤ 2 cm: drawn flat on the floor, never solid |
| Walls | Modular panels with a trim line, steel columns on the panel joints | every wall mesh is exactly a kit `wall` box (collision footprint) |
| Dock | Roll-up doors drawn ON the wall (closed), a warm dock light | doors in the spec are openings; drawn openings are openings |
| Workshop | Fence-mesh panels on the workshop walls | the mesh is drawn on the wall's own box; it is solid in the model and Gazebo |
| Mezzanine | Deck with railings on its open edges, ramp with chevrons | railings sit outside the drivable deck surface edge… see §7 |
| Racks | Upright frames, beams, and per-shelf loads (boxes, crates, shrink-wrapped pallets), instanced, varied by seed | the whole rack is one solid box in the model; loads stay inside it |
| Benches, pallets | Low-poly, instanced | each is exactly its kit box |
| Light | Cool blue-grey ambient; warm LED strip fixtures; emissive EXIT signs; dock light | baked into the floor light map at build time; no runtime light cost beyond a hemisphere + one key |
| Atmosphere | Light depth fog; dust in light shafts on the high tier only; dark ceiling with visible fixtures | fixtures hang above 4 m: outside the robot's reach |
| Actors | Forklifts with amber beacons, walkers in hi-vis vests | each mesh fits inside its actor's footprint box, at the model's kinematic pose |
| COCO | Real URDF model, orange accents, headlight cone, status LED strip (green manual, cyan auto, red STOP), blob shadow on low, real shadow on high | the LED shows the model's command source, never a guess |

### The Proving Ground ("test lab")

Light-grey lab floor with a 1 m grid and calibration marks, panel walls with trim, the
same lighting style and a baked AO. Visuals only: the World Spec, its canonical bytes and
every v1/v2 hash stay byte-identical (tested).

## 5. Budgets (per world)

| Tier | Download (gzip) | Triangles | Draw calls |
| --- | --- | --- | --- |
| low | ≤ 1.2 MB | ≤ 150 k | ≤ 120 |
| high | ≤ 3 MB | ≤ 400 k | ≤ 250 |

Repeats are instanced. ACES filmic tone mapping always; bloom on emissives on the high
tier only. Medium must hold 60 fps on the emulated Nothing Phone (1).

## 6. Motion and feel

- 150–250 ms eased UI transitions; one pulse on decisions; `prefers-reduced-motion`
  removes pulses, marching borders and camera easing beyond a straight cut.
- No camera shake, no bob, no fake suspension (README §5.6). The chase camera's spring
  is the only "feel", and it follows the model's real acceleration limits.
- Haptics: a short tick on GRAB, a double tick on delivery, a long buzz on STOP, a thud
  on contact; silent when the device or the setting says no.

## 7. Decorative honesty (G1 §0)

A thing that looks solid must be solid in the model and in Gazebo; a thing the robot can
pass through must not look solid. Every decorative mesh is in one of four classes, and a
test (`lab_web/test/g1_honesty.test.ts`) checks each against the World Spec:

1. **solid** — lies inside a collision footprint (a kit box or an actor box);
2. **wall** — mounted on a wall box's face, inside its footprint plus 5 cm;
3. **overhead** — its lowest point is above 2.5 m (fixtures, signs, ceiling);
4. **decal** — at most 2 cm tall, flat on the floor;
5. **outside** — outside the drivable bounds.

Mezzanine railings are class 1: they stand on the deck's own platform box edge, which
is solid in the model (the deck is an elevation solid; the robot may only reach it by
the ramp), and they are not drawn across the ramp's mouth.

## 8. Where the evidence label lives

In Play the evidence label is a small ⓘ chip (top-right, under Pause): it opens a sheet
saying MODEL · kinematic, MODEL · MoveIt-style for Grasp Assist, and what is real
(STACK recordings) and what is not (no physical robot). It is never a banner.
