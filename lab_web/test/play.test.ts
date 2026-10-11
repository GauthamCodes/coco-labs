// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Play's page-side pieces (M3.5): the challenge link codec, personal bests
 * (which must survive storage that throws), and the route. Scoring itself is
 * coco_lab.play, tested in Python (coco_lab/test/test_play.py,
 * lab_web/tools/test_play_levels.py) and in browsers (tools/perf/play_check.mjs).
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import { beats, keepBest, readBest, type PlayResult } from '../src/play/best';
import { decodeScore, encodeScore } from '../src/play/share';
import { route } from '../src/landing';

const H = 'a'.repeat(64);
const R = 'b'.repeat(64);

describe('challenge links', () => {
  it('round-trip a submission and its result hash exactly, doubles included', () => {
    const submission = { v: 1 as const, challenge: 'map-the-arena', level: 'forty-metres', level_hash: H,
      inputs: { ticks: 301, log: [{ tick: 0, kind: 'config', choice: 'map.algorithm=occupancy' },
        { tick: 7, kind: 'goal', x: 6.123456789012345, y: -0.1 + 0.2 }] } };
    const q = new URLSearchParams(encodeScore({ submission, result_hash: R }).slice(1));
    expect(q.get('view')).toBe('play');
    expect(decodeScore(q)).toEqual({ submission, result_hash: R });
  });

  it.each([
    ['c=next-node&l=wall', 'no payload'],
    ['c=Next_Node&l=wall&s=e30', 'a bad challenge id'],
    ['c=next-node&l=wall&s=!!!', 'not base64'],
    [`c=next-node&l=wall&s=${btoa(JSON.stringify({ v: 2, h: H, i: [], r: R }))}`, 'another version'],
    [`c=next-node&l=wall&s=${btoa(JSON.stringify({ v: 1, h: 'xyz', i: [], r: R }))}`, 'a bad level hash'],
    [`c=next-node&l=wall&s=${btoa(JSON.stringify({ v: 1, h: H, r: R }))}`, 'no inputs'],
  ])('refuse %s (%s)', (q) => {
    expect(decodeScore(new URLSearchParams(q))).toBeNull();
  });
});

const result = (stars: number, value: number, challenge = 'beat-the-planner'): PlayResult => ({
  challenge, level: 'bog', level_hash: H, valid: true, why: null, score: { name: 'cost ratio', value }, stars,
  metrics: [], thresholds: [], hash: R,
});

describe('personal bests', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('rank by stars, then by the score in the direction that is better', () => {
    expect(beats(result(2, 1.2), { stars: 1, score: 1.0, hash: R, level_hash: H })).toBe(true);
    expect(beats(result(2, 1.2), { stars: 2, score: 1.1, hash: R, level_hash: H })).toBe(false);   // lower ratio is better
    expect(beats(result(2, 7, 'next-node'), { stars: 2, score: 6, hash: R, level_hash: H })).toBe(true); // more matches
    expect(beats({ ...result(3, 1), valid: false }, null)).toBe(false);
  });

  it('are kept per level version, in storage that works', () => {
    const store = new Map<string, string>();
    vi.stubGlobal('window', { localStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => { store.set(k, v); } } });
    expect(keepBest(result(2, 1.2))?.stars).toBe(2);
    expect(keepBest(result(1, 1.0))?.stars).toBe(2);
    expect(readBest('beat-the-planner', 'bog', H)?.score).toBe(1.2);
    expect(readBest('beat-the-planner', 'bog', 'c'.repeat(64))).toBeNull();   // another version of the level
  });

  it('cost nothing when storage throws: the page plays on and remembers nothing', () => {
    const boom = () => { throw new Error('SecurityError'); };
    vi.stubGlobal('window', { localStorage: { getItem: boom, setItem: boom } });
    expect(readBest('beat-the-planner', 'bog', H)).toBeNull();
    expect(keepBest(result(3, 1))).toBeNull();
    vi.stubGlobal('window', { get localStorage() { throw new Error('blocked'); } });
    expect(keepBest(result(3, 1))).toBeNull();
  });
});

describe('the route', () => {
  it('opens Play by name', () => {
    expect(route('?view=play', 'arena')).toEqual({ app: 'play' });
    expect(route('?view=play&c=next-node&l=wall', 'v1')).toEqual({ app: 'play' });
  });
});
