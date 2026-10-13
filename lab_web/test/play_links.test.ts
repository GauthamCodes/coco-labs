// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** M4.8: challenge links carry their payload deflated (z=); M3's s= links still read; coco verify reads both. */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { decodeScore, encodeScore, hasSharedScore, LIMITS, type SharedScore } from '../src/play/share';
// @ts-expect-error -- a Node tool, plain JavaScript
import { decodeLink } from '../tools/verify.mjs';
import { REPO } from './helpers';

const subs = JSON.parse(readFileSync(join(REPO, 'docs', 'v2', 'data', 'm4', 'm48', 'race_submissions.json'), 'utf-8')).submissions;
const longest = subs.reduce((a: { inputs: unknown[] }, b: { inputs: unknown[] }) => (b.inputs.length > a.inputs.length ? b : a));
const shared: SharedScore = {
  submission: { v: 1, challenge: 'race-the-ghost', level: longest.level, level_hash: longest.level_hash, inputs: longest.inputs },
  result_hash: 'b'.repeat(64),
};
const params = (q: string) => new URLSearchParams(q.slice(q.indexOf('?') + 1));

describe('challenge links', () => {
  it('a long race drive makes a short link that decodes exactly', () => {
    const q = encodeScore(shared);
    expect(q).toContain('&z=');
    expect(q.length).toBeLessThan(6000);          // the plain form was 17.9 KB (HTTP 431)
    expect(decodeScore(params(q))).toEqual(shared);
  });

  it('the page sees a submission in a z= link as in an s= link, and none without either (M4.10)', () => {
    // the Play page tested s= alone and ignored every z= link (measured: a race link sat on the level's intro, 300 s)
    expect(hasSharedScore(params(encodeScore(shared)))).toBe(true);
    expect(hasSharedScore(params('?view=play&c=next-node&l=a&s=e30'))).toBe(true);
    expect(hasSharedScore(params('?view=play&c=next-node&l=a'))).toBe(false);
    const page = readFileSync(join(REPO, 'lab_web', 'src', 'play', 'PlayApp.tsx'), 'utf-8');
    expect(page).not.toMatch(/params\.has\('[sz]'\)/);
  });

  it("an M3 link (s=, the plain JSON) still decodes", () => {
    const json = JSON.stringify({ v: 1, h: shared.submission.level_hash, i: shared.submission.inputs, r: shared.result_hash });
    const s = Buffer.from(json, 'utf-8').toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    expect(decodeScore(params(`?view=play&c=race-the-ghost&l=${shared.submission.level}&s=${s}`))).toEqual(shared);
  });

  it('a z payload past the limit, or not deflate, is refused', () => {
    const big = 'A'.repeat(Math.ceil((LIMITS.z + 10) * 4 / 3));
    expect(decodeScore(params(`?c=race-the-ghost&l=warm-up&z=${big}`))).toBeNull();
    expect(decodeScore(params('?c=race-the-ghost&l=warm-up&z=bm90LWRlZmxhdGU'))).toBeNull();
  });

  it('coco verify reads the link the page makes', () => {
    const d = decodeLink(`https://x/coco-labs/${encodeScore(shared)}`);
    expect(d.submission).toEqual(shared.submission);
    expect(d.result_hash).toBe(shared.result_hash);
  });
});
