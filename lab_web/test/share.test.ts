// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// Share links: the TypeScript half of the round trip. The Python half
// (tools/test_glue.py::test_share_vectors_reproduce_their_trace_digests)
// reruns coco_lab on each vector and must get the digest a link carries.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import type { Catalog } from '../src/bundle/load';
import {
  decodeRuns, diffRuns, encodeRuns, parseShare, runsToStrokes, ShareError, shareQuery, traceDigest,
  type EditRun,
} from '../src/lab/share';
import type { SearchSettings } from '../src/lab/settings';
import type { Stroke } from '../src/worker/protocol';
import { LAB_WEB, loadDir, REPO } from './helpers';

const catalog: Catalog = JSON.parse(readFileSync(join(LAB_WEB, 'public/generated/catalog.json'), 'utf-8'));
const sa = catalog.settings!;
interface Vector { bundle: string; strokes: Stroke[]; settings: SearchSettings; trace_sha256: string }
const vectors: { golden: Record<string, string>; vectors: Vector[] } = JSON.parse(
  readFileSync(join(LAB_WEB, 'test/golden/share_vectors.json'), 'utf-8'));
const fixture = (id: string) => join(REPO, 'coco_lab/test/fixtures/bundles', id);
const cellsOf = (id: string) => ({ astar_open: 400, weighted_astar_greedy_trap: 400 } as Record<string, number>)[id] ?? null;

describe('the trace digest agrees with Python', () => {
  it.each(Object.entries(vectors.golden))('%s', async (id, sha) => {
    expect(await traceDigest(await loadDir(fixture(id)))).toBe(sha);
  });
});

describe('a share link round-trips the inputs coco_lab ran', () => {
  it.each(vectors.vectors.map((v) => [v.bundle, v] as const))('%s', async (_, v) => {
    const base = await loadDir(fixture(v.bundle));
    const cur = base.map.occupancy.slice();
    for (const s of v.strokes) for (const [r, c] of s.cells) cur[r * base.map.width + c] = s.value === 'occupied' ? 1 : 0;
    const runs = diffRuns(base.map.occupancy, cur);
    const q = shareQuery({ bundle: v.bundle, settings: v.settings, runs, digest: v.trace_sha256.slice(0, 12) }, sa);
    expect(q).toMatchSnapshot();
    const back = parseShare(q, sa, cellsOf)!;
    expect(back.bundle).toBe(v.bundle);
    expect(back.settings).toEqual(v.settings);
    expect(runsToStrokes(back.runs, base.map.width)).toEqual(v.strokes);
    expect(back.digest).toBe(v.trace_sha256.slice(0, 12));
  });
});

describe('edits encoding', () => {
  it('round-trips 1,000 seeded random edit sets, up to the native arena size', () => {
    let seed = 20261001;
    const rand = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    };
    for (let k = 0; k < 1000; k++) {
      const cells = 1 + Math.floor(rand() * 500 * 380);
      const runs: EditRun[] = [];
      let at = 0;
      const n = Math.floor(rand() * 40);
      for (let i = 0; i < n && at < cells; i++) {
        const start = at + Math.floor(rand() * Math.min(5000, cells - at));
        if (start >= cells) break;
        const length = 1 + Math.floor(rand() * Math.min(300, cells - start));
        const value = (rand() < 0.5 ? 0 : 1) as 0 | 1;
        const prev = runs[runs.length - 1];
        // adjacent same-value runs are one run in diffRuns's canonical form
        if (prev && prev.start + prev.length === start && prev.value === value) prev.length += length;
        else runs.push({ start, length, value });
        at = start + length;
      }
      expect(decodeRuns(encodeRuns(runs), cells)).toEqual(runs);
    }
  });

  it('diffRuns merges neighbours and splits on value', () => {
    const base = Uint8Array.from([0, 0, 0, 1, 1, 2, 0, 0]);
    const cur = Uint8Array.from([1, 1, 0, 0, 0, 0, 0, 1]);
    expect(diffRuns(base, cur)).toEqual([
      { start: 0, length: 2, value: 1 }, { start: 3, length: 3, value: 0 }, { start: 7, length: 1, value: 1 }]);
  });

  it('refuses a map edit it cannot share', () => {
    expect(() => diffRuns(Uint8Array.from([0]), Uint8Array.from([2]))).toThrow(ShareError);
  });
});

describe('a share link is untrusted input', () => {
  const ok = shareQuery({ bundle: 'astar_open', settings: null, runs: [{ start: 3, length: 2, value: 1 }], digest: null }, sa);
  it.each([
    ['an unknown version', ok.replace('v=1', 'v=9')],
    ['an unserved bundle', ok.replace('bundle=astar_open', 'bundle=nope')],
    ['edits outside the map', shareQuery({ bundle: 'astar_open', settings: null, runs: [{ start: 399, length: 2, value: 1 }], digest: null }, sa)],
    ['edits that are not base64url', '?v=1&bundle=astar_open&e=ab%2Bc'],
    ['a truncated number', '?v=1&bundle=astar_open&e=gA'],
    ['an odd count', '?v=1&bundle=astar_open&e=AQ'],
    ['a malformed digest', ok + '&h=XYZ'],
    ['settings out of the catalog', '?v=1&bundle=astar_open&s=9.0.8.0.0'],
    ['a connectivity of 6', '?v=1&bundle=astar_open&s=0.0.6.0.0'],
  ])('refuses %s', (_, q) => {
    expect(() => parseShare(q, sa, cellsOf)).toThrow(ShareError);
  });

  it('leaves the old ?bundle=<id> links alone', () => {
    expect(parseShare('?bundle=astar_open', sa, cellsOf)).toBeNull();
  });
});
