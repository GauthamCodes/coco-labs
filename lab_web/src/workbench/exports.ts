// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.6: an experiment's export, one zip: results.csv, summary.json, spec.json,
 * runs.jsonl and manifest.json, every file made by coco_lab.experiments.export in a
 * worker (the same bytes `coco experiment run` writes, but for the manifest's host
 * and the wall-clock column). With traces: each Arena run (control, localisation)
 * re-run tick by tick into its own MCAP file -- JSON messages on
 * /coco/experiment/tick, labelled MODEL -- checked against the run's hash chain; a
 * full task's run adds its game record (replayable: coco_lab.games.play, Play).
 */
import { McapWriter, TempBuffer } from '@mcap/core';
import { Zip, ZipDeflate } from 'three/addons/libs/fflate.module.js';
import type { ExperimentPool, RunRecord } from './pool';
import { worldId, type ExperimentSpec } from './spec';

/** A zip of the given files (deflated), as bytes. */
export function zipFiles(files: Record<string, Uint8Array>): Uint8Array {
  const parts: Uint8Array[] = [];
  let failed: Error | null = null;
  const z = new Zip((err: Error | null, data: Uint8Array) => { if (err) failed = err; else parts.push(data); });
  for (const [name, bytes] of Object.entries(files)) {
    const f = new ZipDeflate(name, { level: 6 });
    z.add(f);
    f.push(bytes, true);
  }
  z.end();
  if (failed) throw failed;
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

export function saveBytes(name: string, bytes: Uint8Array, type = 'application/zip'): void {
  const url = URL.createObjectURL(new Blob([bytes as Uint8Array<ArrayBuffer>], { type }));
  const a = document.createElement('a');
  a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

const TICK_SCHEMA = {
  title: 'coco.experiment.trace.v1', type: 'object', description: 'One tick of a COCO Lab experiment run (MODEL: coco_lab in the browser; not ROS 2, not a robot)',
  properties: { tick: { type: 'integer' }, t: { type: 'number' }, truth: { type: 'array', items: { type: 'number' }, description: 'x, y, yaw (map frame)' },
    v: { type: 'number' }, w: { type: 'number' }, belief: { type: 'array', items: { type: 'number' } }, contact: { type: 'boolean' }, state_hash: { type: 'string' } },
};

/** One run's ticks as an MCAP file (JSON messages; Foxglove opens it). */
export async function traceMcap(ticks: (number | boolean | string)[][], meta: Record<string, string>): Promise<Uint8Array> {
  const buf = new TempBuffer();
  const w = new McapWriter({ writable: buf, chunkSize: 1 << 20 });
  const enc = new TextEncoder();
  await w.start({ profile: '', library: 'COCO Lab Workbench (lab_web/src/workbench/exports.ts) -- MODEL' });
  const schemaId = await w.registerSchema({ name: 'coco.experiment.trace.v1', encoding: 'jsonschema', data: enc.encode(JSON.stringify(TICK_SCHEMA)) });
  const channelId = await w.registerChannel({ topic: '/coco/experiment/tick', schemaId, messageEncoding: 'json', metadata: new Map() });
  let seq = 0;
  for (const r of ticks) {
    const [tick, t, x, y, th, v, wz, bx, by, bth, contact, hash] = r as [number, number, number, number, number, number, number, number, number, number, boolean, string];
    const ns = BigInt(Math.round(t * 1e9));
    await w.addMessage({ channelId, sequence: seq++, logTime: ns, publishTime: ns,
      data: enc.encode(JSON.stringify({ tick, t, truth: [x, y, th], v, w: wz, belief: [bx, by, bth], contact, state_hash: hash })) });
  }
  await w.addMetadata({ name: 'coco', metadata: new Map(Object.entries({ evidence: 'MODEL', ...meta })) });
  await w.end();
  return buf.get();
}

export async function exportZip(pool: ExperimentPool, spec: ExperimentSpec, records: RunRecord[], host: Record<string, unknown>, traces = false): Promise<{ name: string; bytes: Uint8Array; checked?: { traced: number; bad: number[] } }> {
  const text = JSON.stringify(spec), world = worldId(spec);
  const files = await pool.exportFiles(text, world, records, host);
  const enc = new TextEncoder();
  const id = (JSON.parse(files['manifest.json']) as { experiment: string }).experiment;
  const out: Record<string, Uint8Array> = Object.fromEntries(Object.entries(files).map(([k, v]) => [`coco_experiment_${id}/${k}`, enc.encode(v)]));
  let checked: { traced: number; bad: number[] } | undefined;
  if (traces && spec.family !== 'planning') {
    const want = new Map(records.map((r) => [r.index, r]));
    const got = await pool.traces(text, world, records.map((r) => r.index));
    const bad = got.filter((g) => g.chain !== want.get(g.index)?.chain).map((g) => g.index);
    for (const g of got) {
      const base = `coco_experiment_${id}/runs/run_${String(g.index).padStart(5, '0')}`;
      if (g.ticks.length) out[`${base}.mcap`] = await traceMcap(g.ticks, { experiment: id, run: String(g.index), status: g.status, chain: g.chain });
      if (g.record) out[`${base}.record.json`] = enc.encode(JSON.stringify(g.record) + '\n');
    }
    checked = { traced: got.length, bad };
  }
  return { name: `coco_experiment_${id}${traces ? '_traces' : ''}.zip`, bytes: zipFiles(out), checked };
}

export async function downloadExport(pool: ExperimentPool, spec: ExperimentSpec, records: RunRecord[], host: Record<string, unknown>, traces: boolean): Promise<void> {
  const z = await exportZip(pool, spec, records, host, traces);
  if (z.checked?.bad.length) throw new Error(`traces of runs ${z.checked.bad.join(', ')} did not reproduce their hash chains; nothing saved`);
  saveBytes(z.name, z.bytes);
}
