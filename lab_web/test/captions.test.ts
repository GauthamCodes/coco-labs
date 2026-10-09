// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

import { caption } from '../src/arena/lens/captions';
import { FamilyStore } from '../src/arena/lens/store';

const CMD = 'coco.control.local.command.v1';
const store = (status: string, nCandidates: number, nValid: number) => {
  const s = new FamilyStore();
  s.add({ channel: CMD, tick: 5, columns: { status: [status], n_candidates: new Float64Array([nCandidates]), n_valid: new Float64Array([nValid]) }, scalars: {} });
  return s;
};

describe('Move lens captions', () => {
  it("a recorded Lab 5 cycle says what Nav2 logged, never the converter's record marker", () => {
    expect(caption('move', store('eval', 819, 0), 5)).toBe('Nav2 scored 819 candidates this cycle; 0 were valid.');
    expect(caption('move', store('eval', 819, -1), 5)).toBe('Nav2 scored 819 candidates this cycle.');
    expect(caption('move', store('rollout', 819, 12), 5)).toBeNull();
    expect(caption('move', store('rollout:n_valid_unknown', 819, -1), 5)).toBeNull();
  });

  it("the model's own statuses are unchanged", () => {
    expect(caption('move', store('ok', 231, 200), 5)).toBeNull();
    expect(caption('move', store('no_valid_candidate', 231, 0), 5)).toMatch(/^No valid candidate: all 231 trajectories/);
  });
});
