# ADR 0012 — Running strangers' code: the threat model

Date: 2026-11-04. Scope R2 · Bring Your Own Algorithm (R2.1 design; R2.2, R2.6, R2.7 build it).

## Problem

R2 runs Python that anyone wrote: a link a student opens, a leaderboard pull request, a file
exported to ROS 2. COCO Lab has no accounts, servers or secrets, but a visitor's browser,
the repository's CI and a researcher's laptop are worth protecting.

## Assets and attackers

| Asset | Where | Attacker's aim |
| --- | --- | --- |
| The visitor's browser, network position, other tabs, local services (loopback) | the site | exfiltrate, scan or attack from the visitor's machine; mine; crash the tab |
| The visitor's stored data (prefs in localStorage; the service worker's caches) | the site | read, poison |
| The repository, its Actions secrets and token, the leaderboard's integrity | GitHub | push, steal a token, publish a fake result |
| The researcher's machine | `coco experiment run --algorithm`, the ROS 2 package | whatever the file can do |

Out of scope: a visitor who runs code they wrote themselves on their own machine (natively or
in ROS 2) — that is their machine and their code; the guard there is for portability and
honest measurement, not containment.

## Decision: defence in depth, with the boundary named per place

### 1. The guard, everywhere (`coco_lab.user_code`) — not a boundary on its own

Parse the file and refuse: imports outside the allow-list; attribute names starting with `_`
or naming frames, code or tracebacks (`gi_frame`, `f_globals`, `tb_frame`, ...); names
starting with `__` (but `__name__`); `async`/`await`; star imports. Run with a reduced
builtins table (no `open`, `exec`, `eval`, `compile`, `input`, `globals`, `vars`, `id`,
`memoryview`, `breakpoint`, `__import__` except the hook; `getattr` and friends refuse `_`
names) and an import hook that hands out **shims** holding only public names
(`math` — deterministic functions only, `random` — over `ctx.rng`, `heapq`, `collections`,
`itertools`, `functools`, `bisect`, `typing`, `dataclasses`, `coco_lab.api`). numpy is not
shipped by the site, so it is not allowed. `x ** y` is rewritten to an exact power.

CPython was never designed to contain hostile code; a guard like this (RestrictedPython's
kind) has been escaped before. It keeps honest code honest, makes results portable, and
makes an escape need a second, independent failure — the boundaries below.

### 2. The browser: a dedicated, locked-down worker (R2.2)

- User code runs **only** in its own Pyodide worker, never in the page or the Arena workers.
  Workers have no DOM.
- The worker is started from a `blob:` URL so it **inherits the page's CSP** (a worker loaded
  from a same-origin URL gets its CSP from response headers, which GitHub Pages cannot set):
  `script-src 'self' 'wasm-unsafe-eval' <pinned CDN>` — no `unsafe-eval`, so neither
  `eval` nor `Function` nor a dynamic `import()` of new code is possible from JavaScript.
- After Pyodide and `coco_lab` are loaded and **before user code**, the worker deletes or
  stubs, on the global object and its prototypes: `fetch`, `XMLHttpRequest`, `WebSocket`,
  `WebSocketStream`, `WebTransport`, `EventSource`, `importScripts`, `Worker`,
  `SharedWorker`, `BroadcastChannel`, `MessageChannel` (new ones), `indexedDB`, `caches`,
  `navigator.storage`, `navigator.locks`, `navigator.usb/serial/hid/bluetooth`,
  `Notification`, `RTCPeerConnection`, `requestFileSystem`; and removes `js`, `pyodide`,
  `pyodide.ffi`, `pyodide_js`, `_pyodide` from Python's `sys.modules` and its importers.
- **Limits:** a hard per-call time limit enforced from the page: the worker posts a heartbeat
  after every call, and a silence longer than the limit (default 5 s per call) terminates the
  worker and starts a fresh one. A memory ceiling: the WebAssembly memory is checked after
  every call (default 1 GiB above the boot size), and an allocation past WebAssembly's own
  maximum fails inside the call with `MemoryError`; both end the run and restart the worker.
  Console output is capped (64 KB per run), events per call (20,000 kept), the path
  (200,000 poses), the file (256 KB).
- The page treats every worker message as untrusted data: typed fields only, text rendered
  as text, never HTML.
- **Consent:** a link that carries code always opens it in the editor with an explicit
  "Run this code" button. Nothing runs automatically.

**Residual risk (stated, not hidden):** if both the guard and the lockdown were defeated,
code could still issue requests that the page's CSP allows: to the site itself, the pinned
Pyodide CDN and loopback ports (the Live tab's `ws://localhost:*`). Any web page can already
make such requests, so this is no worse than visiting an untrusted page; it is listed so a
future change (a sandboxed iframe with a stricter policy) can remove it.

### 3. CI: the leaderboard verifier (R2.6)

- The verifier workflow runs on **`pull_request`** (never `pull_request_target`), so a fork's
  code runs with a read-only token and **no secrets**; `permissions: contents: read`.
- The algorithm runs inside `docker run --network none --read-only --cpus 2 --memory 4g
  --pids-limit 256 --cap-drop ALL --security-opt no-new-privileges` with a job and a step
  timeout; the image is the pinned Python with `coco_lab` from the base branch (the PR's own
  copy of `coco_lab` is never used to judge it).
- The verifier only produces an **artifact** (results + report). A separate, trusted
  **`workflow_run`** workflow, which never checks out or executes PR code, reads that
  artifact as data, validates its schema, and labels the PR `verified` or comments the
  report. Nothing writes to the repository automatically: entries land when the owner merges.

### 4. ROS 2 (R2.7)

The generated package loads `algorithm.py` through the same guard. It runs on the
researcher's own machine as an ordinary node; it is not contained, and the README says so.
Its controller publishes into COCO's `cmd_vel_arbiter`, never to the wheels: STOP and the
safety chain still win (invariant 3).

### 5. Determinism (a fairness rule, enforced in every place)

User code is a pure function of its inputs plus `ctx.rng`: no clock, no `id()`, no system
randomness. Every user run is run twice and the two chains compared; a non-deterministic
algorithm is labelled "non-deterministic", can still be run, and cannot be submitted.
`PYTHONHASHSEED=0` wherever user code runs (string hashes, so set order, would otherwise
depend on the process).

## Held-out scenarios (R2.6, §1.5)

See the leaderboard section of R2_STATUS / CONTRIBUTING for the scheme and its stated limit:
a seed committed only in a workflow file is readable by anyone who reads the repository, so
"unpublished" here means "not in the suite files", not "secret".

## Consequences

- Each escape route has two independent stops in the browser and one hard boundary in CI.
- The escape tests (R2.2) are part of CI; a passing escape is a stop condition.
