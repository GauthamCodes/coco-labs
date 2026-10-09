// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 2 localisation bundles -> v2 runs (M2.7), and back, with nothing lost.
 *
 * A loc bundle (coco_lab.locbundle: one simulated drive and up to four
 * filters run on it; coco_lab computed everything, so MODEL) becomes one
 * v2 run. World row k is tick k at its own t:
 *
 *   spec                  the bundle's manifest.json, byte for byte
 *   world.grid            the map the filters localised against
 *   truth.pose            the drive's ground truth (world.gt_*)
 *   estimate.pose         "odometry": dead reckoning (world.odom_*); and,
 *                         per filter, its estimate with its covariance
 *                         (estimator = the run id; cov_yaw = cov_tt;
 *                         cov_xt, cov_yt NaN: the bundle has none)
 *   metrics               cmd.v / cmd.w; err_xy.<run>, err_yaw.<run>
 *   sensor.scan.lidar     the scan at every filter update (world.updates are
 *                         its ticks), at full precision in `ranges_f64`
 *   localise.particles.*  MCL: the particle set at every update (f32 in the
 *                         bundle, exact in double) and its bookkeeping
 *   localise.ekf.update   the EKF's beams used, gated and NIS
 *
 * `toLab2` rebuilds every array from the channels and the v1 decoder
 * re-checks the content hash.
 */

import { create, fromBinary, toBinary, type DescMessage } from '@bufbuild/protobuf';

import { encodeBatch, type Column } from '../schemas/columns';
import { ManifestSchema, Tier, EvidenceClass, type Manifest } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import { EstimateBatchSchema } from '../schemas/gen/coco/estimate/v1/estimate_pb';
import { EkfUpdateBatchSchema, FilterHeaderSchema, ParticleSetBatchSchema, ParticleUpdateBatchSchema } from '../schemas/gen/coco/localise/v1/localise_pb';
import { ParamsSchema } from '../schemas/gen/coco/common/v1/common_pb';
import { MetricBatchSchema } from '../schemas/gen/coco/metrics/v1/metrics_pb';
import { ScanBatchSchema } from '../schemas/gen/coco/sensor/v1/scan_pb';
import { TruthPoseBatchSchema } from '../schemas/gen/coco/truth/v1/truth_pb';
import { WorldGridSchema } from '../schemas/gen/coco/world/v1/world_pb';
import { decodeLoc, parseLocManifest, type DecodedLocBundle } from '../loc/decode';
import type { ReadMessage, RunRecord } from '../schemas/mcap';
import { runId, specSha256 } from '../schemas/runid';
import { rawFromColumns } from './raw';

export const SPEC_FORMAT = 'coco_lab.loc_bundle.v1+json';
export const CONVERTER = 'lab_web/src/convert/lab2.ts';
const PER_BATCH = 2048;
export const CH = {
  grid: 'coco.world.grid.v1', truth: 'coco.truth.pose.v1', estimate: 'coco.estimate.pose.v1', metrics: 'coco.metrics.values.v1',
  scan: 'coco.sensor.scan.lidar.v1', mclHeader: 'coco.localise.particles.header.v1', ekfHeader: 'coco.localise.ekf.header.v1', set: 'coco.localise.particles.set.v1',
  pupdate: 'coco.localise.particles.update.v1', ekf: 'coco.localise.ekf.update.v1',
} as const;

export interface Converted { manifest: Manifest; records: RunRecord[] }

const big = (n: number) => BigInt(n);
const nan = (n: number) => new Array(n).fill(NaN);

