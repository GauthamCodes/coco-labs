# M0.5 — what "Remove" found (2026-10-08)

README §4 marks three components **Remove**: Isaac integration inside COCO
Lab, the VLM layer, and browser policy training. Searched on
`v2/m0-transition` over every tracked file (`git ls-files`, `git grep -i`
for `isaac`, `vlm`, `vision-language`, `llm`, `policy train*`,
`onnx`/`onnxruntime`/`tensorflow`, `tfjs`).

## Result: no code or config for any of the three exists in COCO Lab

| Component | In `coco_lab`, `coco_lab_ros`, `lab_web`, `coco_web` | Elsewhere in the repository | Action |
|---|---|---|---|
| Isaac inside COCO Lab | **none** | `coco_sim/coco_sim/backends/isaac.py` — a data-only translation layer of the robot stack's episode spec ("This is the adapter BOUNDARY, not an Isaac integration"; imports no `omni`/`pxr`/`isaacsim`), tested by `coco_sim/test/test_backends.py`. `docs/data/isaac_foundation/` — measured evidence (2026-09-24) of Isaac Sim on this machine | **Kept.** `coco_sim` is a robot-stack package, frozen by README §4 ("Not deleted … G3 decides"); the evidence directory falls under "never delete evidence" (README §3). Neither is Isaac *in COCO Lab* |
| VLM layer | **none** | `docs/M7_DESIGN.md` §2.7 item 2 and `docs/M7_PHASES.md` — the robot project's M7 design ("spec only, nothing built") | Marked in place: "Removed from COCO Lab's scope permanently (2026-10-08)". Design record kept unchanged |
| Browser policy training | **none — never planned for the browser** | `docs/M7_PHASES.md` Phase 4 "Policy training" (robot project, MuJoCo, never started); `coco_rl/` trains the shipped ramp policy (robot stack) | Marked in place: "Not COCO Lab work". `coco_rl` is a frozen robot-stack package |

**Roadmap entries.** The v1 roadmap carried "Full Isaac backend", "VLM
task layer" and "M7 Phase 4 policy training" in its §9 "Deferred" table.
That roadmap is archived unchanged (`docs/archive/v1/ROADMAP.md`); the new
`docs/ROADMAP.md` lists all three as **Removed** and rewrites the old
themes: "Learn" → deferred, "Estimate" → merged into Localise, "Many Robots"
→ deferred. No live document, and nothing in the site's source
(`lab_web/src`, `index.html`), mentions the old later-lab themes.

**Files deleted in M0.5: none** — there was no code, config or
COCO Lab document for these components to delete.
