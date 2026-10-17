# Optional aggregate visit counter

`VISIT_COUNTER_ID` in `lab_web/site.config.ts` is empty. Counting is off. No account,
endpoint, key or counter has been created. The shipped app makes no counter request,
loads no analytics script, and computes no visitor identifier.

To enable it, Gautham sets that **one value** to his existing public counter's HTTPS
increment URL, with his counter ID in its path, then rebuilds. Example shape only:
`https://counter.example.org/increment/GAUTHAMS_COUNTER_ID` (not a working service).
The endpoint must accept an empty POST, increment one aggregate total, and permit
cross-origin requests without credentials. Its response is ignored. This counts
page loads, including reloads; it never claims unique visitors or deduplicates users.
The build adds only that configured origin to connect-src. Revert the value to `''`
to turn it off; no script/account removal is needed.

Choose an existing endpoint whose operator explicitly guarantees no IP/user-agent
fingerprinting, visitor/session IDs, cookies, per-user logs or personal-data retention.
Do not put a secret API token in this public setting. No page URL, query, referrer,
device properties or user input is sent. The network itself necessarily exposes an
IP address to the endpoint; its operator must discard it rather than track visitors.
The app sends credentials: omit, referrerPolicy: no-referrer, cache: no-store and
redirect: error. Failure is silent and does not affect COCO Lab.

No hosted provider is endorsed by this implementation. Reviewed on 2026-10-18:
[GoatCounter's privacy documentation](https://www.goatcounter.com/help/privacy)
describes IP/user-agent session grouping, which conflicts with this project's no
fingerprinting rule. [CounterAPI v2](https://docs.counterapi.dev/api/endpoints/v2/)
requires authentication; a private API token must never be shipped to visitors.
Neither service was configured or contacted to register a counter. Integration is
verified against a mock aggregate endpoint; activation belongs to Gautham.

The blank-config browser regression covers title, Play, Compare and Research, with
zero third-party requests. Live is an explicit connection to the simulated Stack,
not telemetry; its configured remote endpoint is unrelated to counting.
