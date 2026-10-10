// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The ROS-to-event adapter's output, read in TypeScript (M3.1): Python
 * writes it (coco_lab_ros/adapter.py through coco_schemas/mcap_write.py),
 * the site reads it. The golden file is the adapter's full-detail conversion
 * of a 2 s slice of a Lab 5 recording; coco_lab_ros/test/test_adapter.py
 * pins it byte for byte, this file decodes it and repacks it for the site.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { zstdCompressSync } from 'node:zlib';

import { fromBinary } from '@bufbuild/protobuf';
import { describe, expect, it } from 'vitest';

import { readRawStream, readRun, repackRun, MANIFEST_CHANNEL } from '../src/schemas/mcap';
import { EvidenceClass, ManifestSchema, Tier } from '../src/schemas/gen/coco/envelope/v1/manifest_pb';
import { ScanBatchSchema } from '../src/schemas/gen/coco/sensor/v1/scan_pb';
import { TruthPoseBatchSchema } from '../src/schemas/gen/coco/truth/v1/truth_pb';
import { REPO } from './helpers';

const GOLDEN = join(REPO, 'coco_lab_ros', 'test', 'fixtures', 'golden', 'lab5_crossing_dwb_1.full.mcap');
const bytes = new Uint8Array(readFileSync(GOLDEN));

describe('the adapter output in TypeScript', () => {
  it('reads front to back: profile, schemas, channels, every message', () => {
    const raw = readRawStream(bytes);
    expect(raw.profile).toBe('coco');
    expect(raw.messages.length).toBe(163);
    const topics = new Map([...raw.channels.values()].map((c) => [c.topic, c]));
    expect(topics.get(MANIFEST_CHANNEL)).toBeTruthy();
    expect(raw.metadata.map((m) => m.name)).toEqual(['coco']);
  });

  it('decodes the manifest: STACK, cited by checksum', () => {
    const raw = readRawStream(bytes);
    const manifest = fromBinary(ManifestSchema, raw.messages[0].data);
    expect(manifest.evidenceClass).toBe(EvidenceClass.STACK);
    expect(manifest.tier).toBe(Tier.STACK);
    expect(manifest.specFormat).toBe('coco_lab_ros.case_spec.v1+json');
    const spec = JSON.parse(new TextDecoder().decode(manifest.spec));
    expect(spec.source.files.find((f: { name: string }) => f.name.endsWith('.mcap')).sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(raw.metadata[0].metadata.get('run_id')).toBe(manifest.runId);
  });

  it('decodes Python-encoded batches with the TypeScript schemas', () => {
    const raw = readRawStream(bytes);
    const topic = (id: number) => raw.channels.get(id)!.topic;
    const scans = raw.messages.filter((m) => topic(m.channelId) === 'coco.sensor.scan.lidar.v1')
      .map((m) => fromBinary(ScanBatchSchema, m.data));
    expect(scans.reduce((n, b) => n + b.count.length, 0)).toBe(20);
    const beams = scans.reduce((n, b) => n + b.ranges.length, 0);
    expect(beams).toBe(scans.reduce((n, b) => n + b.count.reduce((a, c) => a + c, 0), 0));
    const truth = raw.messages.filter((m) => topic(m.channelId) === 'coco.truth.pose.v1')
      .map((m) => fromBinary(TruthPoseBatchSchema, m.data));
    expect(truth.reduce((n, b) => n + b.x.length, 0)).toBe(101);
  });

  it('repacks for the site: chunked, zstd, indexed -- the same messages byte for byte', async () => {
    const raw = readRawStream(bytes);
    const packed = await repackRun(bytes, (d) => new Uint8Array(zstdCompressSync(d)));
    expect(packed.byteLength).toBeLessThan(bytes.byteLength);
    const run = await readRun(packed);
    expect(run.profile).toBe('coco');
    expect(run.messages.length).toBe(raw.messages.length);
    const byTime = [...raw.messages].sort((a, b) => (a.logTime < b.logTime ? -1 : a.logTime > b.logTime ? 1 : 0));
    run.messages.forEach((m, i) => {
      expect(m.logTime).toBe(byTime[i].logTime);
      expect(Buffer.from(m.data).equals(Buffer.from(byTime[i].data))).toBe(true);
    });
    expect(run.manifest.evidenceClass).toBe(EvidenceClass.STACK);
  });
});
