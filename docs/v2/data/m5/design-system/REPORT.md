# M5.4 · Night Shift checkpoint

Milestone / checkpoints completed: M5.0–M5.3 previously complete; M5.4 complete.
Start SHA: `007f749`; end: the `[M5.4] Establish Night Shift` checkpoint commit, branch `v2/m5-focus`. Authorized M5.4 work was already in the tree at session start.

Gautham's notes: found, blank template preserved. No pre-design observations exist;
that prerequisite was explicitly waived. Nothing Phone (1) is the primary target.
N1 is addressed; N2 has both emulated reference orientations, with interaction
completion assigned to M5.5–M5.7. No usability response or phone measurement invented.

## Change and evidence

- Single TS token source generates initial CSS variables and renderer palettes;
  dark default and explicit light theme, saved through the preferences module.
  Colour/type/spacing/radius/elevation/motion tokens; reduced-motion handling.
- Outfit display and Manrope UI variable fonts, OFL, self-hosted; Lucide icons,
  ISC with retained Feather notice. `docs/v2/DESIGN_ASSETS.json` records source,
  pinned package integrity, every font checksum, icon-tree digest and licence
  checksum. Full notices are shipped locally. The build verifies the manifest.
- Existing CAD arena/robot materials use dark neutral finishes and work lighting.
  Geometry, model state, event data and hash definitions are untouched.
- Real title, Play HUD and two-pane Compare references use the existing assets,
  the existing MODEL attract recording and actual coco_lab search events. The
  Compare reference uses one scissored context; no JavaScript planner or score.
  These are diagnostic reference queries; normal routing migrates in M5.5.
- `COLOUR_REVIEW.md`, `colours-final.json`, five unit tests, full rendered Compare
  simulations and labelled swatches cover both themes and both requested colour
  deficiencies. This is TESTED design simulation, not a human usability pass.

Evidence classes: MODEL for the rendered model/recording and searches; TESTED
for software checks and colour simulations. Phone layout evidence is explicitly
**emulated Nothing Phone (1)**, never a real-device result.

## Verification

Before: packages 3534, web 456, tools 195; five deterministic canvas scenes,
five replays, 22 URL forms plus six archive views passed at M5.3.

After: packages **3534 passed**, web **461 passed**, tools **195 passed**; typecheck, build, asset manifests and dist checks pass. Five additional web tests cover the token contrast/simulation checks. All five final deterministic canvas checks pass with zero differing pixels. Final references: 12 captures, zero console errors, one GL context each (`../screens/reference/final/references.json`). The rendered-pixel regression passes in both themes (`canvas-colours.json`).
Logs: `packages.txt`, `vitest-colour-output.txt`, `tools-rerun.txt`, `build-colour-output.txt`,
`dist-colour-output.txt`, `assets-check.txt`, `screens-colour-check/`, `urls-final/`, `replays/`.
The stable URL run passes 22 forms plus six archive views; all five replays pass with zero console errors.
No model golden/hash update was made. Prior visual baselines are copied to
`../screens/pre-night-shift/`; new palette baselines are intentional visual changes.

Retained failed/intermediate checks: the initial tiny font subset was emitted as
a data URL and refused by CSP; `assetsInlineLimit: 0` fixes this with local files,
without widening CSP. Two initial source-policy failures (hard-coded repo link,
user-agent sniff) are fixed with a relative link and coarse-pointer capability.
One build-tool run exited 143 without a test summary; rerun required. One local
archive check overlapped a dist rebuild, yielding a stale hashed-asset 404; the
fresh, frozen server run passes all 22 forms and six archive views. These failures
are retained, not discarded or counted as passes. Reference display choices are
reapplied after asynchronous recording buffers are created. Explicit HUD stacking
keeps overlays above the canvas. The floor shader now converts its linear colour
to sRGB; a rendered-pixel check verifies the real output against both token palettes.

## Measurements and limits

Reference JSON records power/AC, driver, renderer, dimensions, GL contexts and
console errors. Balanced, AC, NVIDIA 580.178.04 reported; browser captures use
software GL (actual renderer in JSON), not RTX/Intel frame-rate acceptance.
CPU-heavy suites and a system unattended driver build overlapped this work; no
performance budget is claimed from these layout checks. Original balanced power
profile was unchanged. Toolchain: Node 24.21.0, Python 3.12.3 pinned workspace venv.

Phone references use 915×412 / 412×915, DPR 2.625, mobile/touch and CPU 4× proxy.
They do not emulate an Adreno GPU. Layout captures use local, unthrottled assets;
emulated 4G startup measurements remain M5.11. ADB: no attached device, recorded
in `../phone/ADB_CHECK_M54.txt`. Real Phone remains pending: connect over USB.

M5.4 acceptance: tokens/themes, licensed self-hosted fonts/icons, colour simulation
and real reference screens implemented. Gautham's aesthetic review remains pending
as a soft gate. Whole-app keyboard/accessibility, Focus, final routes, performance,
real phone and launch-owner gates remain for their specified checkpoints.

Screenshots awaiting Gautham: [all reference sizes and simulations](../screens/reference/README.md).
Initial and refinement captures are retained. No feedback received yet.

Files moved or removed this checkpoint: none. Palette definitions now live in
`tokens.ts`; `render/palette.ts` remains a compatibility export. Previous screenshot
baselines are preserved as evidence copies, rather than deleted.

ADRs: none new. Owner amendments remain in the dated 2026-10-14 plan-change log.
Deviations: none in scope/order; environment interruptions recorded above.
Ideas parked: none. Stop condition: none. Five-person usability stays Gautham-owned
and gates public launch only. No release, merge, robot-project edit or cloud work.

Questions: the one M5.4 USB connection request is recorded in STATUS; do not wait.
Next step: M5.5 actual title/app shell, About, Settings and old-route migration.
Phone defaults: provisional 60 fps (optional 120), automatic tier with 1.5–2.0 DPR
caps; final settings depend on the real 10-minute heat run. Play interaction/cap
implementation is M5.6, not claimed complete here.
