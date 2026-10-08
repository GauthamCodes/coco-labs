# COCO Lab — roadmap

**The plan is [`README.md` §7](../README.md#7-roadmap)** (the master plan,
the authority for COCO Lab since 2026-10-08). Where the work stands:
[`docs/STATUS.md`](STATUS.md). This file holds only a pointer and the v1
history.

```
M0 Transition ─▶ M1 Glass-box Arena core ─▶ M2 Whole loop ─▶ M3 Play + Case Files (public v2 launch)
     ─▶ M4 Stack in the cloud ─▶ [gate] M5 Interactive Stack sessions ─▶ [gate] M6 Hardware bridge
```

> **Old references.** Any mention of "`docs/ROADMAP.md` §N", a ROADMAP line
> number, or "`docs/LAB_PHASES.md`" written before 2026-10-08 means the v1
> files, archived unchanged at
> [`docs/archive/v1/ROADMAP.md`](archive/v1/ROADMAP.md) and
> [`docs/archive/v1/LAB_PHASES.md`](archive/v1/LAB_PHASES.md). The v1
> README is [`docs/archive/v1/README_v1.md`](archive/v1/README_v1.md).

## v1 history (frozen at tag `coco-lab-v1-final` = `3571169`)

| Phase | Lab | Shipped | Release | Release target (`main`) | Write-up |
|---|---|---|---|---|---|
| 0 · Make the repo tell the truth | — | 2026-09-29 | — | — | `docs/archive/v1/ROADMAP.md` §6 |
| 1 · Plan | Lab 1 | 2026-09-30 (Lab 1.1: 2026-10-01) | `lab1-v1.0` (2026-10-01) | `main` at release | [`labs/LAB1_PLAN.md`](labs/LAB1_PLAN.md) |
| 2 · Live | — | 2026-10-04 | `live-v1.0` (2026-10-04) | `4530a8b` | [`live/LIVE.md`](live/LIVE.md) |
| 3 · Localise | Lab 2 | 2026-10-04 | `lab2-v1.0` (2026-10-04) | `4b675c1` | [`labs/LAB2_LOCALISE.md`](labs/LAB2_LOCALISE.md) |
| 4 · Map | Lab 3 | 2026-10-05 | `lab3-v1.0` (2026-10-06) | `a63a4c8` | [`labs/LAB3_MAP.md`](labs/LAB3_MAP.md) |
| 5 · Search | Lab 4 | 2026-10-07 | `lab4-v1.0` (2026-10-07) | `b554910` | [`labs/LAB4_SEARCH.md`](labs/LAB4_SEARCH.md) |
| 6 · Move | Lab 5 | 2026-10-07 | `lab5-v1.0` (2026-10-08) | `2b6f8ad` | [`labs/LAB5_MOVE.md`](labs/LAB5_MOVE.md) |

Release dates and targets: `gh release view` on 2026-10-08
([`v2/data/m0/releases.txt`](v2/data/m0/releases.txt)). Measured results:
[`docs/RESULTS.md`](RESULTS.md). The v1 baseline v2 is measured against:
[`docs/v2/BASELINE.md`](v2/BASELINE.md).

## What happened to the old roadmap's themes

| v1 theme (archived roadmap §5 "Later labs", §9 "Deferred") | Now |
|---|---|
| **Learn** (RL; when a tuned controller is enough) | **Deferred** — README §6: no RL lessons or policy training until the robot project shows where learning beats classical control. (README's "Learn" *mode* is guided missions, a different thing.) |
| **Estimate** (observability; friction non-identifiability) | **Merged into Localise** — README §4: "Old roadmap 'Estimate' → Merge into the Localise lens". |
| **Many Robots** (multi-agent pathfinding) | **Deferred** — README §6: multi-robot behaviour is a non-goal until further notice. |
| Global leaderboard | **Deferred** — until deterministic server-side score verification exists (README §6). |
| Full Isaac backend / Isaac inside COCO Lab | **Removed** — out of scope permanently (README §4, §6). |
| VLM task layer | **Removed** — out of scope permanently (README §4, §6). |
| M7 Phase 4 policy training / browser policy training | **Removed** — out of scope permanently (README §4). |
| Always-on hosted live robot; concurrent drivers | **Replaced** by cloud Stack sessions, M4–M5, gated (README §7). |
