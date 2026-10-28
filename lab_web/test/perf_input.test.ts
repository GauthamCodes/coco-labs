// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// M4.10: ?perf's input -> motion (README §7 M4, the phone touch row), control_latency.mjs's definition.

import { describe, expect, it } from 'vitest';

import { perf } from '../src/arena/perf';

const still = (p: number[], frames: number, t0: number) => {
  for (let k = 0; k < frames; k += 1) perf.drawnPose(p, t0 + k * 16);
};

describe('perf input -> motion', () => {
  it('times a drive input from rest to the first frame that draws the robot moved', () => {
    still([1, 2, 0.5], 5, 0);
    perf.driveInput(100);
    perf.drawnPose([1, 2, 0.5], 116);          // the same pose: not yet
    perf.drawnPose([1.001, 2, 0.5], 140);
    expect(perf.snapshot().inputToMotionMs.at(-1)).toBe(40);
  });

  it('ignores an input while the robot is still moving (coasting or autonomy)', () => {
    const n = perf.snapshot().inputToMotionMs.length;
    perf.drawnPose([2, 2, 0], 200);
    perf.drawnPose([2.1, 2, 0], 216);           // moving: not at rest
    perf.driveInput(220);
    perf.drawnPose([2.2, 2, 0], 232);
    expect(perf.snapshot().inputToMotionMs.length).toBe(n);
  });

  it('G2.9: an input released before any motion (pushed into a wall) is no sample and disarms the timer', () => {
    const n = perf.snapshot().inputToMotionMs.length, blocked = perf.snapshot().inputNoMotion;
    still([5, 5, 0], 5, 500);
    perf.driveInput(600);                       // pushed into a wall: the drawn pose never changes
    still([5, 5, 0], 60, 616);
    perf.driveRelease();                        // released at ~1.6 s with no motion
    perf.drawnPose([5, 5, 0], 1700);
    perf.driveInput(1800);                      // backing away moves it 60 ms later
    perf.drawnPose([4.99, 5, 0], 1860);
    const s = perf.snapshot();
    expect(s.inputNoMotion).toBe(blocked + 1);
    expect(s.inputToMotionMs.length).toBe(n + 1);
    expect(s.inputToMotionMs.at(-1)).toBe(60);  // not 1260 (timed from the blocked push)
  });

  it('a release after the motion was drawn changes nothing', () => {
    const blocked = perf.snapshot().inputNoMotion;
    still([6, 6, 0], 4, 3000);
    perf.driveInput(3100);
    perf.drawnPose([6.1, 6, 0], 3150);
    perf.driveRelease();
    expect(perf.snapshot().inputNoMotion).toBe(blocked);
    expect(perf.snapshot().inputToMotionMs.at(-1)).toBe(50);
  });

  it('keeps the last 20', () => {
    for (let k = 0; k < 25; k += 1) {
      const t = 1000 + k * 200;
      still([k, 0, 0], 4, t);
      perf.driveInput(t + 70);
      perf.drawnPose([k + 0.5, 0, 0], t + 80 + k);
    }
    const ms = perf.snapshot().inputToMotionMs;
    expect(ms.length).toBe(20);
    expect(ms.at(-1)).toBe(10 + 24);
  });
});
