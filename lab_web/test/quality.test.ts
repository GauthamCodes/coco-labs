// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** The 3D view's quality tiers (M4.4): measured, settled, hysteretic, overridable; and the fallback verdict. */

import { describe, expect, it } from 'vitest';

import { FALLBACK_WINDOWS, QualityController, SETTLE_MS, STALL_MS, UP_WINDOWS, WINDOW_MS, type QualityEvent } from '../src/arena/render/quality';

/** Feed `ms` of frames at a steady `interval`; return the events and the end time. */
function run(q: QualityController, t0: number, ms: number, interval: number): { events: QualityEvent[]; t: number } {
  const events: QualityEvent[] = [];
  let t = t0;
  while (t < t0 + ms) {
    t += interval;
    const e = q.frame(t, interval);
    if (e) events.push(e);
  }
  return { events, t };
}

describe('quality tiers', () => {
  it('a device at 60 fps stays on high; nothing is judged while settling', () => {
    const q = new QualityController(0);
    expect(run(q, 0, SETTLE_MS - 100, 50).events).toEqual([]);   // slow, but settling
    expect(run(q, SETTLE_MS, 30_000, 1000 / 60).events).toEqual([]);
    expect(q.tier).toBe('high');
  });

  it('steps down a tier per slow window, each after settling again', () => {
    const q = new QualityController(0);
    let { events, t } = run(q, 0, SETTLE_MS + WINDOW_MS + 20, 1000 / 30);
    expect(events).toEqual([expect.objectContaining({ kind: 'tier', tier: 'medium' })]);
    ({ events, t } = run(q, t, SETTLE_MS + WINDOW_MS + 40, 1000 / 30));
    expect(events.map((e) => e.kind === 'tier' && e.tier)).toEqual(['low']);
    expect(q.tier).toBe('low');
    expect(t).toBeGreaterThan(0);
  });

  it('steps back up only after sustained fast windows, and stops oscillating', () => {
    const q = new QualityController(0, 'auto', 'medium');
    let t = run(q, 0, SETTLE_MS + WINDOW_MS * (UP_WINDOWS - 1) + 50, 1000 / 60).t;
    expect(q.tier).toBe('medium');                                 // not yet: fewer than UP_WINDOWS windows
    t = run(q, t, WINDOW_MS + 50, 1000 / 60).t;
    expect(q.tier).toBe('high');
    // high is too slow here: down twice from high, then it never tries high again
    for (let k = 0; k < 2; k += 1) {
      t = run(q, t, SETTLE_MS + WINDOW_MS + 50, 1000 / 40).t;
      expect(q.tier).toBe('medium');
      t = run(q, t, SETTLE_MS + WINDOW_MS * UP_WINDOWS + 100, 1000 / 60).t;
    }
    expect(q.tier).toBe('medium');
  });

  it('ignores stalls (a hidden tab) and restarts settling on request', () => {
    const q = new QualityController(0);
    let t = SETTLE_MS;
    for (let k = 0; k < 100; k += 1) { t += STALL_MS + 1; expect(q.frame(t, STALL_MS + 1)).toBeNull(); }
    q.restart(t);
    expect(run(q, t, SETTLE_MS - 10, 1000 / 10).events).toEqual([]);
    expect(q.tier).toBe('high');
  });

  it('falls back to top-down when the low tier cannot hold 24 fps', () => {
    const q = new QualityController(0, 'auto', 'low');
    const { events } = run(q, 0, SETTLE_MS + WINDOW_MS * FALLBACK_WINDOWS + 100, 1000 / 15);
    expect(events).toEqual([expect.objectContaining({ kind: 'fallback' })]);
    expect(q.fellBack).toBe(true);
    expect(run(q, 20_000, 10_000, 1000 / 60).events).toEqual([]);  // decided: nothing more
  });

  it('a low tier at 30 fps is slow but does not fall back', () => {
    const q = new QualityController(0, 'auto', 'low');
    expect(run(q, 0, 30_000, 1000 / 30).events).toEqual([]);
  });

  it('an override holds its tier and never steps', () => {
    const q = new QualityController(0, 'high');
    expect(run(q, 0, 30_000, 1000 / 20).events).toEqual([]);
    expect(q.tier).toBe('high');
    expect(q.setChoice('low', 30_000)).toEqual(expect.objectContaining({ kind: 'tier', tier: 'low' }));
    expect(q.setChoice('auto', 30_000)).toBeNull();
    expect(q.tier).toBe('low');
  });
});

it('sustained stalls on a known-visible canvas reach the low-tier fallback',()=>{
 const q=new QualityController(0);const events=[];
 for(let now=500;now<50000;now+=500){const event=q.frame(now,500,true);if(event)events.push(event);}
 expect(events.map(event=>event.kind)).toEqual(['tier','tier','fallback']);
 expect(q.fellBack).toBe(true);
});
