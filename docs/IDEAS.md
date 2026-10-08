# Ideas — parked, never implemented mid-milestone

One line per idea (README §0, change control), in the form:

`date | idea | gap it closes | earliest milestone`

2026-10-08 | Live view: stop logging browser console errors when no local Stack is running and the remote endpoint is offline (probe quietly, then show "offline") | "no console errors" holds for every view except Live (docs/v2/BASELINE.md) | M1 — **moved into M0 (fix A.2, 2026-10-08) and done**; see the STATUS.md plan-change log
2026-10-08 | A phone-friendly `?perf` overlay that prints click→first-frame on screen, so phone baselines need no remote DevTools | phone measurement needs a USB cable today (docs/v2/PHONE_BASELINE.md) | M1
2026-10-08 | Explain why warm edits measured 1,265–1,686 ms against Lab 1.1's 1,158–1,172 ms (Chromium vs Firefox, harness, machine) | an unexplained baseline difference | M1
2026-10-08 | Cold-start measurement against a fixed, recorded network profile (throttled) instead of the live CDN path, which ranged 3.9–39.7 s | cold start is not comparable run to run | M1
2026-10-08 | Rename the published `live-v1.0` release title ("the real robot in the browser") — owner action, releases are not edited by agents | release title contradicts README correction 3 | M0 merge (owner) — **done in M0 fix A.4 (2026-10-08) under a one-off owner permission**
2026-10-08 | Replace the remaining "real stack" / "real run" / "real mission" / "Replay — recorded real run" wording (consistent with README correction 1, but easy to misread as hardware) with evidence-class badges (STACK, MODEL) | M0.6 fixed only "real robot"; the shorthand "real" remains in v1 views and generated captions | M2
