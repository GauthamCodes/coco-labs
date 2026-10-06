# Search bundle format 1.0 (Lab 4)

Normative. The reference implementation is `coco_lab/coco_lab/searchbundle.py`;
`coco_lab/test/test_searchbundle.py::test_the_format_document_matches_the_code`
pins this document to it. The TypeScript reader is
`lab_web/src/search/decode.ts`, pinned to the Python writer by golden files
(`coco_lab/test/fixtures/search_bundles/`, `lab_web/test/searchdecode.test.ts`).

It follows bundle format v1's rules exactly (`coco_lab.bundle`): a directory
holding `manifest.json` and `arrays.bin` (or `arrays.bin.gz`, gzip mtime 0);
canonical JSON; little-endian arrays at contiguous offsets; `content_hash` =
SHA-256 over the canonical manifest (without `content_hash`, `encoding` and
`provenance.created_utc`), a newline, and the uncompressed arrays; every size
bounded before allocation; refused, never repaired.

## Manifest

| key | meaning |
|---|---|
| `schema` | `coco_lab.search_bundle` |
| `version` | `1.0` (a reader refuses another MAJOR) |
| `provenance` | bundle v1 provenance. `source_kind` `sketch`, or `recorded-run` with `rosbag` (below) |
| `problem` | `regionsearch.SearchProblem.to_dict()`: `regions` (`id`, `label`, `approach`, `platform`, `survey_pose`, `exit`, `survey_cost`), `start`, `start_xy`, `travel` (metres, `travel[location][region]`, location = `start` or a region id), `detection` (one d per region), `prior`, `meta` |
| `runs` | 1 to `MAX_RUNS` = 32 entries, each `{id, kind, header, summary, n_events}`; a `recorded` run adds `timeline`, `record`, `evaluator` |
| `arrays` | the array table |
| `encoding` | `{byte_order: little, compression: none or gzip}` |
| `content_hash` | `sha256:<hex>` |

One problem per bundle: every run in it searched the same regions with the
same costs, detection and prior (rule 6).

## Runs

`kind` is `sketch` (`regionsearch.run_search`: a seed and a placed truth) or
`recorded` (`regionsearch.replay_search`: a real mission's looks). `header` is
the trace header (`schema` `coco_lab.search_trace`, `version` `1.0`, `policy`,
`given_order`, and for a sketch `seed`, `max_surveys`, `passes`,
`true_detection`). `summary`: `status` (`discovered`, `exhausted` or
`stopped`), `order`, `surveys`, `discovered`, `discovered_at`, `cost`
(metres driven, derived), `truth` (a sketch's placement; `null` for a
recording), `model_contradicted`, and `plan` — the policy's whole one-pass
order before any look, its expected cost and P(find).

A `recorded` run's `timeline` is `[[t, state, reason], ...]` — the mission's
FSM in simulator seconds. `record` names the run (commit, episode, colour,
order given, outcome, lift, home error, relocalisations, recoveries, runner
checks, bag hash, every look). `evaluator` holds where the target REALLY stood,
from the episode manifest: display data for the truth/belief toggle, never
read by replay.

For a multi-run recorded bundle, `provenance.rosbag.sha256` is the SHA-256 of
the runs' bag hashes, sorted and joined by newlines; each run's `record`
carries its own. `sim_time_start` is 0 and `sim_time_end` the longest run's
simulator seconds from its recorder's start.

## Arrays (per run, in this order)

| name | dtype | shape |
|---|---|---|
| `run.<id>.kind` | i32 | n_events: index into `select, survey, mark, discover, exhausted, stopped` |
| `run.<id>.region` | i32 | n_events: region index, -1 if none |
| `run.<id>.outcome` | i32 | n_events: 1 found, 0 miss, -1 not a look |
| `run.<id>.cost` | f64 | n_events: metres driven by then (never decreasing) |
| `run.<id>.belief` | f64 | n_events x n_regions: the belief AFTER the event (each row sums to 1) |
| `run.<id>.candidates` | f64 | n_events x n_regions: at a `select`, the expected cost of surveying each region next and the rest optimally; NaN elsewhere |
| `run.<id>.t` | f64 | n_events, recorded runs only: simulator seconds (NaN if not known) |

## Replay

`searchbundle.replay_check` recomputes every run with this coco_lab — a
sketch from its seed and truth, a recording from its looks alone, the policy
choosing every region again — and refuses unless the arrays come out byte for
byte and the summaries match.
