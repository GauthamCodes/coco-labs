// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.10: soak3d's long-task observer, proven able to see one (a check whose success is "we saw
 * nothing" must first show it can see something): the same observer on the same page, then a
 * 120 ms busy loop on the main thread, in a real page task (setTimeout).
 *
 *   node tools/perf/longtask_selfcheck.mjs OUT.json
 *
 * Measured: the loop run directly in page.evaluate (a DevTools evaluation) is NOT reported as a
 * long task, so the self-check would read false; in setTimeout it is (120 ms). The page's own work
 * (frames, input handlers, worker messages) runs as page tasks, which the observer reports.
 */
import { writeFileSync } from 'node:fs';
import { chromium } from 'playwright';
const b = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const p = await b.newPage({ viewport: { width: 1400, height: 900 } });
await p.goto(`${process.argv[3] ?? 'http://127.0.0.1:4244/coco-labs/'}?view=arena&world=v2&camera=follow`);
await p.waitForFunction(() => !!window.__cocoPerf?.marks?.world3d_ready && !!window.__cocoPerf?.marks?.arena_ready, null, { timeout: 240000 });
await p.evaluate(() => {
  window.__lt = [];
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push(e.duration); }).observe({ type: 'longtask', buffered: false });
});
await p.waitForTimeout(3000);
const before = await p.evaluate(() => window.__lt.length);
await p.evaluate(() => { setTimeout(() => { const t = performance.now(); while (performance.now() - t < 120) { /* block */ } }, 0); });
await p.waitForTimeout(1000);
const after = await p.evaluate(() => window.__lt.slice());
const out = { observer_sees_a_long_task: after.length > before, before, recorded_ms: after };
writeFileSync(process.argv[2], JSON.stringify(out, null, 1) + '\n');
console.log(JSON.stringify(out));
await b.close();
