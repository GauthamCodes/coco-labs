# Preliminary M5.1 audit (no fix yet)

`link-corpus.json` is a preliminary inventory of decoded Play/run link occurrences in committed Markdown and JSON under `docs/` and `lab_web/test/` at source `6c286b7`. It includes repeated occurrences, not unique links. For each `?view=arena|play` query, the audit parsed `z`, `s` or `run`, base64url-decoded it, inflated `z`, and accepted JSON version 1 with a level or chain hash. It measured encoded length, JSON byte length, input count, input ticks and first tick; the `from` fields identify the committed source for each peak. The recorded margin of 2 is a candidate for further assessment, not an implemented limit. This audit does not cover every future legitimate link or validate every challenge's semantics.

The reproducibility workflow was inspected read-only through GitHub:
`gh run view 38238187853 --json jobs,conclusion` and
`gh api repos/GauthamCodes/coco-labs/actions/jobs/114773957841/logs`.
The archived CI log is `../setup/v1-job-log.txt`. Build and pinned-archive fetch succeeded; comparison failed beyond the allowed created_utc differences in generated/catalog.json, the coco_lab wheel and index.html. This remains an unfixed M5.1 defect; no workflow has been disabled or public URL changed.

No product source, hash, golden trace or recording changed during this audit.


## Completed M5.1 validation

Use `link-corpus-v2.json` (not the preliminary audit) as the limits basis.
`committed-play-verified-final.json` combines the original current-layout
checks and the legacy-layout re-score; baseline probe shows no M5 hash change.
The all-engine v2 corpus and original v1 corpus checks passed. Case File
first-frame measurement passed 100/100 at <=2s with the actual robot mesh.
The final applied-click browser check is `browser-goal-applied/check.json`;
earlier inverse-only/immediate-read harness output is retained, superseded.
The immediate-read failure sampled the previous goal before the new worker
tick finished; the final hook waits for the applied input log.
Screenshots are in `../screens/defects/` relative to m5, not browser outputs.
Final suites: packages-verified.txt (3534), vitest-final.txt (456), tools.txt
(193), with typecheck-close.txt and focused-close.txt. No fixture was weakened.