export async function fromLab2(b: DecodedLocBundle, manifestBytes: Uint8Array): Promise<Converted> {
  const spec = await specSha256(manifestBytes);
  const engines: [string, string][] = [['coco_lab', b.provenance.coco_lab_version], ['converter', `${CONVERTER} 1`]];
  const records: RunRecord[] = [];
  const rec = (channel: string, schema: DescMessage, data: Uint8Array, tWorld: number, seq = 0) => records.push({ channel, schema, data, tWorld, seq });
  const w = b.world;
  const m = b.map;
  rec(CH.grid, WorldGridSchema, toBinary(WorldGridSchema, create(WorldGridSchema, {
    mapId: m.id, width: m.width, height: m.height, resolution: m.geo?.resolution ?? 0, originX: m.geo?.origin[0] ?? 0,
    originY: m.geo?.origin[1] ?? 0, blocked: m.occupancy.map((v) => (v === 0 ? 0 : 1)), occupancy: m.occupancy, cost: [],
    specSha256: spec, row0IsBottom: false })), 0);
  // the drive, in batches of rows
  let mseq = 0;
  for (let s = 0; s < w.nRows; s += PER_BATCH) {
    const e = Math.min(w.nRows, s + PER_BATCH);
    const n = e - s;
    const t = Array.from(w.t.subarray(s, e));
    const clk = { seq: Array.from({ length: n }, (_, i) => big(s + i)), tick: Array.from({ length: n }, (_, i) => big(s + i)), t_world: t };
    rec(CH.truth, TruthPoseBatchSchema, encodeBatch(TruthPoseBatchSchema, { ...clk, x: w.gtX.subarray(s, e), y: w.gtY.subarray(s, e),
      theta: w.gtYaw.subarray(s, e) }), t[0], s);
    rec(CH.estimate, EstimateBatchSchema, encodeBatch(EstimateBatchSchema, { ...clk, x: w.odomX.subarray(s, e), y: w.odomY.subarray(s, e),
      theta: w.odomYaw.subarray(s, e), cov_xx: nan(n), cov_xy: nan(n), cov_xt: nan(n), cov_yy: nan(n), cov_yt: nan(n), cov_tt: nan(n) },
    { estimator: 'odometry' }), t[0], s);
    const idx = Array.from({ length: 2 * n }, (_, i) => i);
    rec(CH.metrics, MetricBatchSchema, encodeBatch(MetricBatchSchema, {
      seq: idx.map((i) => big(mseq + i)), tick: idx.map((i) => big(s + (i >> 1))), t_world: idx.map((i) => t[i >> 1]),
      name: idx.map((i) => (i & 1 ? 'cmd.w' : 'cmd.v')), value: idx.map((i) => (i & 1 ? w.cmdW[s + (i >> 1)] : w.cmdV[s + (i >> 1)])),
      unit: idx.map((i) => (i & 1 ? 'rad/s' : 'm/s')) }), t[0], mseq);
    mseq += 2 * n;
  }
  // the scans, at the updates
  const li = b.scenario.lidar;
  const nb = w.nBeams;
  const inc = nb > 1 ? (li.angle_max - li.angle_min) / (nb - 1) : 0;
  for (let u = 0; u < w.updates.length; u += 1) {
    const k = w.updates[u];
    const r = w.ranges.subarray(u * nb, (u + 1) * nb);
    rec(CH.scan, ScanBatchSchema, encodeBatch(ScanBatchSchema, {
      seq: [big(u)], tick: [big(k)], t_world: [w.t[k]], angle_min: [li.angle_min], angle_increment: [inc],
      range_min: [li.range_min], range_max: [li.range_max], count: [nb], ranges: Array.from(Float32Array.from(r)), ranges_f64: r }), w.t[k], u);
  }
  // the filters
  for (const r of b.runs) {
    rec(r.kind === 'mcl' ? CH.mclHeader : CH.ekfHeader, FilterHeaderSchema, toBinary(FilterHeaderSchema, create(FilterHeaderSchema, {
      filterId: r.id, kind: r.kind, params: create(ParamsSchema, { items: [] }) })), 0);
    const c = r.cols as Record<string, ArrayLike<number>>;
    const rows = Array.from(c.row);
    const t = Array.from(c.t);
    for (let s = 0; s < r.n; s += PER_BATCH) {
      const e = Math.min(r.n, s + PER_BATCH);
      const n = e - s;
      const sl = (name: string) => Array.from({ length: n }, (_, i) => c[name][s + i]);
      const clk = { seq: Array.from({ length: n }, (_, i) => big(s + i)), tick: rows.slice(s, e).map(big), t_world: t.slice(s, e) };
      rec(CH.estimate, EstimateBatchSchema, encodeBatch(EstimateBatchSchema, { ...clk, x: sl('est_x'), y: sl('est_y'), theta: sl('est_yaw'),
        cov_xx: sl('cov_xx'), cov_xy: sl('cov_xy'), cov_xt: nan(n), cov_yy: sl('cov_yy'), cov_yt: nan(n), cov_tt: sl('cov_yaw') },
      { estimator: r.id }), t[s], s);
      const idx = Array.from({ length: 2 * n }, (_, i) => i);
      rec(CH.metrics, MetricBatchSchema, encodeBatch(MetricBatchSchema, {
        seq: idx.map((i) => big(mseq + i)), tick: idx.map((i) => big(rows[s + (i >> 1)])), t_world: idx.map((i) => t[s + (i >> 1)]),
        name: idx.map((i) => (i & 1 ? `err_yaw.${r.id}` : `err_xy.${r.id}`)),
        value: idx.map((i) => (i & 1 ? c.err_yaw[s + (i >> 1)] : c.err_xy[s + (i >> 1)])), unit: idx.map((i) => (i & 1 ? 'rad' : 'm')) }), t[s], mseq);
      mseq += 2 * n;
      if (r.kind === 'mcl') {
        const res = sl('resampled'); const inj = sl('injected');
        if (res.some((v) => v !== 0 && v !== 1) || inj.some((v) => v < 0)) throw new Error(`${r.id}: resampled / injected out of range`);
        rec(CH.pupdate, ParticleUpdateBatchSchema, encodeBatch(ParticleUpdateBatchSchema, { ...clk,
          update: Array.from({ length: n }, (_, i) => big(s + i)), n_eff: sl('n_eff'), resampled: res.map((v) => v === 1),
          injected: inj, p_inject: sl('p_inject'), w_avg: sl('w_avg'), w_slow: sl('w_slow'), w_fast: sl('w_fast'),
          cluster_weight: sl('cluster_weight') } as Record<string, Column>, { filter_id: r.id }), t[s], s);
      } else {
        const z = nan(n);
        rec(CH.ekf, EkfUpdateBatchSchema, encodeBatch(EkfUpdateBatchSchema, { ...clk,
          update: Array.from({ length: n }, (_, i) => big(s + i)),
          pred_x: z, pred_y: z, pred_theta: z, pred_cov_xx: z, pred_cov_xy: z, pred_cov_xt: z, pred_cov_yy: z, pred_cov_yt: z, pred_cov_tt: z,
          post_x: z, post_y: z, post_theta: z, post_cov_xx: z, post_cov_xy: z, post_cov_xt: z, post_cov_yy: z, post_cov_yt: z, post_cov_tt: z,
          beams_used: sl('beams_used'), beams_gated: sl('beams_gated'), nis: sl('nis') }, { filter_id: r.id }), t[s], s);
      }
    }
    const p = r.particles;
    if (p) {
      for (let u = 0; u < r.n; u += 1) {
        const a = p.offset[u]; const z = p.offset[u + 1];
        const n = z - a;
        rec(CH.set, ParticleSetBatchSchema, encodeBatch(ParticleSetBatchSchema, {
          seq: Array.from({ length: n }, (_, i) => big(a + i)), tick: new Array(n).fill(big(rows[u])), t_world: new Array(n).fill(t[u]),
          x: p.x.subarray(a, z), y: p.y.subarray(a, z), theta: p.yaw.subarray(a, z), weight: p.w.subarray(a, z) },
        { update: big(u), filter_id: r.id }), t[u], a);
      }
    }
  }
  const channels = [...new Map(records.map((x) => [x.channel, x.schema.typeName])).entries()].map(([name, message]) => ({ name, message }));
  const manifest = create(ManifestSchema, {
    runId: await runId(manifestBytes, b.scenario.seed, engines), specFormat: SPEC_FORMAT, spec: manifestBytes, specSha256: spec,
    seed: big(b.scenario.seed), tier: Tier.TRACE, evidenceClass: EvidenceClass.MODEL,
    engines: engines.map(([name, version]) => ({ name, version })), channels,
    provenance: { createdUtc: b.provenance.created_utc, tool: CONVERTER, gitSha: b.provenance.git_commit ?? '',
      gitDirty: b.provenance.git_dirty ?? false, source: `coco_lab.loc_bundle ${b.contentHash}`,
      note: 'Lab 2: a Sketch drive and the filters coco_lab ran on it' },
    schemaPackageVersion: '1.0.0',
  });
  return { manifest, records };
}

