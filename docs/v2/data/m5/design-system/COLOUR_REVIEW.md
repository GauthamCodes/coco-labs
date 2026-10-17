# M5.4 computation colour review

TESTED design simulation, not a human colour-vision or usability result.

The sole token source is `lab_web/src/ui/tokens.ts`. Semantic meanings stay fixed:
orange frontier, blue expanded cells, pink path, red rejected candidates, purple
uncertainty, green dashed truth outline. Uncertainty remains translucent. Viridis
remains the ordered heat scale. Labels and shapes accompany colour.

Method: Machado, Oliveira and Fernandes (2009), severity 100 matrices, applied to
linear RGB, clamped to display gamut and returned to sRGB. Matrices were checked
against the authors' published model as distributed by
[colorspacious](https://github.com/njsmith/colorspacious/blob/master/colorspacious/cvd.py).
Paper: [A Physiologically-based Model for Simulation of Color Vision Deficiency](https://doi.org/10.1109/TVCG.2009.113).
The browser captures use SVG `feColorMatrix` with `color-interpolation-filters="linearRGB"`.

Opaque role swatches must have pairwise CIELAB D65 deltaE76 >=10 under both
simulations. This is a declared engineering check, not a clinical threshold or
proof that every person can distinguish every small/translucent mark. The real
scene captures and labelled shape swatches are retained for review. The expanded
blue cells are translucent; paths are lines, frontier cells an edge, truth an
outline and uncertainty discs. Final M5.7 interaction checks remain required.

| Theme | Simulation | Closest opaque role pair | deltaE76 |
| --- | --- | --- | --- |
| dark | protanopia | path / particles | 16.752831 |
| dark | deuteranopia | rejected / truth | 14.625757 |
| light | protanopia | frontier / truth | 13.827054 |
| light | deuteranopia | frontier / rejected | 14.858913 |

All tested UI text pairs (normal, muted, accent and evidence labels on each panel)
meet WCAG AA 4.5:1; the minimum is 5.292143:1.
Error labels also pass; primary opaque computation strokes on the free-cell
background meet 3:1 (`test/night_shift.test.ts`). This checks token combinations,
not every legacy panel; whole-app keyboard/accessibility checks remain M5.11.

Initial dark rejected red `#ff6b6b` approached green truth under deuteranopia
(deltaE76 8.117325, retained in `colour-initial.json`). It is tuned to `#df6b54`.
Light chosen-trajectory ochre is darkened to `#a66200` for graphical contrast.
Neither change alters a computation role, model event or hash.

Reproduce: pinned Node, from lab_web, `node tools/m54_colours.mjs
../docs/v2/data/m5/design-system/colours-final.json`; `npm test --
 test/night_shift.test.ts`; run `m54_references.mjs` and `m54_palette_sheets.mjs`
against the built site. Actual full Compare scenes and both-theme swatches are
under `../screens/reference/`, including protanopia/deuteranopia captures.

The custom grid shader originally wrote linear RGB directly to the output,
darkening the free-cell floor. Its output now includes the sRGB conversion.
`m54_canvas_colours.mjs` checks actual WebGL pixels in both themes against the
free-cell token within one channel value; `canvas-colours.json` retains the
counts. This checks a mostly-free committed scene, not an invented benchmark.
