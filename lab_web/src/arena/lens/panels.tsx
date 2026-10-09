// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The lens UI (M2.2): the lens bar (one tab per lens, the disclosure level,
 * Focus), the Inspect-level inspector templates per family, the event log
 * and metric charts. Charts appear only at Inspect, or when a mission asks
 * for one (`forceCharts`). Everything shown is a value the model emitted.
 */

import { LENSES, LEVEL_TITLES, LEVELS, type Lens, type LensId, type Level } from './registry';
import { familyOf, type FamilyBatch, type FamilyStore, type MetricPoint } from './store';

export function LensBar({ lens, level, focus, available, onLens, onLevel, onFocus }: {
  lens: LensId; level: Level; focus: boolean; available: Set<LensId>;
  onLens: (l: LensId) => void; onLevel: (l: Level) => void; onFocus: (f: boolean) => void;
}) {
  return (
    <div className="lens-bar" role="toolbar" aria-label="Lenses" data-testid="lens-bar">
      <div className="arena-row" role="tablist" aria-label="Lens">
        {LENSES.map((l) => (
          <button key={l.id} type="button" role="tab" aria-selected={l.id === lens}
            className={l.id === lens ? 'seg-btn active' : 'seg-btn'} data-testid={`lens-${l.id}`}
            title={available.has(l.id) ? l.question : `${l.question} (arrives in ${l.since})`}
            onClick={() => onLens(l.id)}>{l.title}</button>
        ))}
      </div>
      <div className="arena-row" role="group" aria-label="Detail">
        {LEVELS.map((v) => (
          <button key={v} type="button" className={v === level ? 'seg-btn active' : 'seg-btn'} aria-pressed={v === level}
            data-testid={`level-${v}`} onClick={() => onLevel(v)}>{LEVEL_TITLES[v]}</button>
        ))}
        <label className="layer-toggle" title="Dim everything outside this lens">
          <input type="checkbox" checked={focus} onChange={(e) => onFocus(e.target.checked)} data-testid="focus-toggle" />Focus
        </label>
      </div>
    </div>
  );
}

const fmt = (v: unknown, d = 3) => (typeof v === 'number' ? (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(d))
  : typeof v === 'bigint' ? v.toString() : v === undefined || v === null ? '—' : String(v));
const col = (b: FamilyBatch | null, k: string, i = 0) => {
  const c = b?.columns[k] as ArrayLike<unknown> | undefined;
  return c && c.length > i ? c[i] : undefined;
};
const last = (b: FamilyBatch | null, k: string) => {
  const c = b?.columns[k] as ArrayLike<unknown> | undefined;
  return c && c.length ? c[c.length - 1] : undefined;
};

