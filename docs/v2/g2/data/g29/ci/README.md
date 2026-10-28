# G2.9 — the Lab workflow's update-isolation failure (CI)

Every failed "lab_web in Chromium, Firefox and WebKit" run on this branch since G2 began (2fafce1 … 07fac0b;
5 checked, all the same) failed in `lab_web/tools/update_isolation_check.mjs`: `page.waitForFunction` timed
out waiting for the new worker (build B) to report its version. Runs of the same code also passed
(13944de, e869448), so it was intermittent; main and G1's runs passed.

**Not slowness:** raising that wait from 120 s to 300 s (07fac0b) still timed out in CI.

**Reproduced on the laptop on one CPU core** (`taskset -c 0`; [`update_isolation_hang_one_core.log`](update_isolation_hang_one_core.log),
the worker's states from Chrome's DevTools protocol): B installed at 5.0 s and was activated at 6.1 s, the
old worker went redundant at 5.0 s; the check still timed out. Its wait asked
`navigator.serviceWorker.controller` for its version and awaited the reply with no limit; a poll whose message
reached the old worker as it stopped got no reply, so that one poll never ended and Playwright never polled
again, however long the timeout.

**Fix (the check only; the service worker is unchanged):** a poll with no reply in 1 s counts as "not yet".
On one core: 3 of 3 passed ([`update_isolation_fixed_one_core_*.log`](.)). The wait is 120 s again.
