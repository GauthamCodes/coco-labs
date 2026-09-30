// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The decoder against Python, bundle by bundle: all six golden fixtures
// (five 1.0, one 1.1) and the three 1C recorded runs. Every array's
// little-endian bytes must hash to what coco_lab wrote (expected.json), and
// the content and map hashes are RECOMPUTED here and must equal the
// manifests'. The fixture bytes are read in place, never copied.

import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { columnBytes } from '../src/bundle/arrays';
import { contentHash, mapContentHash, parseManifest } from '../src/bundle/decode';
import type { DecodedBundle } from '../src/bundle/model';
import { sha256Hex } from '../src/bundle/sha256';
import { expected, loadDir, readBundleDir, REPO } from './helpers';

function columnOf(b: DecodedBundle, name: string) {
  const [head, ...rest] = name.split('.');
  if (head === 'trace') return (b.trace.events as any)[rest[0]];
  if (name === 'map.occupancy') return b.map.occupancy;
  if (name === 'map.cost') return b.map.cost;
  return b.recording!.streams[rest[0] as 'gt']![rest[1]];
}

describe.each(expected.bundles.map((e) => [e.id, e] as const))('bundle %s', (_id, exp) => {
  const dir = join(REPO, exp.dir);

  it('decodes, with every array byte-identical to coco_lab', async () => {
    const b = await loadDir(dir);
    expect(b.version).toBe(exp.version);
    expect(b.contentHash).toBe(exp.content_hash);
    expect(b.provenance.source_kind).toBe(exp.source_kind);
    expect(b.map.contentHash).toBe(exp.map_hash);
    expect([b.map.width, b.map.height]).toEqual([exp.width, exp.height]);
    expect(b.map.cost !== null).toBe(exp.cost_layer);
    expect(b.map.geo === null ? null : {
      resolution: b.map.geo.resolution, origin: b.map.geo.origin, frame: b.map.geo.frame,
    }).toEqual(exp.geo);
    expect(b.trace.n).toBe(exp.events);
    expect(b.trace.header).toEqual(exp.header);
    expect(b.trace.summary).toEqual(exp.summary);
    expect(b.run).toEqual(exp.run);
    expect(b.rawBytes).toBe(exp.file_bytes.raw);
    const names = Object.keys(exp.arrays);
    expect(b.arrays.map((a) => a.name)).toEqual(
      [...names].sort((x, y) => exp.arrays[x].offset - exp.arrays[y].offset));
    for (const name of names) {
      const e = exp.arrays[name];
      const col = columnOf(b, name);
      expect(col.length, name).toBe(e.count);
      expect(await sha256Hex(columnBytes(col)), name).toBe(e.sha256);
      if (e.count > 0) {
        expect(col[0], name).toBe(e.first);
        expect(col[col.length - 1], name).toBe(e.last);
      }
    }
    if (exp.recording === null) {
      expect(b.recording).toBeNull();
    } else {
      expect(b.recording!.groups).toEqual(exp.recording.groups);
      expect(b.recording!.missing).toEqual(exp.recording.missing);
      expect(b.recording!.runId).toBe(exp.recording.run_id);
    }
  });

  it('recomputes the content hash and the map hash Python wrote', async () => {
    const { manifest } = readBundleDir(dir);
    const b = await loadDir(dir);
    const parsed = parseManifest(manifest);
    // raw = the concatenated LE arrays, rebuilt from the decoded columns
    const parts = b.arrays.map((a) => columnBytes(columnOf(b, a.name)));
    const raw = new Uint8Array(parts.reduce((s, p) => s + p.length, 0));
    let off = 0;
    for (const p of parts) {
      raw.set(p, off);
      off += p.length;
    }
    expect(await contentHash(parsed.tree, raw)).toBe(exp.computed_content_hash);
    expect(await mapContentHash(b.map)).toBe(exp.map_hash);
  });

  it('decodes identically through the DataView (big-endian host) path', async () => {
    const fast = await loadDir(dir);
    const slow = await loadDir(dir, { forceDataView: true });
    for (const a of fast.arrays) {
      expect(await sha256Hex(columnBytes(columnOf(slow, a.name))), a.name)
        .toBe(await sha256Hex(columnBytes(columnOf(fast, a.name))));
    }
  });
});

describe('the fixture set', () => {
  it('is six golden fixtures (five 1.0, one 1.1) and three 1C bundles', () => {
    const ids = expected.bundles.map((e) => e.id);
    expect(ids).toHaveLength(9);
    expect(expected.bundles.filter((e) => e.version === '1.0')).toHaveLength(5);
    expect(expected.bundles.filter((e) => e.version === '1.1')).toHaveLength(4);
  });

  it('has unaligned array offsets, which the decoder copies', () => {
    const odd = expected.bundles.flatMap((e) => Object.entries<any>(e.arrays)
      .filter(([, a]) => a.dtype !== 'u8' && a.offset % (a.dtype === 'i32' ? 4 : 8) !== 0));
    expect(odd.length).toBeGreaterThan(0);
  });

  it('decodes the synthetic 1.1 fixture: geo null, cmd missing', async () => {
    const b = await loadDir(join(REPO, 'coco_lab/test/fixtures/bundles/recorded_run_synthetic_1_1'));
    expect(b.version).toBe('1.1');
    expect(b.map.geo).toBeNull();
    expect(b.recording!.missing).toEqual(['cmd']);
    expect(b.recording!.streams.cmd).toBeUndefined();
    expect(Object.keys(b.recording!.streams).sort()).toEqual(['amcl', 'gt', 'plan']);
  });
});
