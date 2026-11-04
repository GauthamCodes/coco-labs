# R1 · Research Workbench — before and after

Screenshots catch regressions; **Gautham judges the look** (README §9 rule 8).

| | Before | After |
| --- | --- | --- |
| Tree | `3a03f48` (= main `7bbb430` + R1.0 paperwork) | `18d13c3` (R1.8) |
| Tool | `lab_web/tools/r1/screens.mjs` (G1's tool plus Learn) | the same, plus the Workbench tabs |
| Renderer | ANGLE, NVIDIA GeForce RTX 4050 Laptop GPU (OpenGL ES 3.2) | the same |
| Metadata | [`screens/before/shots.json`](screens/before/shots.json) | [`screens/after/shots.json`](screens/after/shots.json) |

Desktop is 1440 × 900; the phone columns are the **emulated** Nothing Phone (1) (viewport, touch, 4× CPU throttle
on this laptop's GPU), never a phone. The `play` shots in both sets show Play's mode select (no canvas before a
game starts, so the tool's ready condition times out there; unchanged by R1).

## The four surfaces the prompt names

| Surface | Before | After | What changed (as seen) |
| --- | --- | --- | --- |
| Title, desktop | ![](screens/before/desktop-title.png) | ![](screens/after/desktop-title.png) | One big PLAY and three small doors (Compare, Research, Learn) → **three equal doors Play · Learn · Workbench**; a quiet "Compare algorithms side by side →" link below; any key still plays |
| Title, phone landscape | ![](screens/before/phone-landscape-title.png) | ![](screens/after/phone-landscape-title.png) | the same three doors in one row |
| Title, phone portrait | ![](screens/before/phone-portrait-title.png) | ![](screens/after/phone-portrait-title.png) | the doors stack |
| Compare, desktop | ![](screens/before/desktop-compare.png) | ![](screens/after/desktop-compare.png) | top bar Play · Learn · Compare · Workbench; the live comparison unchanged; a **Scenario** section (start and goal source, Previous/Next, "Turn this into an experiment") in the controls |
| Compare, phone landscape | ![](screens/before/phone-landscape-compare.png) | ![](screens/after/phone-landscape-compare.png) | top bar only (the controls sheet holds the Scenario section) |
| Compare, phone portrait | ![](screens/before/phone-portrait-compare.png) | ![](screens/after/phone-portrait-compare.png) | top bar only |
| Research → Recordings, desktop | ![](screens/before/desktop-recordings.png) | ![](screens/after/desktop-recordings.png) | the library unchanged, now under the Workbench tabs (Experiments · Benchmarks · **Recordings** · Datasets); eyebrow "WORKBENCH · RECORDINGS" |
| Recordings, phone landscape | ![](screens/before/phone-landscape-recordings.png) | ![](screens/after/phone-landscape-recordings.png) | the tabs above the library |
| Recordings, phone portrait | ![](screens/before/phone-portrait-recordings.png) | ![](screens/after/phone-portrait-recordings.png) | the tabs wrap to two rows |
| Learn, desktop | ![](screens/before/desktop-learn.png) | ![](screens/after/desktop-learn.png) | `?view=learn` opened Compare's tours → **a Learn page**: seven mission cards, each with its tour and a pre-made experiment |
| Learn, phone landscape | ![](screens/before/phone-landscape-learn.png) | ![](screens/after/phone-landscape-learn.png) | cards in two columns |
| Learn, phone portrait | ![](screens/before/phone-portrait-learn.png) | ![](screens/after/phone-portrait-learn.png) | cards in one column |

## New surfaces (no before)

| Surface | Desktop | Phone landscape | Phone portrait |
| --- | --- | --- | --- |
| Workbench · Experiments (the builder; default spec) | ![](screens/after/desktop-workbench.png) | ![](screens/after/phone-landscape-workbench.png) | ![](screens/after/phone-portrait-workbench.png) |
| Workbench · Benchmarks | ![](screens/after/desktop-benchmarks.png) | ![](screens/after/phone-landscape-benchmarks.png) | ![](screens/after/phone-portrait-benchmarks.png) |
| Workbench · Datasets | ![](screens/after/desktop-datasets.png) | ![](screens/after/phone-landscape-datasets.png) | ![](screens/after/phone-portrait-datasets.png) |

The results view (after a run) is in R1.3's full-page shots: [`data/r13/a11y/`](data/r13/a11y/) (desktop and
emulated phone landscape, dark and light); Benchmarks and Datasets in full: [`data/r15/a11y/`](data/r15/a11y/),
[`data/r16/a11y/`](data/r16/a11y/).

## Looks wrong / for Gautham to judge

- The title's doors now have equal weight as asked; PLAY is no longer the visually dominant button (any key
  still plays). Gautham asked for equal weight; whether the game still reads as the front door is his call.
- The scenario maps on the Benchmarks tab draw zones and start/goal marks, not the walls (no occupancy
  raster on that page yet).
- Workbench forms are dense on a phone in portrait; landscape is the supported phone layout (R1.3).
- Found at R1.9 and fixed: in emulated phone portrait the builder's "Name in results" field ran past its
  fieldset (fields now never exceed their row); the after set above was retaken with the fix.
