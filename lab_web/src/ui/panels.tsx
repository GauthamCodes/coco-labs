// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import type { DecodedBundle, ValidatedBy } from '../bundle/model';
import type { CatalogEntry } from '../bundle/load';
import { otherGroups, recordingOverlays } from '../render/overlays';
import { cellCentre } from '../trace/coords';
import { fMeaning, type HoverState } from '../trace/hover';

const LAB1C_CITE = 'docs/RESULTS.md, "COCO Lab Phase 1C" > "The three real runs (measured)"';

/** Display formatting only (6 significant digits); the stored value is untouched. */
function fmt(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(6)));
  if (Array.isArray(v)) return `[${v.map(fmt).join(', ')}]`;
  if (typeof v === 'object') {
    return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k} ${fmt(x)}`).join(' · ');
  }
  return String(v);
}

function Rows({ rows }: { rows: Array<[string, unknown]> }) {
  return (
    <dl className="rows">
      {rows.map(([k, v]) => (
        <div key={k} className="row"><dt>{k}</dt><dd>{fmt(v)}</dd></div>
      ))}
    </dl>
  );
}

function place(b: DecodedBundle, cell: [number, number]): string {
  const rc = `[${cell[0]}, ${cell[1]}]`;
  if (!b.map.geo) return `${rc} (no geo)`;
  const [x, y] = cellCentre(b.map, cell[0], cell[1]);
  return `${rc} · x ${x.toFixed(3)} m, y ${y.toFixed(3)} m`;
}

export function SummaryPanel({ b }: { b: DecodedBundle }) {
  const h = b.trace.header;
  const s = b.trace.summary;
  return (
    <section aria-label="Summary">
      <h3>What was searched</h3>
      <Rows rows={[
        ['algorithm', h.algorithm], ['heuristic', h.heuristic], ['weight', h.weight],
        ['tie-break', h.tie_break], ['f column', fMeaning(h.algorithm, h.weight)],
        ['graph', h.graph], ['move model', b.run.model],
        ['start [row, col]', place(b, b.run.start)], ['goal [row, col]', place(b, b.run.goal)],
        ['map', `${b.map.id || '(unnamed)'} · ${b.map.width} × ${b.map.height}` +
          (b.map.geo ? ` · ${b.map.geo.resolution} m/cell` : ' · no geo') +
          (b.map.cost ? ' · cost layer' : '')],
      ]} />
      <h3>Result, as stored in the trace</h3>
      <Rows rows={[
        ['status', s.status], ['expansions', s.expansions], ['pushes', s.pushes],
        ['relaxes', s.relaxes], ['path cost', s.path_cost], ['path length (cells)', s.path_length],
        ['path steps', s.path_steps], ['events', b.trace.n],
      ]} />
      <p className="note">Values are the bundle's own; this page recomputes none of them.</p>
    </section>
  );
}

export function ProvenancePanel({ b, entry, validated }: {
  b: DecodedBundle; entry: CatalogEntry | null; validated: ValidatedBy;
}) {
  const p = b.provenance;
  return (
    <section aria-label="Provenance">
      <h3>Provenance</h3>
      <Rows rows={[
        ['source kind', p.source_kind], ['tool', p.tool], ['coco_lab version', p.coco_lab_version],
        ['git commit', p.git_commit], ['git dirty', p.git_dirty], ['created (UTC)', p.created_utc],
        ['seed', p.seed], ['episode spec hash', p.episode_spec_hash],
        ['rosbag sha256', p.rosbag?.sha256], ['rosbag sim time',
          p.rosbag ? `${p.rosbag.sim_time_start} – ${p.rosbag.sim_time_end} s` : null],
        ['bundle version', b.version], ['content hash', b.contentHash], ['map hash', b.map.contentHash],
      ]} />
      <h3>Validation</h3>
      <p>
        Decoded and structurally checked in this browser.{' '}
        {validated ? `Semantics validated by ${validated.by === 'catalog'
          ? 'coco_lab when the site was built' : 'coco_lab in this browser'}: ${validated.detail}.`
          : 'Not validated by coco_lab.'}
      </p>
      {entry && <p className="cite">Evidence: {entry.citation}</p>}
    </section>
  );
}

export function RecordingPanel({ b }: { b: DecodedBundle }) {
  const rec = b.recording;
  if (!rec) {
    return <section aria-label="Recording"><p>This bundle carries no recording (it is not a recorded run).</p></section>;
  }
  const m = rec.meta as Record<string, any>;
  const overlays = recordingOverlays(b);
  return (
    <section aria-label="Recording" data-testid="recording-panel">
      <h3>Recorded streams</h3>
      <table className="groups">
        <thead><tr><th>group</th><th>frame</th><th>source</th><th>samples</th><th>on the map</th></tr></thead>
        <tbody>
          {(['gt', 'amcl', 'plan', 'cmd'] as const).map((g) => {
            const info = rec.groups[g];
            const o = overlays.find((x) => x.group === g);
            return (
              <tr key={g}>
                <td>{g}</td>
                <td>{info?.frame ?? '—'}</td>
                <td>{info?.source ?? '—'}</td>
                <td>{info ? info.count : 'not captured'}</td>
                <td>{g === 'cmd' ? 'no (velocities)' : o?.placed ? 'drawn' : (o as { reason?: string })?.reason}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <ul className="notes">{otherGroups(b).map((t) => <li key={t}>{t}</li>)}</ul>
      <h3>Run results, as exported by coco_lab_ros.lab_export</h3>
      <Rows rows={[
        ['run id', rec.runId],
        ['result phase', m.result?.phase], ['error code', m.result?.error_code],
        ['duration (sim s)', m.duration_sim_s], ['window (sim s)', m.window_sim],
        ['tracking error mean / p95 / max (m)', m.tracking_error_m
          ? `${fmt(m.tracking_error_m.mean)} / ${fmt(m.tracking_error_m.p95)} / ${fmt(m.tracking_error_m.max)} (n ${m.tracking_error_m.n})`
          : null],
        ['endpoint error (m)', m.endpoint_error_m],
        ['recoveries', m.recoveries],
        ['synthetic', m.synthetic], ['note', m.note],
      ]} />
      <p className="cite">{m.synthetic ? 'A synthetic decoder fixture, not a run.' : `Evidence: ${LAB1C_CITE}`}</p>
    </section>
  );
}

export function HoverPanel({ b, cell, states }: {
  b: DecodedBundle; cell: [number, number] | null; states: HoverState[];
}) {
  if (!cell) return <section aria-label="Hover"><p>Point at a cell to see its g, h and f.</p></section>;
  const occ = ['free', 'occupied', 'unknown'][b.map.occupancy[cell[0] * b.map.width + cell[1]]];
  const cost = b.map.cost ? b.map.cost[cell[0] * b.map.width + cell[1]] : null;
  return (
    <section aria-label="Hover" data-testid="hover-panel">
      <h3>Cell {place(b, cell)}</h3>
      <p>{occ}{cost !== null ? ` · cost ${fmt(cost)}` : ''}</p>
      {states.length === 0 ? <p>No event has touched this cell yet.</p> : (
        <table className="hover">
          <thead><tr><th>sub</th><th>last event</th><th>g</th><th>h</th><th>f</th></tr></thead>
          <tbody>
            {states.map((s) => (
              <tr key={s.sub}>
                <td>{s.sub}</td><td>{s.kind} #{s.index}</td>
                <td>{fmt(s.g)}</td><td>{fmt(s.h)}</td><td>{fmt(s.f)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="note">{fMeaning(b.trace.header.algorithm, b.trace.header.weight)}; values as stored.</p>
    </section>
  );
}
