# M0.2 — v1 frozen (checked 2026-10-08)

## Tag

`coco-lab-v1-final`, annotated, message "COCO Lab v1 final: Labs 1–5 +
Live, before v2", on `35711693d11da99218fa85050db60c6e10462bd2` — coco-labs
`main` fast-forwarded to `lab5` (see `START_STATE.md`).

## The six releases (`gh release list` / `gh release view`, raw output in `releases.txt`)

| release | published (UTC) | draft | asset(s) |
|---|---|---|---|
| `lab1-v1.0` | 2026-10-01 06:06:30 | no | `coco_lab1_demo.mp4`, 2,005,151 B |
| `live-v1.0` | 2026-10-04 18:17:00 | no | **none** — by design: `docs/releases/live-v1.0.md` §Video says no Phase 2 video exists |
| `lab2-v1.0` | 2026-10-04 18:17:02 | no | `coco_lab2_demo.mp4`, 3,399,232 B |
| `lab3-v1.0` | 2026-10-06 09:38:28 | no | `coco_lab3_demo.mp4`, 5,268,119 B |
| `lab4-v1.0` | 2026-10-07 10:16:04 | no | `coco_lab4_demo.mp4`, 2,505,787 B |
| `lab5-v1.0` | 2026-10-08 05:11:35 | no | `coco_lab5_demo.mp4`, 3,615,891 B (Latest) |

All six exist and are published. The asset sizes equal the sizes
`docs/RESULTS.md` records for the videos it lists (Lab 1 2,005,151 B,
Lab 2 3,399,232 B, Lab 3 5,268,119 B, Lab 5 3,615,891 B).

**Not changed, reported:** the `live-v1.0` release TITLE reads "COCO Live —
the real robot in the browser". The plan's correction 3 says Live drives
the simulated stack and must not imply hardware. Releases are not edited
in M0 (owner's rule); the title is listed as a question for the owner.

## Recordings cited by checksum in `docs/RESULTS.md`

`docs/RESULTS.md` cites three external recordings by full SHA-256 (the
Lab 1C bags, "Evidence per run", hash definition
`coco_lab_ros.export.dir_sha256`). Recomputed read-only by
`check_recordings.py` (a copy of that definition), raw output
`recordings.json`:

| recording | cited SHA-256 | size | resolves |
|---|---|---|---|
| `~/coco_lab_runs/lab1c/run_astar/bag` | `13bc214d…96c4f` | 8,127,558 B | **yes** (hash and size equal) |
| `~/coco_lab_runs/lab1c/run_dijkstra/bag` | `498253a1…771dc` | 8,402,694 B | **yes** |
| `~/coco_lab_runs/lab1c/run_greedy/bag` | `82b76311…47b7b` | 6,891,474 B | **yes** |

3 of 3 resolve; none missing. Every other checksum in `docs/RESULTS.md` is
of a committed file (bundles, costmap snapshots under `docs/data/`,
`nav2_params.yaml`, path files), a site build tree, or a release video
(sizes above), not of a recording in `~/coco_lab_runs/`.
