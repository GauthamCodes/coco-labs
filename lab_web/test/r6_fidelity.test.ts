// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** R6.B1: the fidelity knobs in the Workbench builder, and their words on results. */
import { describe, expect, it } from 'vitest';
import { fidelityText, setKnob } from '../src/workbench/Fidelity';
import type { ExperimentSpec } from '../src/workbench/spec';

const base: ExperimentSpec = { schema: 'coco.experiment.v1', family: 'control', algorithms: [{ name: 'rpp' }],
  scenarios: { kind: 'sampled', n: 2, seed: 1 } };

describe('the fidelity knobs', () => {
  it('appear in the spec only when set, and leave it as it was when cleared', () => {
    const on = setKnob(setKnob(base, 'cmd_latency', 5), 'lidar_dropout', 0.1);
    expect(on.fidelity).toEqual({ cmd_latency: 5, lidar_dropout: 0.1 });
    const off = setKnob(setKnob(on, 'cmd_latency', undefined), 'lidar_dropout', '');
    expect('fidelity' in off).toBe(false);          // no knob left: the spec as it was
    expect(setKnob(base, 'linear_accel', Number.NaN).fidelity).toBeUndefined();
  });
  it('read as words on every result', () => {
    expect(fidelityText({ lidar_dropout: 0.1, cmd_latency: 5, odom_preset: 'stack_uncalibrated' }))
      .toBe('command latency 5 ticks · LiDAR dropout 0.1 · odometry stack_uncalibrated');
    expect(fidelityText(undefined)).toBe('');
  });
});
