# M5.3 code shape · 2026-10-15

Milestone / checkpoints completed: M5.0–M5.3; M5.4 next. M5 remains open.
Start SHA: eb5edbc; ending implementation SHA is the M5.3 commit containing this evidence.
Branch: v2/m5-focus. No merge, release, tag or protected evidence deletion.
Gautham's notes: found, blank template preserved; no observations; prerequisite waived.

## Change and evidence

- ArenaApp is a lazy dispatcher; sceneCore owns renderer/cameras, input, worker and session lifecycle. ArenaSceneView holds the original presentation. PlayScene, CompareScene and ResearchScene are thin lazy shells. Routes and controls stay unchanged in this checkpoint.
- source-equivalence.json: extracted component logic and JSX byte-identical to eb5edbc. Python model, v1 hash definitions and golden traces untouched. MODEL / TESTED evidence.
- vite.config.ts: one content-hashed Three.js engine chunk. Its fflate utility stays outside the engine group so existing 2D Play links do not download the renderer. Same compressor implementation, no dependency change. check_dist.mjs enforces the engine and three lazy-shell chunks.
- Build and dist-final.txt pass; final/screens/screenshots.json has five zero-difference images; final/replays/replay_check.json has five passes, zero errors; final/urls/v1_links_check.json has 22 forms and six archive views, zero errors.
- after/verify.json: one coco verify invocation, all 137 committed links match under their hash versions, zero failures. after/defects/check.json: six applied floor picks within one cell; races reject assisted controls on desktop and both emulated Nothing Phone (1) orientations.

## Suites before → after

Packages: 3534 → 3534 passed, zero failed/skipped (packages.txt).
Web: 456 → 456 passed, typecheck passed (vitest.txt, typecheck-final.txt).
Build tools: 195 → 195 passed (tools.txt).
Initial typecheck caught five unused model exports; corrected. Initial bundle grouping pulled the engine into 2D Play through fflate; narrowed and rebuilt. Intermediate evidence retained. Final browser checks repeated on the corrected bundle.

## Per-route bundle inventory

Loaded app asset chunks only, gzip level 6. Generated Pyodide loader/runtime JavaScript, Python and WASM are outside this inventory. This is not the final title-screen acceptance measurement, and not a network timing claim. Reproduce with tools/m5_bundle_inventory.mjs OUT SITE; sources in before/bundles.json and final/bundles.json.

| Route | Before gzip bytes | After gzip bytes |
| --- | ---: | ---: |
| arena | 346019 | 346348 |
| learn | 73178 | 73173 |
| play | 87413 | 87448 |
| casefiles | 75244 | 75242 |
| live | 80877 | 80876 |

## Conditions and acceptance

Balanced on AC, NVIDIA RTX 4050 driver 580.178.04; original profile unchanged. conditions.json plus each browser harness's start/end conditions. Correctness tests ran alongside suites; their timing fields are not performance-budget results.

Agent files: met (AGENTS 178 lines, STATUS <=200, all history preserved, six cache entries only removed in M5.2).
Determinism and defects: met by M5.1 evidence plus unchanged model, full golden suite and 137/137 verification here.
Links: existing forms pass; three-mode route migration pending M5.5. Claims: existing missions and Case Files pass; new tours pending M5.7.
Focus, title, cold/warm starts, final JavaScript budget, frame rate, accessibility and 30-minute hygiene: pending their later checkpoints and M5.11.
Phone: emulated Nothing Phone (1) race checks pass; real phone not connected (adb.txt). Phone row pending USB connection; emulation alone cannot meet it. Default settings still provisional 60 fps, optional 120, automatic tier/pixel cap pending phone heat measurement.
Usability: pending Gautham; public-launch gate only. No owner row marked done.

Screenshots awaiting Gautham: prior M5.1 desktop and phone race screenshots remain listed in STATUS; M5.3 has no look change. Pixel-regression and phone correctness captures here are evidence, not new design proposals.
Files reorganized: ArenaApp.tsx logic → sceneCore.ts; JSX → ArenaSceneView.tsx; three new thin shell files. No source file or evidence removed. Full M5.2 moves/cache list remains in ../agent-overhead/MOVES.md.
ADRs / plan changes: no new ADR or decision; ADR 0008 and approved E1–E8/phone waiver remain.
Deviations: none. Operational bundle correction described above; no behaviour change.
Ideas parked: none. Stop condition hit: none. Questions: none blocking.
Next according to README: M5.4 Night Shift tokens, fonts/icons with licence/source/checksum, colour-blind checks and real reference screenshots; add the phone connection question once, continue without waiting.
