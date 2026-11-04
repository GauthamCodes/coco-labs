# R1.4 Shareable links and Verify

Evidence class: MODEL / TESTED.

## What was added

- `lab_web/src/workbench/links.ts`: **Copy link** puts the spec in `?view=workbench&exp=` (base64url JSON)
  while the link stays within 1,800 characters, otherwise deflated in the fragment `#expz=` (never sent to a
  server); both decode through M5's bounded decoder (`links/bounds.mjs` `boundedJson`: size limits, a
  bomb-safe inflate); `exp` joins the URL fields `urlFieldError` bounds. A finished experiment's link carries
  its digest `d=`; opening it rebuilds the spec, re-runs every run and says **"Reproduced exactly"** or
  **"DIFFERS"** (with both digests). The link is always shown in a field as well as copied.
- **Verify** re-runs a random 10% of the runs (at least one; `crypto.getRandomValues`) on the pool and
  checks each one's status, hash chain and counts against the records on the page.
- `lab_web/tools/r1/link_e2e.mjs` and a CI step (`lab-web-browsers`): build and run an experiment through the
  JSON editor in one browser context, copy its link, open it in a **fresh** context, require "Reproduced
  exactly", identical runs and summary tables, an identical digest and a passing Verify; `--long` forces the
  fragment form.

## Results ([`link_e2e_*.json`](.))

The experiment: A*, Dijkstra and weighted A* (weight 3) × 8 seeded Proving Ground pairs = 24 runs.

| Browser | Link | Fresh context | Tables | Verify | Digest |
| --- | --- | --- | --- | --- | --- |
| Chromium | `?exp=` (514 chars) | Reproduced exactly | identical | 2 of 2 match | `2554d51e9df9d757…` |
| Firefox | `?exp=` (514 chars) | Reproduced exactly | identical | 2 of 2 match | `2554d51e9df9d757…` |
| WebKit | `?exp=` (514 chars) | Reproduced exactly | identical | 2 of 2 match | `2554d51e9df9d757…` |
| Chromium, `--long` | `#expz=` (458 chars, deflated) | Reproduced exactly | identical | 2 of 2 match | `18003fd01a25c051…` (the spec has notes) |
| **CPython** (`coco experiment run`, [`native_e2e_spec/`](native_e2e_spec/)) | — | — | — | — | `2554d51e9df9d75706d0b1352bc4c68cb17862fb7107f87efb09c6ec11160839` |

The same spec gives the same digest in three browser engines and natively. The long spec's digest differs
because its notes are part of the spec, and every run's chain binds to the exact spec.

Found and fixed: WebKit refuses a page script's clipboard read (the first WebKit run failed at "copied the
link"); the page now shows the link in a field, which the test reads.

vitest: 626 tests, 82 files (adds `r1_links.test.ts`: short and fragment round-trips, malformed payloads,
wrong schema and bad digests refused).
