// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Measurement hooks for Phase 1D-6 (headless-browser timings). Nothing is
 * sent anywhere: the numbers live on `window.__cocoLabPerf` for the local
 * harness to read, and only when the page was opened with `?perf`.
 */

interface PerfLog {
  frames: number[]; // draw time per frame, ms
  frameTimes: number[]; // performance.now() at each drawn frame
  marks: Record<string, number>;
}

declare global {
  interface Window {
    __cocoLabPerf?: PerfLog;
  }
}

const enabled = typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('perf');
if (enabled) window.__cocoLabPerf = { frames: [], frameTimes: [], marks: {} };

export function perfFrame(ms: number): void {
  const p = enabled ? window.__cocoLabPerf : undefined;
  if (!p) return;
  p.frames.push(ms);
  p.frameTimes.push(performance.now());
}

export function perfMark(name: string): void {
  const p = enabled ? window.__cocoLabPerf : undefined;
  if (p) p.marks[name] = performance.now();
}
