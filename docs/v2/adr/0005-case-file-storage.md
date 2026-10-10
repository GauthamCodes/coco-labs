# ADR 0005 — Case File storage: zstd run files committed to the repository, lazy-loaded

- **Status:** accepted, 2026-10-10 (M3.2).
- **Evidence class of every number here:** MODEL (the conversion tooling),
  measured on the development laptop. The recordings themselves are STACK.
- **Evidence:** [`docs/v2/data/m3/m32/casefile_sizes.json`](../data/m3/m32/casefile_sizes.json).

## Context

M3.3 publishes every recorded full-stack run as a Case File: the Lab 4
searches, the Lab 5 drives, the SLAM tours, Run 15's reproduction, the A\*
myth, the Lab 2 kidnaps and robot_localization tour, and Lab 1's runs. The
constraints come from the M3 prompt (B.2, M3.2):

- **Raw bags stay where they are.** They live in `~/coco_lab_runs/`, about
  2.8 GB, and are never moved or deleted.
- **A Case File is a summary-detail event file.** Its manifest cites its
  source bag by checksum.
- **Budget:** about 20 MB per Case File and about 150 MB in total on the
  site, lazy-loaded.
- **If they don't fit in the repository within that budget, stop and ask.**
  The alternative is release assets, which only the owner creates.

The CI runners and the Pages build cannot see `~/coco_lab_runs`. So the
conversion runs here, once per recording, and its output must live
somewhere the build can reach.

## Measured

`coco_lab_ros.adapter` converted one recording of each kind at `summary`
detail, and `lab_web`'s `repackRun` repacked it as the site serves it (zstd
chunks plus index).

| Sample | Bag | Summary file | Served (zstd) |
|---|---|---|---|
| Lab 5, static room, MPPI 1 (the largest Lab 5 bag) | 13.4 MB | 535 KB | **337 KB** |
| Lab 5, crossing, DWB 1 | 13.3 MB | 393 KB | **189 KB** |
| Lab 4, A1 fixed red (log window: start to the first terminal state + 2 s) | 115.3 MB | 877 KB | **345 KB** |
| Lab 2, kidnap recovery K1 (233 s, scans) | 45.0 MB | 1.97 MB | **1.00 MB** |
| Lab 3, s1 tour (649 s, scans) | 83.3 MB | 2.83 MB | **1.89 MB** |
| Lab 1C, A\* run | 8.1 MB | 155 KB | **74 KB** |
| robot_localization replay, s1 | 13.1 MB | 930 KB | **581 KB** |

Counting each kind at its largest sample gives about **52 MB** for the
bag-backed Case Files:

| Kind | Case Files | Bytes |
|---|---|---|
| Lab 5 | 54 | 18.2 MB |
| Lab 2 kidnaps | 20 | 20.0 MB |
| Lab 4 | 16 | 5.5 MB |
| Lab 3 tours | 2 | 3.8 MB |
| robot_localization | 5 | 2.9 MB |
| Run 15's reproduction | 9 | 1.7 MB |
| Lab 1 | 3 | 0.2 MB |

The SLAM backends' maps and the A\* myth's committed data add little; M3.3
measures every Case File. The largest single file is about 2 MB, a tenth
of the per-file budget.

## Options

| | Where Case Files live | For | Against |
|---|---|---|---|
| **A. Committed to the repository** (chosen) | `lab_web/casefiles/<id>.mcap` (zstd, indexed) plus `index.json`, copied into the Pages artifact at build | It fits the budget about 3× over. Reviewable, versioned with the code that reads it. CI tests each file's manifest and citation. No outward action. | About 50–60 MB of binary in git history; a re-conversion adds another copy |
| B. Release assets | Attached to a GitHub release, downloaded at build | Not in git history | Only the owner creates releases; the B.5 stop exists for this |
| C. Built at deploy from the bags | — | — | The bags are not on the runners |

## Decision

**A.**

- **The files.** Case Files are the adapter's `summary`-detail output,
  repacked by `repackRun` with zstd (the same messages byte for byte),
  committed under **`lab_web/casefiles/`** with an `index.json`. The
  build copies them to `generated/casefiles/`.
- **Lazy loading.** The site fetches one Case File only when it is opened;
  the list fetches only `index.json`.
- **Every file is checked:**
  - **Citation.** The manifest cites every file of its source bag directory
    by sha256 and size (ADAPTER.md, "Citation").
  - **Cross-check, the B.5 check.** Where a committed manifest already
    names a bag's checksum, the Case File's must equal it, **by that lab's
    own definition**. A mismatch stops the conversion; it is not patched.

    | Lab | Committed field | What it hashes |
    |---|---|---|
    | Lab 4 | `docs/data/lab4/replay/p05_matrix/manifest.json` `record.bag_sha256` | The whole bag directory, `docs/data/p05_evidence.py` `_sha_dir`: each file's name, NUL, bytes, sorted |
    | Lab 5 | `docs/data/lab5/drive/*/manifest.json` `bag_sha256` | `bag_0.mcap` alone (`lab5_evidence.py`) |
    | Lab 1C | `docs/data/lab1c/runs.json` | `sha256` / `dir_sha256` (`coco_lab_ros.export`) |
    | Lab 3 | `docs/data/lab3/results.json` `source_bag_sha256` | Per file (`make_drive.py`) |

    Checked here, before the decision:
    - Lab 5 `crossing_DWB_1`: `bag_0.mcap` = `673d7f05…` = its manifest.
    - Lab 4 `A1_fixed_red`: `bag_0.mcap` alone is `538b4101…`, **not** the
      manifest's `a2945562…`, but the directory hash is `a2945562…`. That
      is the field's own definition, so it is a match.

    The Case File's manifest therefore cites every file's sha256, and the
    M3.3 cross-check computes each lab's own definition.
  - **Budget, enforced in CI.** A test refuses a Case File over 20 MB or a
    total over 150 MB.
  - **Reproducibility.** The conversion is deterministic; the adapter's
    tests pin it on fixtures. Its inputs are the bags here, so CI checks the
    committed files, not the conversion.
- **Re-converting** (a new adapter version) replaces the files in one
  reviewed commit. The old bytes stay in history, and the raw bags stay in
  `~/coco_lab_runs/`.

## Consequences

- The repository grows by roughly 50–60 MB once, measured and reported in
  M3.3. Nothing is moved out of `~/coco_lab_runs/`.
- A Case File's evidence class is STACK by its manifest. Its text cites the
  bag checksum and `docs/RESULTS.md`.
- If the set ever outgrows the budget (more recordings, `full` detail), the
  stop condition returns and the owner decides on release assets.
