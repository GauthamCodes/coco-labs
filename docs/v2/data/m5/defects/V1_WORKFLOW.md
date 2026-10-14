# Frozen v1 reproducibility check — disabled, M5.1

The archived GitHub job log (`../setup/v1-job-log.txt`, run 38238187853)
shows the source build and checksum-verified pinned archive fetch passed,
but comparison failed beyond created_utc in generated/catalog.json,
the built wheel and index.html. The source archive is therefore not
reproducible under the current evolving Python wheel toolchain/CI build
metadata. A source rebuild succeeding is not proof of matching the archive.

M5 permits documenting and disabling this workflow. The job is explicitly
disabled rather than reporting success or weakening comparison. Its full
recipe is kept for investigation. The pinned v1-site branch, deployment
fetch and strict archive checksum verification remain active and unchanged.
No tag, evidence or public URL is removed. Re-enabling requires pinning the
original wheel/build metadata toolchain and showing a strict comparison
passes; no archive content may be replaced merely to make this check green.