/** The loc bundle back, from the channels alone: decoded (hash-checked) by the v1 decoder. */
export async function toLab2(manifest: Manifest, messages: ReadMessage[]): Promise<DecodedLocBundle> {
  if (manifest.specFormat !== SPEC_FORMAT) throw new Error(`not a converted Lab 2 bundle: ${manifest.specFormat}`);
  const parsed = parseLocManifest(manifest.spec);
  const on = (ch: string) => messages.filter((x) => x.channel === ch);
  const col: Record<string, number[]> = {};
  const push = (name: string, vals: ArrayLike<number>) => { const a = (col[name] ??= []); for (let i = 0; i < vals.length; i += 1) a.push(vals[i]); };
  const sorted = <T extends { seq: bigint[] }>(ch: string, schema: DescMessage, keep: (b: T) => boolean = () => true) =>
    on(ch).map((x) => fromBinary(schema, x.data) as unknown as T).filter(keep).sort((a, b) => Number(a.seq[0] - b.seq[0]));
  const grid = fromBinary(WorldGridSchema, on(CH.grid)[0].data);
  col['map.occupancy'] = Array.from(grid.occupancy);
  type Tp = { seq: bigint[]; tWorld: number[]; x: number[]; y: number[]; theta: number[] };
  for (const b of sorted<Tp>(CH.truth, TruthPoseBatchSchema)) { push('world.t', b.tWorld); push('world.gt_x', b.x); push('world.gt_y', b.y); push('world.gt_yaw', b.theta); }
  type Es = Tp & { estimator: string; covXx: number[]; covXy: number[]; covYy: number[]; covTt: number[]; tick: bigint[] };
  const ests = on(CH.estimate).map((x) => fromBinary(EstimateBatchSchema, x.data) as unknown as Es);
  for (const b of ests.filter((e) => e.estimator === 'odometry').sort((a, c) => Number(a.seq[0] - c.seq[0]))) {
    push('world.odom_x', b.x); push('world.odom_y', b.y); push('world.odom_yaw', b.theta);
  }
  type Mb = { seq: bigint[]; tick: bigint[]; tWorld: number[]; name: string[]; value: number[] };
  const mets = sorted<Mb>(CH.metrics, MetricBatchSchema);
  for (const b of mets) {
    b.name.forEach((nm, i) => {
      if (nm === 'cmd.v') push('world.cmd_v', [b.value[i]]);
      else if (nm === 'cmd.w') push('world.cmd_w', [b.value[i]]);
      else { const [what, run] = [nm.slice(0, nm.indexOf('.')), nm.slice(nm.indexOf('.') + 1)]; push(`run.${run}.${what}`, [b.value[i]]); }
    });
  }
  type Sc = { seq: bigint[]; tick: bigint[]; rangesF64: number[] };
  for (const b of sorted<Sc>(CH.scan, ScanBatchSchema)) { push('world.updates', b.tick.map(Number)); push('world.ranges', b.rangesF64); }
  for (const b of ests.filter((e) => e.estimator !== 'odometry').sort((a, c) => Number(a.seq[0] - c.seq[0]))) {
    const R = b.estimator;
    push(`run.${R}.row`, b.tick.map(Number)); push(`run.${R}.t`, b.tWorld); push(`run.${R}.est_x`, b.x); push(`run.${R}.est_y`, b.y);
    push(`run.${R}.est_yaw`, b.theta); push(`run.${R}.cov_xx`, b.covXx); push(`run.${R}.cov_xy`, b.covXy);
    push(`run.${R}.cov_yy`, b.covYy); push(`run.${R}.cov_yaw`, b.covTt);
  }
  type Pu = { seq: bigint[]; filterId: string; nEff: number[]; resampled: boolean[]; injected: number[]; pInject: number[]; wAvg: number[];
    wSlow: number[]; wFast: number[]; clusterWeight: number[] };
  for (const b of sorted<Pu>(CH.pupdate, ParticleUpdateBatchSchema)) {
    const R = b.filterId;
    push(`run.${R}.n_eff`, b.nEff); push(`run.${R}.resampled`, b.resampled.map(Number)); push(`run.${R}.injected`, b.injected);
    push(`run.${R}.p_inject`, b.pInject); push(`run.${R}.w_avg`, b.wAvg); push(`run.${R}.w_slow`, b.wSlow); push(`run.${R}.w_fast`, b.wFast);
    push(`run.${R}.cluster_weight`, b.clusterWeight);
  }
  type Ek = { seq: bigint[]; filterId: string; beamsUsed: number[]; beamsGated: number[]; nis: number[] };
  for (const b of sorted<Ek>(CH.ekf, EkfUpdateBatchSchema)) {
    push(`run.${b.filterId}.beams_used`, b.beamsUsed); push(`run.${b.filterId}.beams_gated`, b.beamsGated); push(`run.${b.filterId}.nis`, b.nis);
  }
  type Ps = { seq: bigint[]; filterId: string; update: bigint; x: number[]; y: number[]; theta: number[]; weight: number[] };
  const sets = on(CH.set).map((x) => fromBinary(ParticleSetBatchSchema, x.data) as unknown as Ps);
  for (const R of [...new Set(sets.map((s) => s.filterId))]) {
    const mine = sets.filter((s) => s.filterId === R).sort((a, c) => Number(a.update - c.update));
    let off = 0;
    push(`run.${R}.particles.offset`, [0]);
    for (const s of mine) {
      push(`run.${R}.particles.x`, s.x); push(`run.${R}.particles.y`, s.y); push(`run.${R}.particles.yaw`, s.theta); push(`run.${R}.particles.w`, s.weight);
      off += s.x.length;
      push(`run.${R}.particles.offset`, [off]);
    }
  }
  return decodeLoc(parsed, rawFromColumns(parsed.tree, parsed.total, col));
}
