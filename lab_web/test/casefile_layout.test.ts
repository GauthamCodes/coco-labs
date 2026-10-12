// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Case Files' layout is lossless (M3 review, decision D6; ADR 0005, amendment D6).
 *
 * M3 committed each Case File with its messages in log-time order. D6 rewrites each so
 * its scans come after everything else, and the first frame draws before they arrive
 * (lab_web/tools/layout_casefiles.mjs, src/arena/case_load.ts).
 * lab_web/casefiles/lossless.json records, for every M3 file, its sha256 and its content
 * digest (mcap.ts contentDigest: per channel, every message's bytes, log time, publish
 * time and sequence, in order, and the channel's schema). Here every Case File must have
 * exactly that digest, hold its scans last, be the file its index names, and its manifest
 * must still cite the source bag.
 */

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { contentDigest, DEFERRED_CHANNELS, readRawStream, readRun, streamCase } from '../src/schemas/mcap';
import { REPO } from './helpers';

const DIR = join(REPO, 'lab_web', 'casefiles');
interface Entry { id: string; bytes: number; sha256: string; bags: string[] }
const index = JSON.parse(readFileSync(join(DIR, 'index.json'), 'utf-8')) as { layout: string; total_bytes: number; casefiles: Entry[] };
const lossless = JSON.parse(readFileSync(join(DIR, 'lossless.json'), 'utf-8')) as {
  casefiles: Record<string, { sha256: string; bytes: number; digest: Record<string, unknown> }> };
const sha = (b: Uint8Array) => createHash('sha256').update(b).digest('hex');
const read = (id: string) => new Uint8Array(readFileSync(join(DIR, `${id}.mcap`)));

describe('the Case Files, laid out for a first frame before the scans (D6)', () => {
  it('are the same 100 Case Files M3 committed, in the ordered layout', () => {
    expect(index.layout).toBe('ordered');
    expect(index.casefiles.map((e) => e.id).sort()).toEqual(Object.keys(lossless.casefiles).sort());
    expect(index.casefiles).toHaveLength(100);
    expect(index.total_bytes).toBe(index.casefiles.reduce((n, e) => n + e.bytes, 0));
  });

  it('every file is the one its index names', () => {
    for (const e of index.casefiles) {
      const b = read(e.id);
      expect(sha(b), e.id).toBe(e.sha256);
      expect(b.byteLength).toBe(e.bytes);
    }
  });

  it('every Case File holds exactly what the adapter wrote (lossless.json; M4.7 re-conversion)', () => {
    for (const e of index.casefiles) {
      expect(contentDigest(readRawStream(read(e.id)), sha), e.id).toEqual(lossless.casefiles[e.id].digest);
    }
  }, 300_000);

  it('every Case File holds its scans after everything else', () => {
    let withScans = 0;
    for (const e of index.casefiles) {
      const r = readRawStream(read(e.id));
      const late = r.messages.map((m) => DEFERRED_CHANNELS.includes(r.channels.get(m.channelId)!.topic));
      const first = late.indexOf(true);
      if (first >= 0) withScans += 1;
      expect(first < 0 || late.slice(first).every(Boolean), e.id).toBe(true);
    }
    expect(withScans).toBeGreaterThan(0);
  }, 300_000);

  it('read as it arrives, a Case File hands over its first frame before its scans', async () => {
    const bytes = read('lab2_rl_fidelity_1_tour');
    let firstAt = -1;
    let given = 0;
    // arrive in 64 KiB pieces, as a network would deliver it
    const body = new ReadableStream<Uint8Array>({
      pull(c) {
        if (given >= bytes.byteLength) { c.close(); return; }
        c.enqueue(bytes.subarray(given, given + 65536)); given += 65536;
      },
    });
    const run = { messages: 0 };
    const scans = await streamCase(body, (r) => { firstAt = Math.min(given, bytes.byteLength); run.messages = r.messages.length; });
    expect(scans.length).toBeGreaterThan(0);
    expect(scans.every((m) => DEFERRED_CHANNELS.includes(m.channel))).toBe(true);
    // the first frame was handed over when well under the whole file had arrived
    expect(firstAt).toBeGreaterThan(0);
    expect(firstAt).toBeLessThan(0.6 * bytes.byteLength);
    const all = (await readRun(bytes)).messages;
    expect(run.messages + scans.length).toBe(all.length);
  });

  it("every Case File's manifest still cites its source bag by sha256", async () => {
    for (const e of index.casefiles) {
      const { manifest } = await readRun(read(e.id));
      const spec = JSON.parse(new TextDecoder().decode(manifest.spec));
      const cited: { bag: string; files: { sha256: string }[] }[] = spec.source.bags ?? [spec.source];
      expect(cited.map((c) => c.bag), e.id).toEqual(e.bags);
      expect(cited.every((c) => c.files.length > 0 && c.files.every((f) => /^[0-9a-f]{64}$/.test(f.sha256)))).toBe(true);
    }
  }, 300_000);
});
