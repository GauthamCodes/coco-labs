# R2.2 · The sandboxed worker — TESTED (real browsers, laptop)

Code: `lab_web/src/studio/sandbox.worker.ts` (boot, lockdown, runs), `lockdown.ts` (what is taken away, the memory
ceiling, the fixed probes), `sandbox_glue.py` (the Python side: heartbeats, drawing chunks, strict JSON),
`sandbox.ts` (the page side: `blob:` bootstrap so the worker inherits the page's CSP, message validation, the
watchdog), `index.html` (`worker-src 'self' blob:`). Threat model: [ADR 0012](../../../adr/0012-running-strangers-code.md).

## The escape tests — every one must fail safely

`lab_web/tools/r2/escape_check.mjs SITE OUT --browser B`: the real Algorithm Studio, each hostile file uploaded and run
as a visitor would; the page must stay up, no request may leave the site, and the starter planner and controller must
still run afterwards. Results: [Chromium](escape_chromium.json), [Firefox](escape_firefox.json),
[WebKit](escape_webkit.json) — **PASS in all three** (2026-11-04/05, the built site served locally).

| Prompt category | Attempt | Outcome (all three browsers) |
| --- | --- | --- |
| network calls | `import js; js.fetch(...)`; `from pyodide.http import pyfetch`; `import urllib.request` | refused by the guard |
| import js | `import js`; `import pyodide.ffi`; `().__class__.__base__.__subclasses__()`; `__import__('js')`; a generator's `gi_frame.f_globals`; `getattr(ctx, '__class__')` | refused by the guard (the last: `AttributeError` at run time, status `error`) |
| DOM access | `document.title = ...`; `js.document.body.innerHTML = ...`; `open('/tmp/x', 'w')` | `NameError` (status `error`) or refused by the guard |
| infinite loops | `while True: pass` in `control()` | **stopped by the time limit** after 5 s (the watchdog terminated the worker; the next run booted a fresh one) |
| memory blow-ups | `bytearray(1.5 GiB)`; `[0] * 400 Mi`; a list growing by 64 MiB | `MemoryError` at the WebAssembly memory ceiling (boot + 1 GiB; `Memory.prototype.grow` refuses), status `error`, the worker restarted |
| huge outputs | 300,000 `print`s; 400,000 `ctx.emit`s; a 250,000-pose path | the console keeps 64 KB and says how much it cut; events past the drawing cap are counted and not drawn (in Firefox the 30 s planner limit stopped this one first — also a safe end); the path is refused (`invalid_output`, at most 200,000 poses) |

**The lockdown's own probes** (the worker's fixed checks, no user code; shown to everyone in the Studio under "What
the sandbox blocks"): **68 checked, 0 reachable** in all three browsers — `fetch`, `XMLHttpRequest`, `WebSocket`,
`WebTransport`, `EventSource`, `importScripts`, `Worker`, `SharedWorker`, `BroadcastChannel`, `MessageChannel`,
`indexedDB`, `caches`, `Notification`, `RTCPeerConnection`, file-system handles, `navigator.storage/locks/
serviceWorker/usb/serial/hid/bluetooth/sendBeacon`, `document`, `window`, `localStorage`, `sessionStorage`, … all
blocked; `eval` and `Function` blocked by the inherited CSP (`EvalError`); `import()` of a remote module and of a
`data:` URL blocked; Python `import js` / `import pyodide_js` blocked; the guard refuses `import js`,
`pyodide.ffi`, `__class__`, `sys`, `open`.

Unit tests: `lab_web/test/r2_studio.test.ts` (the lockdown on a fake global — deleted, pinned, probed; the memory cap;
the watchdog with fake timers — a silent call ended at the family limit and a fresh worker booted, beats keeping a run
alive, the memory ceiling, malformed messages ignored).

**Residual risk, as ADR 0012 states it:** a defeat of both the guard and the lockdown could still reach what the
page's CSP allows (the site, the pinned Pyodide CDN, loopback ports). Never observed; listed so a sandboxed iframe with
a stricter policy can remove it.
