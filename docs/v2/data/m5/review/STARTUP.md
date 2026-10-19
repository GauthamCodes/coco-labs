# M5 review startup changes — 2026-10-19

Review source: fe9d544; owner decisions are recorded in docs/STATUS.md.
The old TitleScreen passed warmModel directly to the first-render onReady
callback. WorldStage invoked it in the rendering callback before that frame
was presented. There was no explicit idle-or-first-input gate.

The review waits for readiness, yields a frame, and starts warm-up at idle
(or the first key/pointer input). Listeners and pending callbacks are removed
on navigation. warmModel adds same-origin fetch preloads for
pyodide.asm.wasm and python_stdlib.zip immediately before worker creation.
No interpreter preload occurs in index.html or before title readiness.

Streaming compilation was already the pinned Pyodide loader's default:
streaming-proof.txt records its checksum and a targeted instantiateStreaming
excerpt. The static server serves application/wasm. No second interpreter
loader or private Pyodide API was introduced.

Laptop at review start: balanced, ACAD/online=0. Functional checks are allowed;
performance acceptance measurements wait for balanced/AC. If AC stays absent,
three-run remeasurement remains pending rather than substituting battery data
or the preceding candidate's timings. Real phone is absent in adb.txt.

Source checksums are in source-snapshot.txt; browser title ordering and
requests are recorded by tools/perf/m5_review.mjs. Historical measurements
remain intact under ../close/startup-immediate/.
