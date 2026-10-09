// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M1.9: every Lab 1 bundle the site serves converts to a v2 run and back
 * with nothing lost. "Nothing lost" is checked the strict way: the v1
 * arrays are rebuilt from the v2 CHANNELS alone (not copied from the spec)
 * and the v1 decoder accepts them, which it does only when the bundle's
 * content hash matches; then every column is compared value for value.
 */

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { zstdCompressSync } from 'node:zlib';

import { describe, expect, it } from 'vitest';

import { arraysFileName, loadBundleBytes } from '../src/bundle/load';
import { parseManifest } from '../src/bundle/decode';
import { fromLab1, toLab1 } from '../src/convert/lab1';
import { EvidenceClass, Tier } from '../src/schemas/gen/coco/envelope/v1/manifest_pb';
import { readRun, writeRun } from '../src/schemas/mcap';
import { LAB_WEB } from './helpers';

const DIR = join(LAB_WEB, 'public', 'generated', 'bundles');
const IDS = readdirSync(DIR).sort();

async function load(id: string) {
  const manifest = new Uint8Array(readFileSync(join(DIR, id, 'manifest.json')));
  const arrays = new Uint8Array(readFileSync(join(DIR, id, arraysFileName(parseManifest(manifest).compression))));
  return { manifest, bundle: await loadBundleBytes(manifest, arrays) };
}

describe('Lab 1 bundles -> v2 runs -> Lab 1 bundles', () => {
  it('finds the ten-plus bundles the site serves, three of them recorded runs', () => {
    expect(IDS.length).toBeGreaterThanOrEqual(10);
    expect(IDS.filter((i) => i.startsWith('lab1c_'))).toEqual(['lab1c_astar', 'lab1c_dijkstra', 'lab1c_greedy']);
  });

  it.each(IDS)('%s: lossless, hash-checked, labelled by evidence class', async (id) => {
    const { manifest, bundle } = await load(id);
    const conv = await fromLab1(bundle, manifest);
    const bytes = await writeRun(conv.manifest, conv.records, (d) => new Uint8Array(zstdCompressSync(d)));
    const run = await readRun(bytes);
    const back = await toLab1(run.manifest, run.messages); // throws unless the content hash matches
    expect(back.contentHash).toBe(bundle.contentHash);
    for (const k of Object.keys(bundle.trace.events) as (keyof typeof bundle.trace.events)[]) {
      expect(back.trace.events[k]).toEqual(bundle.trace.events[k]);
    }
    expect(back.map.occupancy).toEqual(bundle.map.occupancy);
    expect(back.recording?.streams).toEqual(bundle.recording?.streams);
    const stack = bundle.provenance.source_kind === 'recorded-run';
    expect(run.manifest.tier).toBe(stack ? Tier.STACK : Tier.TRACE);
    expect(run.manifest.evidenceClass).toBe(stack ? EvidenceClass.STACK : EvidenceClass.MODEL);
    const channels = new Set(run.messages.map((m) => m.channel));
    if (stack) {
      for (const c of ['coco.truth.pose.v1', 'coco.robot.state.v1', 'coco.plan.path.poses.v1', 'coco.metrics.values.v1',
        'coco.annotation.text.v1']) expect(channels).toContain(c);
    } else {
      expect(channels).not.toContain('coco.truth.pose.v1');
    }
    // deterministic: same bundle, same file
    const again = await fromLab1(bundle, manifest);
    expect(await writeRun(again.manifest, again.records, (d) => new Uint8Array(zstdCompressSync(d)))).toEqual(bytes);
  }, 120_000);

  it('a damaged channel is caught, not passed through', async () => {
    const { manifest, bundle } = await load('lab1c_greedy');
    const conv = await fromLab1(bundle, manifest);
    const run = await readRun(await writeRun(conv.manifest, conv.records));
    const i = run.messages.findIndex((m) => m.channel === 'coco.truth.pose.v1');
    const data = run.messages[i].data.slice();
    data[data.length - 1] ^= 1; // flip one bit of one ground-truth double
    run.messages[i] = { ...run.messages[i], data };
    await expect(toLab1(run.manifest, run.messages)).rejects.toThrow();
  });
});

describe('converted runs in the Arena viewer (replay.ts)', () => {
  const V2 = join(LAB_WEB, 'public', 'generated', 'v2');
  const parse = async (id: string) => {
    const { parseConverted } = await import('../src/arena/replay');
    return parseConverted(new Uint8Array(readFileSync(join(V2, `${id}.mcap`))));
  };

  it.each(['lab1c_astar', 'lab1c_dijkstra', 'lab1c_greedy'])('%s plays as STACK: 0.1 s ticks, belief beside truth', async (id) => {
    const { bundle } = await load(id);
    const run = await parse(id);
    const meta = bundle.recording!.meta as { result: { t_accept_sim: number } };
    const gt = bundle.recording!.streams.gt!;
    const t0 = bundle.provenance.rosbag!.sim_time_start;
    expect(run.evidence).toBe('STACK');
    expect(run.ticks.map((t) => t.tick)).toEqual(run.ticks.map((_, i) => i + 1)); // contiguous, as the session needs
    expect(run.ticks.length).toBe(Math.floor((gt.t[gt.t.length - 1] - t0) / 0.1 + 1e-9));
    // every tick's truth is the latest ground-truth sample at or before it
    for (const t of run.ticks.filter((_, i) => i % 97 === 0)) {
      let j = 0;
      while (j + 1 < gt.t.length && gt.t[j + 1] <= t.t_world) j += 1;
      expect(t.truth).toEqual([gt.x[j], gt.y[j], gt.yaw[j]]);
    }
    // the stack's belief is drawn (once it has one), and it is not the truth
    const amcl = bundle.recording!.streams.amcl!;
    const late = run.ticks.at(-1)!;
    expect(late.pose).toEqual([amcl.x.at(-1), amcl.y.at(-1), amcl.yaw.at(-1)]);
    expect(late.pose).not.toEqual(late.truth);
    // the search: once, at FollowPath acceptance, with the bundle's totals
    const planned = run.ticks.filter((t) => t.plans.length);
    expect(planned.length).toBe(1);
    expect(Math.abs(planned[0].t_world - meta.result.t_accept_sim)).toBeLessThanOrEqual(0.1 + 1e-9);
    expect(planned[0].plans[0].summary.expansions).toBe(bundle.trace.summary.expansions);
    expect([...run.batches.values()].flat().reduce((n, b) => n + b.cols.kind.length, 0)).toBe(bundle.trace.n);
    expect(run.notes.length).toBeGreaterThan(0);
    expect(run.results).toEqual(bundle.recording!.meta);
  });

  it('a glass-box trace plays as MODEL: one tick, the search, no robot motion', async () => {
    const run = await parse('bfs_no_path');
    expect(run.evidence).toBe('MODEL');
    expect(run.ticks.length).toBe(1);
    expect(run.ticks[0].plans[0].status).toBe('no_path');
    expect(run.world.resolution).toBe(1); // a bare trace has no geometry
    expect(run.results).toBeNull();
  });
});
