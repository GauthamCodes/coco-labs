# M5.9 Static caching and optional aggregate counter

Build-time SHA-256 allowlist; scoped service worker precaches shell, hashed JS/CSS,
self-hosted Pyodide/stdlib/wheel/model packs, 3D assets, original icons and static
indexes. Static files are cache-first under content-hash keys. Navigation is
network-first on the canonical index; query-bearing visitor URLs are never cached.
Activation clears only old caches for this app scope. Fetched bytes are checked
against the manifest before storing. A new index bypasses old unversioned cache
entries while the new worker installs, preventing stale model/manifest pairs.

Registration is optional, delayed on first visit to protect initial scene loading,
and never blocks boot. A blocked/unavailable worker leaves the product usable.
Original SVG app artwork is exported to PNG install icons, with source/licence and
checksums in DESIGN_ASSETS.json. The app manifest opens landscape/fullscreen.

`VISIT_COUNTER_ID` is empty. It may contain one owner-provided public HTTPS
aggregate increment endpoint. No account/service was created, no secrets shipped,
and no provider with visitor fingerprinting is endorsed. Empty POST, no cookies,
referrer, page/query, client identifier or device properties; response ignored.
See COUNTER.md for the endpoint contract and activation instructions.

## Checks

`browser-first/checks.json`: actual browser hard reload sees changed index/static
bytes, old caches removed, offline title works, static allowlist contains no personal
query/sentinel, preferences unchanged. Title/Play/Compare/Research work with service
workers blocked. Zero console errors and zero third-party requests with blank config.

Warm start was MEASURED on balanced/AC with NVIDIA 580.178.04, concurrent diagnostic
work, using emulated 4G. Desktop: 7717.699951171875 ms; emulated Nothing Phone (1)
landscape: 5026.800048828125 ms; portrait: 6248.60009765625 ms. These exceed the 3 s
budget; this criterion is NOT MET by this run. Full marks/renderer/conditions are
retained. Final isolated measurements and any justified optimization belong to M5.11.
Emulated values never satisfy the real Phone row.

Typecheck/build and static dist check pass. New counter/cache unit checks pass.
The first web run had 490 passes and a stale generated asset-document checksum;
regenerating ASSETS.md after adding original PNG icon checksums fixes that one
regression (assets-regression.txt). Full suite logs are retained alongside this
report; their final results are recorded in STATUS at checkpoint closure.

No evidence, URL, release, tag or branch was deleted; cache cleanup is limited to
browser static caches. Next: M5.10 draft launch material, then M5.11 acceptance
measurements and PR; never merge or publish a release.

Final package suites: 3569 passed (all twelve); tools 207 passed. Web 490 passes
plus the corrected asset-doc regression: 1 passed. Network-audit diagnostic confirms
controlled warm pages fetch only canonical index and service-worker update scripts,
not model/Pyodide assets. Cache hits alone do not meet the startup budget.
