# Deprecations — v1 components that v2 replaces or merges (M0.8)

From the master plan's component verdicts ([`README.md`](../../README.md)
§4). Each entry is **deprecated, not removed**.

> **The rule: every deprecated component keeps working until the milestone
> that replaces it has shipped its replacement.** Nothing below is deleted
> in M0. A current public view (`?view=plan`, `live`, `localise`, `map`,
> `search`, `move`) is retired only when its content has migrated, and its
> release tag (`lab1-v1.0` … `lab5-v1.0`, `live-v1.0`) and
> `coco-lab-v1-final` stay forever (README §3, integrity rule 3). Old
> recordings stay playable through converters (README §3 invariant 5).

## Replace

| Component (v1) | Where it lives today | Replaced by | Milestone | Stays working until |
|---|---|---|---|---|
| **Canvas 2D rendering** | `lab_web/src/render/{draw,layers,overlays,palette}.ts`, `ui/MapView.tsx`, `live/mapdraw.ts`, `ui/loc/LocCanvas.tsx`, `ui/map/MapCanvas.tsx` (and the SVG arenas in `ui/search/SearchLab.tsx`, `ui/move/shared.tsx`) | One Three.js / WebGL 2 renderer: orthographic 2.5D, instancing, data-texture grids, ID picking, one visual design system (README §5.3) | **M1** (M1.6) | Each view's own migration; the old views stay live until the end of M2 |
| **Per-lab bundle and trace formats** | `coco_lab.bundle` 1.0/1.1 + `trace` + `map`; `loc_bundle`/`loc_trace`; `slam_bundle`/`slam_trace`; `search_bundle`/`search_trace`; `replan_bundle`; `drive_bundle` (inventory: [`BASELINE.md`](BASELINE.md) §4; specs `docs/labs/*_FORMAT.md`, `TRACE_SCHEMA.md`) | One envelope (manifest with `run_id`, spec, tier, evidence class, SHAs) plus typed event families `coco.<family>.<name>.v<major>` in protobuf, stored as MCAP (README §5.2), in a new `coco_schemas` package | **M1–M2** (M1.1 envelope + Lab 1 families; M1.9 Lab 1 converters; M2: every old bundle converts and replays) | Converters exist for that format; the v1 decoders in `lab_web/src/{bundle,loc,map,search,move}/decode.ts` keep reading v1 bundles until then |
| **Live through Tailscale Funnel** (public) | `lab_web/src/ui/LiveView.tsx`, `live/*`, `site.config.ts` `LIVE_REMOTE`, `docs/live/` | Interactive cloud Stack sessions behind a gateway (README §5.4, M5 gate) | **M5** (gated: cost per slot-hour fits budget G4 AND demand shown) | M5 ships; then the public Tailscale Live tab is retired. Renamed **now** to "Live Stack (simulated)" (M0.6) and kept as Gautham's private bench |

## Merge

| Component (v1) | Where it lives today | Merged into | Milestone | Stays working until |
|---|---|---|---|---|
| **Six separate lab views** (Plan, Localise, Map, Search, Move, Live) | `lab_web/src/ui/App.tsx` view switch; `ui/{MapView,Player,Exhibit,LiveView}.tsx`, `ui/{loc,map,search,move}/` | One Arena app with lenses, a timeline and four modes (Learn, Play, Sandbox, Case Files) (README §1, §5.2) | **M1** (Plan content, M1.9: "The old Lab 1 view stays live") → **end of M2** (README §7 M2 exit: "The old per-lab views are retired; their release tags remain") | End of M2, view by view as content migrates |
| **Races and comparisons** | `lab_web/src/ui/Race.tsx`, `lab/race.ts`, the Localise/Map/Move race tables | Sandbox split-compare | README §4 gives no milestone for the whole merge; **M1** (M1.8 "planner choice, side-by-side compare") covers planner races | The owning view's retirement (end of M2 at the latest) |
| **Real-run replays, the A\* myth exhibit, Run 15, the Nav2 overlay** | `ui/Exhibit.tsx`, `ui/TrackingPlot.tsx`, the Replay tabs of Labs 2–5, `ui/move/` Run 15 | Case Files, converted through a ROS-to-event adapter in `coco_lab_ros` (README §7 M3) | **M3** | M3 ships Case Files (Lab 1's three real-run replays already play in the new viewer at M1.9) |
| **Old roadmap theme "Estimate"** | `docs/archive/v1/ROADMAP.md` §5 "Later labs" (never built) | The Localise lens | — (a plan theme, no code) | n/a |

## Kept (for contrast — not deprecated)

The React + Vite + TypeScript shell; `coco_lab` (the reference
implementation, redesigned to emit events, M1); Pyodide in a Web Worker;
the Sketch 2D model (becomes the deterministic Arena model, M1); GitHub
Pages; `coco.v1` (extended additively, M5); `platform_server` (redesigned
as the cloud gateway, M4–M5); the Docker image; the arbiter, latched STOP,
caps and kill switch; `coco_lab_ros` (extended, M3); predict-then-reveal,
paint-and-recompute and the map challenge; share links (redesigned as
spec-hash + input-log links). Robot-stack packages are **frozen**, not
deprecated (`FROZEN.md` in each; README §4, G3).
