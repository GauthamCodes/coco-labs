// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// Lab 4's display arithmetic against a golden bundle coco_lab wrote: what the
// page draws at each event is read from the bundle, never recomputed.

import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { loadSearchBytes } from '../src/search/decode';
import { beliefAt, bookkeepingAt, candidatesAt, kindAt, narrate, outcomeWords, pathAt } from '../src/search/view';
import { readBundleDir, REPO } from './helpers';

async function line() {
  const { manifest, arrays } = readBundleDir(join(REPO, 'coco_lab/test/fixtures/search_bundles/line_small'));
  return loadSearchBytes(manifest, arrays);
}

describe('Lab 4 view', () => {
  it('reads the belief, bookkeeping and candidates the bundle carries', async () => {
    const b = await line();
    const run = b.runs.find((r) => r.id === 'policy')!;
    const n = b.problem.regions.length;
    expect(beliefAt(run, n, 0)).toEqual(Array.from(run.belief.subarray(0, n)));
    const last = run.n - 1;
    expect(kindAt(run, last)).toBe(run.summary.status === 'discovered' ? 'discover' : kindAt(run, last));
    const book = bookkeepingAt(run, last);
    expect(book.order.map((i) => b.problem.regions[i].id)).toEqual(run.summary.order);
    expect(book.surveys).toBe(run.summary.surveys);
    const c = candidatesAt(run, n, 0);
    expect(c.filter((v) => v !== null).length).toBe(n);
    expect(pathAt(b.problem, run, last).length).toBe(1 + 3 * book.order.length);
  });

  it('narrates from what the bundle says happened', async () => {
    const b = await line();
    const gaveUp = b.runs.find((r) => r.id === 'gave_up')!;
    expect(narrate(b.problem, gaveUp, gaveUp.n - 1)).toContain('the challenge is failed');
  });

  it('words a matrix outcome honestly', () => {
    expect(outcomeWords('COMPLETE', '--')).toBe('COMPLETE');
    expect(outcomeWords('COMPLETE', null)).toBe('COMPLETE');
    expect(outcomeWords('COMPLETE', 'LOCALIZATION_DEGRADED')).toBe('COMPLETE (after a relocalisation)');
    expect(outcomeWords('ABORT', 'RETURN_FAILED')).toBe('ABORT (RETURN_FAILED)');
    expect(outcomeWords('VOID', null)).toBe('VOID');
  });
});
