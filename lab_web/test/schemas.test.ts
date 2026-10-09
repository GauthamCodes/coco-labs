// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * coco_schemas in TypeScript (M1.1): the generated code, the columnar fast
 * path and run_id must agree with Python byte for byte (coco_schemas'
 * committed vectors, written by coco_schemas/scripts/make_vectors.py), and
 * a run must survive the MCAP + zstd container.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { zstdCompressSync } from 'node:zlib';

import { create, fromBinary, toBinary } from '@bufbuild/protobuf';
import { describe, expect, it } from 'vitest';

import { encodeBatch, type Column } from '../src/schemas/columns';
import { readRun, writeRun, MANIFEST_CHANNEL } from '../src/schemas/mcap';
import { runId, seedOf } from '../src/schemas/runid';
import { EvidenceClass, ManifestSchema, Tier } from '../src/schemas/gen/coco/envelope/v1/manifest_pb';
import { SearchEventBatchSchema } from '../src/schemas/gen/coco/plan/v1/search_pb';
import { TruthPoseBatchSchema } from '../src/schemas/gen/coco/truth/v1/truth_pb';
import { InputEventBatchSchema, InputKind } from '../src/schemas/gen/coco/input/v1/input_pb';
import { REPO } from './helpers';

const VEC = join(REPO, 'coco_schemas', 'test', 'vectors');
const vec = JSON.parse(readFileSync(join(VEC, 'search_batch.json'), 'utf-8')) as {
  search_id: number; columns: Record<string, number[]>;
};
const pyBytes = new Uint8Array(readFileSync(join(VEC, 'search_batch.binpb')));

const BIG = new Set(['seq', 'tick']);
const camel = (s: string) => s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());

describe('the search batch vector (Python protobuf wrote it)', () => {
  it('the generated TypeScript encodes the same bytes', () => {
    const init: Record<string, unknown> = { searchId: BigInt(vec.search_id) };
    for (const [k, v] of Object.entries(vec.columns)) init[camel(k)] = BIG.has(k) ? v.map(BigInt) : v;
    const msg = create(SearchEventBatchSchema, init as never);
    expect(toBinary(SearchEventBatchSchema, msg)).toEqual(pyBytes);
  });

  it('the columnar fast path, from typed arrays, encodes the same bytes', () => {
    const c = vec.columns;
    const cols: Record<string, Column> = {
      seq: BigUint64Array.from(c.seq.map(BigInt)), tick: BigUint64Array.from(c.tick.map(BigInt)),
      t_world: Float64Array.from(c.t_world), kind: Int32Array.from(c.kind),
      row: Int32Array.from(c.row), col: Int32Array.from(c.col), sub: Int32Array.from(c.sub),
      g: Float64Array.from(c.g), h: Float64Array.from(c.h), f: Float64Array.from(c.f),
      parent_row: Int32Array.from(c.parent_row), parent_col: Int32Array.from(c.parent_col),
      parent_sub: Int32Array.from(c.parent_sub),
    };
    expect(encodeBatch(SearchEventBatchSchema, cols, { search_id: vec.search_id })).toEqual(pyBytes);
  });

  it('decodes back to the columns, and refuses an unknown column', () => {
    const m = fromBinary(SearchEventBatchSchema, pyBytes);
    expect(m.parentRow).toEqual(vec.columns.parent_row);
    expect(m.seq.map(Number)).toEqual(vec.columns.seq);
    expect(() => encodeBatch(SearchEventBatchSchema, { nope: [1] })).toThrow(/no fields nope/);
  });

  it('strings and bools: the fast path matches the generated encoder', () => {
    const cols = { seq: [0, 1, 2], tick: [5, 5, 6], t_world: [0.5, 0.5, 0.6],
      kind: [InputKind.GOAL, InputKind.TELEOP, InputKind.PLANNER], x: [1.5, 0, 0], y: [2, 0, 0], theta: [0, 0, 0],
      has_theta: [false, false, true], linear: [0, 0.3, 0], angular: [0, -0.2, 0], choice: ['', '', 'astar'] };
    const init: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(cols)) init[camel(k)] = BIG.has(k) ? (v as number[]).map(BigInt) : v;
    expect(encodeBatch(InputEventBatchSchema, cols)).toEqual(toBinary(InputEventBatchSchema, create(InputEventBatchSchema, init as never)));
  });
});

describe('run_id', () => {
  const vectors = JSON.parse(readFileSync(join(VEC, 'run_id.json'), 'utf-8')).vectors as
    { note: string; spec_utf8: string; seed: string; engines: [string, string][]; run_id: string }[];

  it.each(vectors.map((v) => [v.note, v] as const))('%s', async (_, v) => {
    expect(await runId(new TextEncoder().encode(v.spec_utf8), v.seed, v.engines)).toBe(v.run_id);
  });

  it('seeds are exact integers in [0, 2^64)', () => {
    expect(seedOf('18446744073709551615')).toBe(2n ** 64n - 1n);
    for (const bad of [-1, 1.5, '01', '1e3', 2n ** 64n, Number.MAX_SAFE_INTEGER + 1]) {
      expect(() => seedOf(bad as never)).toThrow(RangeError);
    }
  });
});

describe('the MCAP container', () => {
  const manifest = create(ManifestSchema, {
    runId: 'f'.repeat(64), specFormat: 'test', seed: 7n, tier: Tier.TRACE,
    evidenceClass: EvidenceClass.MODEL,
    channels: [{ name: 'coco.plan.search.events.v1', message: 'coco.plan.v1.SearchEventBatch' }],
  });
  const truth = encodeBatch(TruthPoseBatchSchema, { seq: [0], tick: [3], t_world: [0.15], x: [1], y: [2], theta: [0.5] });

  it.each([['zstd', (d: Uint8Array) => new Uint8Array(zstdCompressSync(d))], ['none', undefined]] as const)(
    'round-trips every record, %s chunks', async (_, compress) => {
      const bytes = await writeRun(manifest, [
        { channel: 'coco.plan.search.events.v1', schema: SearchEventBatchSchema, data: pyBytes, tWorld: 1.25, seq: 0 },
        { channel: 'coco.truth.pose.v1', schema: TruthPoseBatchSchema, data: truth, tWorld: 0.15 },
      ], compress);
      const run = await readRun(bytes);
      expect(run.profile).toBe('coco');
      expect(run.manifest.runId).toBe(manifest.runId);
      expect(run.messages.map((m) => m.channel)).toEqual([MANIFEST_CHANNEL, 'coco.truth.pose.v1', 'coco.plan.search.events.v1']);
      expect(run.messages[2].data).toEqual(pyBytes);
      expect(run.messages[2].schemaName).toBe('coco.plan.v1.SearchEventBatch');
      expect(run.messages[2].logTime).toBe(1_250_000_000n);
    });

  it('zstd actually compresses the trace chunk', async () => {
    const big = Array.from({ length: 50 }, (_, i) => ({ channel: 'coco.plan.search.events.v1', schema: SearchEventBatchSchema, data: pyBytes, tWorld: i }));
    const z = await writeRun(manifest, big, (d) => new Uint8Array(zstdCompressSync(d)));
    const raw = await writeRun(manifest, big);
    expect(z.byteLength).toBeLessThan(raw.byteLength / 5);
  });
});