/** One inspector template per family: the latest batch's values at the shown tick. */
function rows(family: string, b: FamilyBatch): [string, string][] {
  switch (family) {
    case 'estimate':
      return [[`${b.scalars.estimator} pose`, `(${fmt(last(b, 'x'))}, ${fmt(last(b, 'y'))}) m, θ ${fmt(last(b, 'theta'))} rad`],
        ['σx, σy', `${fmt(Math.sqrt(Number(last(b, 'cov_xx'))))} m, ${fmt(Math.sqrt(Number(last(b, 'cov_yy'))))} m`],
        ['σθ', `${fmt(Math.sqrt(Number(last(b, 'cov_tt'))))} rad`]];
    case 'localise.particles':
      if (b.channel.endsWith('.update.v1')) {
        return [['update', fmt(last(b, 'update'))], ['effective sample size', fmt(last(b, 'n_eff'), 1)],
          ['resampled', String(last(b, 'resampled'))], ['injected', fmt(last(b, 'injected'))],
          ['p(inject)', fmt(last(b, 'p_inject'))], ['w_slow / w_fast', `${fmt(last(b, 'w_slow'), 4)} / ${fmt(last(b, 'w_fast'), 4)}`]];
      }
      return [['particles', fmt((b.columns.x as ArrayLike<number>).length)], ['update', fmt(b.scalars.update)]];
    case 'localise.ekf':
      return [['update', fmt(last(b, 'update'))], ['beams used / gated', `${fmt(last(b, 'beams_used'))} / ${fmt(last(b, 'beams_gated'))}`],
        ['NIS', fmt(last(b, 'nis'))], ['predicted σx', fmt(Math.sqrt(Number(last(b, 'pred_cov_xx'))))],
        ['posterior σx', fmt(Math.sqrt(Number(last(b, 'post_cov_xx'))))]];
    case 'map.grid':
      return [['map', String(b.scalars.map_id ?? '—')], ['update', fmt(b.scalars.update)],
        ['cells changed', fmt((b.columns.seq as ArrayLike<unknown>).length)]];
    case 'map.slam':
      if (b.channel.endsWith('.landmarks.v1')) return [['landmarks', fmt((b.columns.x as ArrayLike<number>).length)], ['update', fmt(b.scalars.update)]];
      if (b.channel.endsWith('.particles.v1')) return [['particles', fmt((b.columns.x as ArrayLike<number>).length)], ['best', fmt(b.scalars.best)]];
      if (b.channel.endsWith('.nodes.v1')) return [['nodes', fmt((b.columns.x as ArrayLike<number>).length)], ['stage', String(b.scalars.stage)], ['chi²', fmt(b.scalars.chi2)]];
      return [['edges', fmt((b.columns.seq as ArrayLike<unknown>).length)], ['stage', String(b.scalars.stage)]];
    case 'control.local':
      if (b.channel.endsWith('.command.v1')) {
        return [['controller', String(b.scalars.controller_id)], ['cycle', fmt(last(b, 'cycle'))], ['status', String(last(b, 'status'))],
          ['candidates (valid)', `${fmt(last(b, 'n_candidates'))} (${fmt(last(b, 'n_valid'))})`],
          ['chosen', fmt(last(b, 'chosen'))], ['command', `v ${fmt(last(b, 'v'))} m/s, ω ${fmt(last(b, 'w'))} rad/s`]];
      }
      {
        const rej = b.columns.rejection as string[];
        const tally = new Map<string, number>();
        for (const r of rej) if (r) tally.set(r, (tally.get(r) ?? 0) + 1);
        return [['candidates', fmt(rej.length)], ['rejected', [...tally].map(([k, n]) => `${k} ×${n}`).join(', ') || 'none']];
      }
    case 'decide.search':
      if (b.channel.endsWith('.belief.v1')) {
        const p = b.columns.probability as ArrayLike<number>;
        return [...Array.from(p, (v, i): [string, string] => [`bay ${i}`, `${(100 * v).toFixed(1)} %`])];
      }
      if (b.channel.endsWith('.action.v1')) return [['chosen bay', fmt(last(b, 'region'))], ['expected cost', fmt(last(b, 'expected_cost'))], ['why', String(last(b, 'reason'))]];
      if (b.channel.endsWith('.observation.v1')) return [['looked in bay', fmt(last(b, 'region'))], ['found', String(last(b, 'found'))]];
      return [['orders considered', fmt((b.columns.order_len as ArrayLike<number>).length)]];
    case 'sensor.detect':
      return [['looked at', String(last(b, 'region_id'))], ['colour', String(last(b, 'colour'))], ['detected', String(last(b, 'detected'))],
        ['detection probability', `${fmt(b.scalars.detection_probability, 2)} (${b.scalars.detection_label})`]];
    case 'mission.fsm':
      return [['state', String(last(b, 'to_state'))], ['from', String(last(b, 'from_state'))], ['event', String(last(b, 'event'))], ['why', String(last(b, 'reason'))]];
    case 'arm':
      return [['phase', String(last(b, 'phase'))], ['joints', `${fmt(last(b, 'joint1'))}, ${fmt(last(b, 'joint2'))} rad`],
        ['fingers', `${fmt(last(b, 'finger_left'))}, ${fmt(last(b, 'finger_right'))} rad`],
        ['magnet', last(b, 'magnet_on') ? 'on' : 'off'], ['holding (magnet)', last(b, 'holding') ? 'yes' : 'no']];
    default:
      return [['rows', fmt((b.columns.seq as ArrayLike<unknown> | undefined)?.length ?? 0)]];
  }
}

