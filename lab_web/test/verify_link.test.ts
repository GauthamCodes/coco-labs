// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * `coco verify` reads the links the page writes (M3.6): its decoder
 * (tools/verify.mjs) is the inverse of src/play/share.ts's encoder.
 */

import { describe, expect, it } from 'vitest';

import { encodeScore } from '../src/play/share';
// @ts-expect-error -- a Node tool, plain JavaScript
import { decodeLink } from '../tools/verify.mjs';

const H = 'c'.repeat(64);
const R = 'd'.repeat(64);

describe('coco verify reads what the page writes', () => {
  it.each([
    ['next-node', 'wall', [[2, 3], [2, 4]]],
    ['map-the-arena', 'forty-metres', { ticks: 99, log: [{ tick: 3, kind: 'goal', x: 0.1 + 0.2, y: -6.000000000000001 }] }],
    ['case-file-detective', 'kidnapped', [632]],
    ['search-the-bays', 'ends', ['ü', 'non-ASCII survives']],
  ])('%s/%s', (challenge, level, inputs) => {
    const submission = { v: 1 as const, challenge, level, level_hash: H, inputs };
    const link = `https://example.org/coco-labs/${encodeScore({ submission, result_hash: R })}`;
    expect(decodeLink(link)).toEqual({ submission, result_hash: R });
  });

  it('refuses a link that is not a Play link', () => {
    expect(() => decodeLink('https://example.org/coco-labs/?view=arena&run=abc')).toThrow(/not a Play challenge link/);
  });
});
