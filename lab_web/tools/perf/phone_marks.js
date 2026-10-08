// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
//
// M0.3 phone baseline: paste this whole file into the REMOTE DevTools
// console of the phone's tab (docs/v2/PHONE_BASELINE.md), BEFORE the first
// edit, with the page opened with `?perf`. It logs each edit's
// click -> first-frame time from the page's own marks (src/ui/perf.ts),
// the same quantity tools/perf/baseline.mjs measures on the laptop.
// Nothing is sent anywhere. Read the list back with `window.__m0phone`.
(() => {
  const p = window.__cocoLabPerf;
  if (!p) return 'No perf marks: reload the page with ?perf in the URL.';
  const out = window.__m0phone || [];
  window.__m0phone = out;
  let last = null;
  setInterval(() => {
    const m = p.marks;
    const t = m['edit-first-frame'];
    if (t && m['edit-click'] && t > m['edit-click'] && t !== last) {
      last = t;
      out.push(Math.round(t - m['edit-click']));
      console.log(`edit ${out.length}: ${out[out.length - 1]} ms${out.length === 1 ? ' (COLD)' : ' (warm)'}`);
    }
  }, 100);
  return 'Recording. Paint one cell at a time; wait for "Done" before the next.';
})();
