// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R6.A3: the LIVE truth-vs-estimate distance is shown only when the gateway says its truth is in the level's
 * own map frame ('level_map': the coco-ros2 image after the fix, checked against Gazebo on a test route).
 */
import { describe, expect, it } from 'vitest';
import { truthGap, truthGapText } from '../src/ros/telemetry';

describe('the LIVE truth-vs-estimate distance', () => {
  it('is measured only in the level map frame', () => {
    expect(truthGap('level_map', [23.3, 6.0, 0], [23.0, 6.4, 0])).toBeCloseTo(0.5, 9);
    expect(truthGap('arena_spawn', [25.0, 6.0, 0], [23.0, 6.0, 0])).toBeNull();   // the old image: 2 m off
    expect(truthGap(undefined, [23, 6, 0], [23, 6, 0])).toBeNull();                 // a gateway that does not say
    expect(truthGap('level_map', undefined, [23, 6, 0])).toBeNull();                // no truth reported
  });
  it('reads as words on the telemetry strip, or nothing', () => {
    expect(truthGapText(0.1234)).toBe(' · truth↔AMCL 0.12 m');
    expect(truthGapText(null)).toBe('');
    expect(truthGapText(Number.NaN)).toBe('');
  });
});
