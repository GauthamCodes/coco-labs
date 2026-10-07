// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The Lab 5 decoders against Python, bundle by bundle: every array's
// little-endian bytes must hash to what coco_lab wrote
// (golden/move_expected.json, from tools/make_move_expectations.py), and
// the content hash is RECOMPUTED here and must equal the manifest's.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { BundleError } from '../src/bundle/errors';
import { sha256Hex } from '../src/bundle/sha256';
import {
  DRIVE_SCHEMA, loadDriveBytes, loadReplanBytes, parseMoveManifest, REPLAN_SCHEMA,
  type DecodedDriveBundle, type DecodedReplanBundle,
} from '../src/move/decode';
import { LAB_WEB, readBundleDir, REPO } from './helpers';

const expected = JSON.parse(readFileSync(join(LAB_WEB, 'test/golden/move_expected.json'), 'utf-8'));
type Col = Uint8Array | Int32Array | Float64Array;
const bytesOf = (c: Col) => new Uint8Array(c.buffer, c.byteOffset, c.byteLength);
const v = (x: unknown) => (x === 'nan' ? NaN : x === 'inf' ? Infinity : x === '-inf' ? -Infinity : x);

function replanColumn(b: DecodedReplanBundle, name: string): Col {
  if (name.startsWith('trace.')) return (b.trace as unknown as Record<string, Col>)[name.slice(6)];
  return ({ known: b.known, truth: b.truth, known_final: b.knownFinal, walk: b.walk, paths: b.paths,
    cost: b.cost, truth_cost: b.truthCost } as Record<string, Col>)[name];
}

function driveColumn(b: DecodedDriveBundle, name: string): Col {
  if (name === 'path') return b.scenario.path;
  const [, id, ...rest] = name.split('.');
  const r = b.runs.find((x) => x.id === id)!;
  const key = rest.join('.');
  if (key.startsWith('actor.')) return r.actors[key.slice(6)];
  if (key.startsWith('roll.')) return (r.rollouts as unknown as Record<string, Col>)[key.slice(5)];
  return ({ gt: r.gt, amcl: r.amcl, cmd: r.cmd, wheel: r.wheel, 'chosen.t': r.chosenT,
    'chosen.off': r.chosenOff, 'chosen.pts': r.chosenPts, eval: r.eval } as Record<string, Col>)[key];
}

const cases: Array<[string, any]> = expected.bundles.map((e: any) => [e.id, e]);

describe.each(cases)('Lab 5 bundle %s', (_id, exp) => {
  const load = () => {
    const { manifest, arrays } = readBundleDir(join(REPO, exp.dir));
    return exp.schema === REPLAN_SCHEMA ? loadReplanBytes(manifest, arrays) : loadDriveBytes(manifest, arrays);
  };

  it('decodes, every array byte-identical to coco_lab', async () => {
    const b = await load();
    expect(b.version).toBe(exp.version);
    expect(b.contentHash).toBe(exp.content_hash);
    for (const [name, a] of Object.entries(exp.arrays) as Array<[string, any]>) {
      const col = exp.schema === REPLAN_SCHEMA ? replanColumn(b as DecodedReplanBundle, name)
        : driveColumn(b as DecodedDriveBundle, name);
      expect(col, name).toBeDefined();
      expect(col.length, name).toBe(a.count);
      expect(await sha256Hex(bytesOf(col)), name).toBe(a.sha256);
      if (a.count) {
        expect(col[0], `${name}[0]`).toBe(v(a.first));
        expect(col[col.length - 1], `${name}[-1]`).toBe(v(a.last));
      }
    }
  });

  it('carries the summaries and metrics as coco_lab wrote them', async () => {
    const b = await load();
    if (exp.schema === REPLAN_SCHEMA) {
      const r = b as DecodedReplanBundle;
      expect(r.summary).toEqual(exp.summary);
      expect(r.rounds.length).toBe(exp.rounds);
    } else {
      const d = b as DecodedDriveBundle;
      expect(d.runs.map((r) => ({ id: r.id, controller: r.controller, outcome: r.outcome, metrics: r.metrics })))
        .toEqual(exp.runs);
    }
  });

  it('refuses a flipped array byte', async () => {
    const { manifest, arrays } = readBundleDir(join(REPO, exp.dir));
    if (exp.compression !== 'none') return; // a flipped gzip byte fails earlier, in gunzip
    const bad = arrays.slice();
    bad[3] ^= 1;
    const p = exp.schema === REPLAN_SCHEMA ? loadReplanBytes(manifest, bad) : loadDriveBytes(manifest, bad);
    await expect(p).rejects.toThrow(BundleError);
  });
});

describe('Lab 5 manifests', () => {
  const dir = (n: string) => readBundleDir(join(REPO, 'coco_lab/test/fixtures/move_bundles', n));

  it('refuse the other format and an unknown major', () => {
    const { manifest } = dir('replan_small');
    expect(() => parseMoveManifest(manifest, DRIVE_SCHEMA)).toThrow(/schema/);
    const text = new TextDecoder().decode(manifest).replace('"version":"1.0"', '"version":"2.0"');
    expect(() => parseMoveManifest(new TextEncoder().encode(text), REPLAN_SCHEMA)).toThrow(/major version 2/);
  });

  it('decode the replan walk and rounds consistently', async () => {
    const { manifest, arrays } = dir('replan_small');
    const b = await loadReplanBytes(manifest, arrays);
    expect([b.walk[0], b.walk[1]]).toEqual(b.world.start);
    const last = b.walk.length - 2;
    expect([b.walk[last], b.walk[last + 1]]).toEqual(b.world.goal);
    const total = b.rounds.reduce((s, r) => s + r.path_len, 0);
    expect(b.paths.length).toBe(2 * total);
    expect(b.summary.costs_agree).toBe(true);
  });

  it('decode the drive rollouts with their flags and NaN totals', async () => {
    const { manifest, arrays } = dir('drive_toy_gz');
    const b = await loadDriveBytes(manifest, arrays);
    const r = b.runs[0];
    expect(r.rollouts).not.toBeNull();
    expect(Array.from(r.rollouts!.flags)).toEqual([5, 0]);
    expect(Array.from(r.rollouts!.n)).toEqual([819, 400]);
    expect(r.record.note).toMatch(/MADE UP/);
  });
});
