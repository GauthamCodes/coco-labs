# R1.6 Exports, notebook and Datasets

Evidence class: MODEL / TESTED.

## Exports

Every experiment exports one zip (`lab_web/src/workbench/exports.ts`): `results.csv` (one row per run, failures
and timeouts included, every metric, the run's chain), `summary.json`, `spec.json`, `runs.jsonl` and
`manifest.json` (experiment id, spec sha256, digest, model and hash versions, world sha256, the checksum and size
of every file, the host and conditions, and the note that `compute_ms` is wall time on that host). Every file is
made by `coco_lab.experiments.export` in a worker — the same code `coco experiment run` uses — and records that
crossed JavaScript are normalised (integral floats as ints) so the bytes are the same on every host.

**With traces**: each run in the Arena (control, localisation) is re-run tick by tick into its own MCAP file
(JSON messages on `/coco/experiment/tick`: truth, belief, v, w, contact, state hash; schema
`coco.experiment.trace.v1`; metadata `evidence: MODEL`), and every re-run's hash chain is checked against the
run's before anything is saved; a full task's run adds its game record (replayable by `coco_lab.games.play`
and Play). A search has no ticks, so planning exports have no traces.

[`export_check.json`](export_check.json) (`lab_web/tools/r1/export_check.mjs`, Chromium; 2 controllers × 2 pairs):

| Check | Result |
| --- | --- |
| the zip holds the export set | results.csv, summary.json, spec.json, runs.jsonl, manifest.json + 4 MCAP traces |
| manifest checksums match the files | yes |
| one valid MCAP per run (`@mcap/core` reader), one message per tick | 4 files, 711 messages = the runs' ticks |
| `results.csv` and `summary.json` = `coco experiment run` of the same spec (wall time removed) | byte-identical |
| digest = native | `c8420b1e3d1c4425…` both |

## Notebook

[`docs/v2/r1/notebooks/analyse_experiment.ipynb`](../../notebooks/analyse_experiment.ipynb)
(`tools/r1/make_notebook.py`; executed once with nbclient in `~/coco_labs_ws/r1_nb_venv`: pandas 2.2.3,
matplotlib 3.9.2; outputs committed). On the committed depot-nav-100 planning reference (600 runs): every
file's sha256 matches the manifest; **the summary recomputed from results.csv matches summary.json**
(N and successes exactly; Wilson bounds, medians and quartiles to a largest relative difference of
2.0e-16 — pandas' quantile formula rounds differently in the last bit); success, box-plot, scatter and paired
tables drawn. An "Open in Colab" link (and the notebook's own badge) points at the main branch: live once R1
is merged; in Colab the notebook fetches the same reference files from the repository.

## Datasets tab

[`docs/v2/r1/datasets/index.json`](../../datasets/index.json) (`tools/r1/build_datasets.py`, kept current by
`lab_web/tools/test_r1_generated.py`): 11 datasets, every file with sha256, size and evidence class —
the 8 COCO-Bench v0 reference results (MODEL) and 3 paired model-vs-Gazebo sets that exist: Fetch by colour's
four rounds (model rounds + STACK ghosts), Fetch Rush rules 5 phone rounds 1/2/3/6 (model rounds + STACK
ghosts), Lab 5's 54 Gazebo runs and M2.5's model re-runs — each with what is and is not comparable.
Audit: [`a11y/a11y.json`](a11y/a11y.json) passes (it first failed on horizontal scroll: long digests in
narrow cards; fixed by wrapping and wider cards).
