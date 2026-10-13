// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.6 (M4 prompt: "Watch is at most two layers"): at the Watch level each lens
 * shows at most two COMPUTATION layers, in every camera. World layers (the
 * Move lens's actors: the people the controller avoids) are the scene, not
 * something an algorithm computed; Learn's mission 05 opens on Move at Watch
 * with its candidate arcs, which this keeps.
 */

import { describe, expect, it } from 'vitest';

import { defaultLayers, LENSES } from '../src/arena/lens/registry';

describe('Watch is at most two computation layers', () => {
  it.each(LENSES.map((l) => [l.id, l] as const))('%s', (_id, lens) => {
    const role = new Map(lens.layers.map((x) => [x.id, x.role]));
    const shown = defaultLayers(lens, 'watch').filter((id) => role.get(id) === 'computation');
    expect(shown.length).toBeLessThanOrEqual(2);
  });
});
