# Preliminary M5.1 audit (no fix yet)

`link-corpus.json` is a preliminary inventory of decoded Play/run link occurrences in committed Markdown and JSON under `docs/` and `lab_web/test/` at source `6c286b7`. It includes repeated occurrences, not unique links. For each `?view=arena|play` query, the audit parsed `z`, `s` or `run`, base64url-decoded it, inflated `z`, and accepted JSON version 1 with a level or chain hash. It measured encoded length, JSON byte length, input count, input ticks and first tick; the `from` fields identify the committed source for each peak. The recorded margin of 2 is a candidate for further assessment, not an implemented limit. This audit does not cover every future legitimate link or validate every challenge's semantics.

The reproducibility workflow was inspected read-only through GitHub:
`gh run view 38238187853 --json jobs,conclusion` and
`gh api repos/GauthamCodes/coco-labs/actions/jobs/114773957841/logs`.
The archived CI log is `../setup/v1-job-log.txt`. Build and pinned-archive fetch succeeded; comparison failed beyond the allowed created_utc differences in generated/catalog.json, the coco_lab wheel and index.html. This remains an unfixed M5.1 defect; no workflow has been disabled or public URL changed.

No product source, hash, golden trace or recording changed during this audit.
