# M5 review startup changes — 2026-10-19

Review source: fe9d544; owner decisions are recorded in docs/STATUS.md.
The old TitleScreen passed warmModel directly to the first-render onReady
callback. WorldStage invoked it in the rendering callback before that frame
was presented. There was no explicit idle-or-first-input gate.

The review waits for readiness, yields a frame, and starts warm-up at idle
(or the first key/pointer input). Listeners and pending callbacks are removed
on navigation. Browsers without requestIdleCallback wait for first input.

The one-shot WASM/stdlib preload attempt caused duplicate downloads under the
no-cache startup protocol: each WASM and stdlib file was fetched twice, adding
4,384,106 bytes. Desktop live readiness was 13147.7 /13193.2 /13278.9 ms;
emulated phone was 13397.1 /13387.9 /13535.9 ms. Those harmful hints were
removed. Raw failed measurements remain in startup-preload-ac/checks.json.
No interpreter fetch is started before title readiness.

Streaming compilation was already the pinned Pyodide loader's default:
streaming-proof.txt records its checksum and a targeted instantiateStreaming
excerpt. The static server serves application/wasm. No second interpreter
loader or private Pyodide API was introduced.

Final measurements were taken balanced on AC, without another heavy job or robot
batch. The earlier battery/interrupted attempts remain retained and are excluded
from acceptance. Final no-hint measurements: startup-final-ac/checks.json.
Desktop live readiness: 9997.8 /9828.4 /9845.3 ms; emulated phone landscape:
10106.3 /10030.5 /9964.7 ms. The latter is the owner-accepted emulated near-miss,
not a real-phone pass. ADB still lists no phone.

Title-idle-final.json proves no worker before input when idle callbacks are
unavailable, title readiness before worker creation in both cases, and an actual
successful WebAssembly.instantiateStreaming call. Only one WASM and one stdlib
request occur in each final context. BUILD.json pins measured source SHA256s and
the final dist inventory; its git_head is the parent of the pending source fixes.
