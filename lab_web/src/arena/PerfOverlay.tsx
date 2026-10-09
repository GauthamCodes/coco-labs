// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * `?perf`: the numbers a phone measurement needs, on screen (M1.5).
 * Times are milliseconds since navigation started, measured in this
 * browser; fps counts real animation frames over the last second.
 */

import { useEffect, useState } from 'react';

import { perf, type PerfSnapshot } from './perf';

const STAGES: [string, string][] = [
  ['worker_create', 'worker created'],
  ['pyodide_module', 'Pyodide module'],
  ['pyodide_ready', 'Pyodide ready'],
  ['coco_lab_ready', 'coco_lab ready'],
  ['arena_ready', 'Arena ready'],
  ['first_frame', 'first frame drawn'],
  ['attract_ready', 'recording ready (attract)'],
  ['first_computation_shown', 'first computation shown'],
];

export function PerfOverlay() {
  const [s, setS] = useState<PerfSnapshot>(() => perf.snapshot());
  useEffect(() => {
    let raf = 0;
    const loop = () => { perf.frame(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    const t = setInterval(() => setS(perf.snapshot()), 500);
    return () => { cancelAnimationFrame(raf); clearInterval(t); };
  }, []);
  const since = (at?: number | null) => (at ? `${Math.round(at - s.navStart)} ms` : '—');
  return (
    <aside className="perf-overlay" data-testid="perf-overlay" aria-label="Performance">
      <b>?perf</b>
      <dl>
        {STAGES.map(([k, label]) => (
          <div key={k}><dt>{label}</dt><dd data-testid={`perf-${k}`}>{since(s.marks[k])}</dd></div>
        ))}
        <div><dt>first plan events</dt><dd data-testid="perf-first-plan">{since(s.firstPlanBatchAt)}</dd></div>
        <div><dt>goal → frontier drawn</dt><dd data-testid="perf-goal-frontier">
          {s.goalToFrontierMs.length ? `${s.goalToFrontierMs[s.goalToFrontierMs.length - 1].toFixed(0)} ms (last of ${s.goalToFrontierMs.length})` : '—'}</dd></div>
        <div><dt>fps</dt><dd data-testid="perf-fps">{s.fps} (p95 frame {s.frameMsP95.toFixed(1)} ms)</dd></div>
        <div><dt>plan events</dt><dd data-testid="perf-events">{s.eventsReceived.toLocaleString()} ({s.eventsPerSecond.toLocaleString()}/s)</dd></div>
        <div><dt>step</dt><dd data-testid="perf-step">{s.stepMsMedian != null ? `${s.stepMsMedian.toFixed(1)} ms median, ${s.ticks} ticks` : '—'}</dd></div>
      </dl>
    </aside>
  );
}