export function LensInspector({ lens, store, tick }: { lens: Lens; store: FamilyStore; tick: number }) {
  const shown: FamilyBatch[] = [];
  for (const c of store.channels().filter((x) => lens.families.includes(familyOf(x)))) {
    const b = store.latest(c, tick);
    if (!b) continue;
    // several estimators share a channel: every one emitted at that tick
    if (c === 'coco.estimate.pose.v1') shown.push(...store.at(c, b.tick)); else shown.push(b);
  }
  if (!shown.length) return <p className="lens-empty" data-testid="lens-inspector-empty">Nothing from the {lens.title} lens yet{lens.since !== 'M1' ? ` (its live computation arrives in ${lens.since})` : ''}.</p>;
  return (
    <div className="lens-inspector" data-testid="lens-inspector">
      {shown.map((b, i) => (
        <section key={`${b.channel}-${i}`} className="inspector-group" data-channel={b.channel}>
          <h4>{b.channel.replace(/^coco\./, '').replace(/\.v\d+$/, '')} <span className="tick">tick {b.tick}</span></h4>
          <dl className="inspector">
            {rows(familyOf(b.channel), b).flatMap(([k, v]) => [<dt key={`${k}-k`}>{k}</dt>, <dd key={`${k}-v`}>{v}</dd>])}
          </dl>
        </section>
      ))}
    </div>
  );
}

export function EventLog({ lens, store, tick }: { lens: Lens; store: FamilyStore; tick: number }) {
  const chans = store.channels().filter((c) => lens.families.includes(familyOf(c)));
  const recent = store.recent(chans, tick, 12);
  return (
    <ol className="event-log" data-testid="event-log" aria-label={`${lens.title} events`}>
      {recent.map((b, i) => (
        <li key={`${b.channel}-${b.tick}-${i}`}><span className="tick">t{b.tick}</span> {b.channel.replace(/^coco\./, '').replace(/\.v\d+$/, '')}
          {' · '}{(b.columns.seq as ArrayLike<unknown> | undefined)?.length ?? 0} rows
          {col(b, 'status') ? ` · ${col(b, 'status')}` : ''}{col(b, 'reason') ? ` · ${col(b, 'reason')}` : ''}</li>
      ))}
    </ol>
  );
}

/** A metric's series as an SVG line, with its range labelled. */
export function MetricChart({ name, points, unit = '' }: { name: string; points: MetricPoint[]; unit?: string }) {
  const W = 260; const H = 72;
  if (points.length < 2) return <figure className="metric-chart" data-testid={`chart-${name}`}><figcaption>{name}: not enough values yet</figcaption></figure>;
  const t0 = points[0].tick; const t1 = points.at(-1)!.tick || 1;
  let lo = Infinity; let hi = -Infinity;
  for (const p of points) { if (Number.isFinite(p.value)) { lo = Math.min(lo, p.value); hi = Math.max(hi, p.value); } }
  if (!(hi > lo)) { hi = lo + 1; }
  const d = points.filter((p) => Number.isFinite(p.value)).map((p, i) => `${i ? 'L' : 'M'}${((p.tick - t0) / Math.max(1, t1 - t0)) * W},${H - ((p.value - lo) / (hi - lo)) * H}`).join(' ');
  return (
    <figure className="metric-chart" data-testid={`chart-${name}`}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={`${name} over time`}><path d={d} fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
      <figcaption>{name}{unit ? ` (${unit})` : ''}: {lo.toFixed(3)} – {hi.toFixed(3)}, latest {points.at(-1)!.value.toFixed(3)}</figcaption>
    </figure>
  );
}

export function LensCharts({ lens, store, tick, force }: { lens: Lens; store: FamilyStore; tick: number; force?: string[] }) {
  const names = force ?? lens.charts;
  return (
    <div className="lens-charts" data-testid="lens-charts">
      {names.map((n) => <MetricChart key={n} name={n} points={store.series(n, tick)} />)}
    </div>
  );
}
