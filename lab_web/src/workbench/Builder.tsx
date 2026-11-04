// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1: the experiment builder -- a form and, beside it, the same spec as JSON or YAML
 * text that can be edited directly. The form never validates on its own beyond
 * shapes: the worker's coco_lab.experiments.plan is the authority, and its refusal
 * (with the reason) is shown as is.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  applies, COMMON_PARAMS, defaultSpec, FAMILY_LABEL, heavy, label, META, runCount, worldId, worldOf,
  type AlgorithmSpec, type ExperimentSpec, type Family, type ParamDef, type Scenarios,
} from './spec';

const num = (v: string) => (v.trim() === '' ? NaN : Number(v));
const isPhone = () => typeof matchMedia !== 'undefined' && matchMedia('(pointer: coarse)').matches && Math.min(screen.width, screen.height) < 600;

function ParamInput({ k, def, value, onChange }: { k: string; def: ParamDef; value: unknown; onChange: (v: number | string | number[] | undefined) => void }) {
  const id = `p-${k}`;
  const shown = value === undefined ? '' : Array.isArray(value) ? value.join(', ') : String(value);
  const placeholder = Array.isArray(def.default) ? def.default.join(', ') : String(def.default);
  if (def.choices) {
    return <label htmlFor={id}>{k}<select id={id} value={shown} onChange={(e) => onChange(e.target.value === '' ? undefined : def.type === 'str' ? e.target.value : Number(e.target.value))}>
      <option value="">default ({placeholder})</option>{def.choices.map((c) => <option key={String(c)} value={String(c)}>{String(c)}</option>)}</select></label>;
  }
  return <label htmlFor={id} title={def.doc || undefined}>{k}<input id={id} inputMode={def.type === 'str' ? 'text' : 'decimal'} value={shown} placeholder={placeholder}
    onChange={(e) => {
      const t = e.target.value;
      if (t.trim() === '') return onChange(undefined);
      if (def.type === 'list') return onChange(t.split(',').map((x) => Number(x.trim())));
      if (def.type === 'str') return onChange(t);
      onChange(num(t));
    }} /></label>;
}

function AlgorithmRow({ family, a, index, onChange, onRemove }: { family: Family; a: AlgorithmSpec; index: number; onChange: (a: AlgorithmSpec) => void; onRemove?: () => void }) {
  const table = META.params[family];
  const keys = Object.keys(table).filter((k) => applies(family, a.name, k));
  const common = keys.filter((k) => COMMON_PARAMS[family].includes(k));
  const rest = keys.filter((k) => !common.includes(k));
  const set = (k: string, v: number | string | number[] | undefined) => {
    const params = { ...(a.params ?? {}) };
    if (v === undefined) delete params[k]; else params[k] = v;
    onChange({ ...a, params });
  };
  return <fieldset className="wb-algo">
    <legend>Algorithm {index + 1}</legend>
    <div className="wb-row">
      <label>Algorithm<select value={a.name} onChange={(e) => onChange({ name: e.target.value, id: a.id, label: a.label })}>
        {META.algorithms[family].map((n) => <option key={n} value={n}>{label(n)}</option>)}</select></label>
      <label>Name in results<input value={a.id ?? ''} placeholder={a.name} onChange={(e) => onChange({ ...a, id: e.target.value || undefined })} /></label>
      {onRemove && <button type="button" onClick={onRemove} aria-label={`Remove algorithm ${index + 1}`}>Remove</button>}
    </div>
    {common.length > 0 && <div className="wb-params">{common.map((k) => <ParamInput key={k} k={k} def={table[k]} value={a.params?.[k]} onChange={(v) => set(k, v)} />)}</div>}
    {rest.length > 0 && <details><summary>All {keys.length} parameters</summary><div className="wb-params">{rest.map((k) => <ParamInput key={k} k={k} def={table[k]} value={a.params?.[k]} onChange={(v) => set(k, v)} />)}</div></details>}
    {family === 'fulltask' && <p className="wb-muted">The planner drives the reference bot's route; Grasp Assist's approach planning stays A*, as in Play.</p>}
  </fieldset>;
}

function ScenarioEditor({ spec, onChange }: { spec: ExperimentSpec; onChange: (s: Scenarios) => void }) {
  const sc = spec.scenarios;
  const w = worldOf(worldId(spec));
  if (spec.family === 'fulltask') {
    const game = sc.kind === 'rounds' ? sc.game : 'fetch_colour';
    const ft = META.fulltask;
    return <fieldset><legend>Scenarios: committed rounds</legend>
      <label>Game<select value={game} onChange={(e) => onChange(e.target.value === 'fetch_rush' ? { kind: 'rounds', game: 'fetch_rush' } : { kind: 'rounds', game: 'fetch_colour', colours: ft.fetch_colour.colours })}>
        <option value="fetch_colour">Fetch by colour (rules {ft.fetch_colour.rules})</option><option value="fetch_rush">Fetch Rush (rules {ft.fetch_rush.rules})</option></select></label>
      {game === 'fetch_colour' && sc.kind === 'rounds' && <div className="wb-checks" role="group" aria-label="Rods">{ft.fetch_colour.colours.map((c) => {
        const on = (sc.colours ?? ft.fetch_colour.colours).includes(c);
        return <label key={c} className="wb-check"><input type="checkbox" checked={on} onChange={() => {
          const cur = sc.colours ?? ft.fetch_colour.colours; onChange({ ...sc, colours: on ? cur.filter((x) => x !== c) : [...cur, c] });
        }} />{c}</label>;
      })}</div>}
      {game === 'fetch_rush' && sc.kind === 'rounds' && <div className="wb-checks" role="group" aria-label="Rounds">{ft.fetch_rush.modes.flatMap((m) => ft.fetch_rush.seeds.map((s) => {
        const all = ft.fetch_rush.modes.flatMap((mm) => ft.fetch_rush.seeds.map((ss) => ({ seed: ss, mode: mm })));
        const cur = sc.rounds ?? all;
        const on = cur.some((r) => r.seed === s && r.mode === m);
        return <label key={m + s} className="wb-check"><input type="checkbox" checked={on} onChange={() => onChange({ ...sc, rounds: on ? cur.filter((r) => !(r.seed === s && r.mode === m)) : [...cur, { seed: s, mode: m }] })} />{m} {s}</label>;
      }))}</div>}
      <p className="wb-muted">R1 v0 plays the committed rounds only: Fetch Rush seeds 1–6 in phone and full mode, and the four rods.</p>
    </fieldset>;
  }
  const suites = META.suites.filter((s) => s.world === spec.world && s.families.includes(spec.family));
  return <fieldset><legend>Scenarios</legend>
    <div className="wb-row" role="radiogroup" aria-label="Scenario source">
      {(['sampled', 'suite', 'pairs'] as const).map((k) => <label key={k} className="wb-check"><input type="radio" name="sc-kind" checked={sc.kind === k} disabled={k === 'suite' && !suites.length}
        onChange={() => onChange(k === 'sampled' ? { kind: 'sampled', n: 20, seed: spec.seed ?? 1, min_separation_m: 3 } : k === 'suite' ? { kind: 'suite', id: suites[0].id } : { kind: 'pairs', pairs: [] })} />
        {{ sampled: 'Seeded random pairs', suite: 'Benchmark suite', pairs: 'Hand-placed pairs' }[k]}</label>)}
    </div>
    {sc.kind === 'sampled' && <><div className="wb-row">
      <label>Pairs (N)<input inputMode="numeric" value={sc.n} onChange={(e) => onChange({ ...sc, n: num(e.target.value) })} /></label>
      <label>Scenario seed<input inputMode="numeric" value={sc.seed ?? spec.seed ?? 1} onChange={(e) => onChange({ ...sc, seed: num(e.target.value) })} /></label>
      <label>Min separation (m)<input inputMode="decimal" value={sc.min_separation_m ?? 2} onChange={(e) => onChange({ ...sc, min_separation_m: num(e.target.value) })} /></label>
      <label>Min clearance (m)<input inputMode="decimal" value={sc.min_clearance_m ?? 0.35} onChange={(e) => onChange({ ...sc, min_clearance_m: num(e.target.value) })} /></label>
    </div>
      {w && Object.keys(w.regions).length > 0 && <div className="wb-checks" role="group" aria-label="Zones">
        <span className="wb-muted">Zones (none = anywhere):</span>
        {Object.keys(w.regions).map((z) => { const on = (sc.zones ?? []).includes(z);
          return <label key={z} className="wb-check"><input type="checkbox" checked={on} onChange={() => { const cur = sc.zones ?? []; const next = on ? cur.filter((x) => x !== z) : [...cur, z]; onChange({ ...sc, zones: next.length ? next : null }); }} />{z.replace('zone_', '').replace(/_/g, ' ')}</label>; })}
        <label className="wb-check"><input type="checkbox" checked={sc.stratify === 'zone'} onChange={(e) => onChange({ ...sc, stratify: e.target.checked ? 'zone' : 'none' })} />stratify by start zone</label>
      </div>}
      <label className="wb-check"><input type="checkbox" checked={sc.require_reachable !== false} onChange={(e) => onChange({ ...sc, require_reachable: e.target.checked })} />only pairs connected on the planning grid (rejections are counted and reported)</label>
    </>}
    {sc.kind === 'suite' && <label>Suite<select value={sc.id} onChange={(e) => onChange({ kind: 'suite', id: e.target.value })}>{suites.map((s) => <option key={s.id} value={s.id}>{s.id} v{s.version} · {s.n} scenarios</option>)}</select></label>}
    {sc.kind === 'pairs' && <label>One pair per line: start x, start y, [heading], goal x, goal y (metres, map frame)
      <textarea rows={5} value={sc.pairs.map((p) => [...p.start, ...p.goal].join(', ')).join('\n')} onChange={(e) => onChange({ kind: 'pairs', pairs: e.target.value.split('\n').map((ln) => ln.split(',').map((x) => Number(x.trim()))).filter((v) => v.length === 4 || v.length === 5).map((v) => v.length === 4 ? { start: [v[0], v[1], 0], goal: [v[2], v[3]] } : { start: [v[0], v[1], v[2]], goal: [v[3], v[4]] }) })} /></label>}
  </fieldset>;
}

function SweepEditor({ spec, onChange }: { spec: ExperimentSpec; onChange: (s: ExperimentSpec['sweep']) => void }) {
  const params = spec.sweep?.params ?? [];
  const keys = Object.keys(META.params[spec.family]).filter((k) => spec.algorithms.some((a) => applies(spec.family, a.name, k)) && META.params[spec.family][k].type !== 'list' && META.params[spec.family][k].type !== 'str');
  if (!keys.length) return null;
  const set = (i: number, p: { name: string; values: (number | string)[] } | null) => {
    const next = [...params];
    if (p === null) next.splice(i, 1); else next[i] = p;
    onChange(next.length ? { params: next } : undefined);
  };
  return <fieldset><legend>Parameter sweep (optional)</legend>
    {params.map((p, i) => <div className="wb-row" key={i}>
      <label>Parameter {i + 1}<select value={p.name} onChange={(e) => set(i, { ...p, name: e.target.value })}>{keys.map((k) => <option key={k}>{k}</option>)}</select></label>
      <label>Values (comma-separated)<input value={p.values.join(', ')} onChange={(e) => set(i, { ...p, values: e.target.value.split(',').map((x) => Number(x.trim())).filter((x) => Number.isFinite(x)) })} /></label>
      <button type="button" onClick={() => set(i, null)}>Remove</button>
    </div>)}
    {params.length < 2 && <button type="button" onClick={() => { const k = keys[0]; const d = Number(META.params[spec.family][k].default); set(params.length, { name: k, values: [d * 0.8, d, d * 1.2].map((x) => +x.toPrecision(3)) }); }}>Add a swept parameter</button>}
    <p className="wb-muted">One parameter gives a line with its IQR band; two give a heatmap. A swept value overrides that parameter for every algorithm it applies to.</p>
  </fieldset>;
}

export function Builder({ spec, onSpec, onRun, running, error }: { spec: ExperimentSpec; onSpec: (s: ExperimentSpec) => void; onRun: () => void; running: boolean; error: string }) {
  const [text, setText] = useState('');
  const [format, setFormat] = useState<'json' | 'yaml'>('json');
  const [textError, setTextError] = useState('');
  useEffect(() => {
    let alive = true;
    if (format === 'json') setText(JSON.stringify(spec, null, 2));
    else void import('yaml').then((y) => { if (alive) setText(y.stringify(spec)); });
    return () => { alive = false; };
  }, [spec, format]);
  const apply = async () => {
    try {
      const parsed = format === 'json' ? JSON.parse(text) : (await import('yaml')).parse(text);
      if (!parsed || parsed.schema !== 'coco.experiment.v1') throw new Error('the spec needs "schema": "coco.experiment.v1"');
      setTextError(''); onSpec(parsed as ExperimentSpec);
    } catch (e) { setTextError(String((e as Error).message)); }
  };
  const phone = useMemo(isPhone, []);
  const load = heavy(spec, phone);
  const family = spec.family;
  const setAlgo = (i: number, a: AlgorithmSpec) => onSpec({ ...spec, algorithms: spec.algorithms.map((x, j) => (j === i ? a : x)) });
  return <section className="wb-builder" aria-label="Experiment builder">
    <form className="wb-form" onSubmit={(e) => { e.preventDefault(); onRun(); }}>
      <div className="wb-row">
        <label className="wb-grow">Title<input value={spec.title ?? ''} onChange={(e) => onSpec({ ...spec, title: e.target.value })} /></label>
        <label>Family<select value={family} onChange={(e) => onSpec(defaultSpec(e.target.value as Family))}>{META.families.map((f) => <option key={f} value={f}>{FAMILY_LABEL[f]}</option>)}</select></label>
        {family !== 'fulltask' && <label>World<select value={spec.world} onChange={(e) => onSpec({ ...spec, world: e.target.value, scenarios: spec.scenarios.kind === 'suite' ? { kind: 'sampled', n: 20, seed: 1 } : spec.scenarios.kind === 'sampled' ? { ...spec.scenarios, zones: null, stratify: 'none' } : spec.scenarios })}>
          {META.worlds.map((w) => <option key={w.id} value={w.id}>{w.title}</option>)}</select></label>}
        <label>Experiment seed<input inputMode="numeric" value={spec.seed ?? 1} onChange={(e) => onSpec({ ...spec, seed: num(e.target.value) })} /></label>
      </div>
      {spec.algorithms.map((a, i) => <AlgorithmRow key={i} family={family} a={a} index={i} onChange={(x) => setAlgo(i, x)} onRemove={spec.algorithms.length > 1 ? () => onSpec({ ...spec, algorithms: spec.algorithms.filter((_, j) => j !== i) }) : undefined} />)}
      {spec.algorithms.length < META.limits.algorithms && <button type="button" onClick={() => onSpec({ ...spec, algorithms: [...spec.algorithms, { name: META.algorithms[family].find((n) => !spec.algorithms.some((a) => a.name === n)) ?? META.algorithms[family][0] }] })}>Add an algorithm</button>}
      <ScenarioEditor spec={spec} onChange={(s) => onSpec({ ...spec, scenarios: s })} />
      <SweepEditor spec={spec} onChange={(s) => { const next = { ...spec }; if (s) next.sweep = s; else delete next.sweep; onSpec(next); }} />
      {(family === 'control' || family === 'localisation') && <div className="wb-row">
        <label>Time limit (ticks of 0.1 s)<input inputMode="numeric" value={spec.limits?.max_ticks ?? 3000} onChange={(e) => onSpec({ ...spec, limits: { max_ticks: num(e.target.value) } })} /></label>
        {family === 'localisation' && <label>Kidnap at (s; empty = none)<input inputMode="decimal" value={spec.options?.kidnap_at_s ?? ''} onChange={(e) => onSpec({ ...spec, options: e.target.value.trim() ? { kidnap_at_s: num(e.target.value) } : {} })} /></label>}
      </div>}
      <div className="wb-runbar">
        <button type="submit" className="wb-primary" disabled={running}>{running ? 'Running…' : `Run ${runCount(spec)} runs`}</button>
        {load.warn && <p className="wb-warn" role="note">{load.reason}</p>}
      </div>
      {error && <p role="alert" className="wb-error">{error}</p>}
    </form>
    <details className="wb-text" open={false}>
      <summary>Edit as {format.toUpperCase()}</summary>
      <div className="wb-row" role="radiogroup" aria-label="Text format">
        {(['json', 'yaml'] as const).map((f) => <label key={f} className="wb-check"><input type="radio" name="wb-format" checked={format === f} onChange={() => setFormat(f)} />{f.toUpperCase()}</label>)}
      </div>
      <textarea aria-label={`Experiment spec as ${format.toUpperCase()}`} spellCheck={false} rows={18} value={text} onChange={(e) => setText(e.target.value)} />
      <button type="button" onClick={() => void apply()}>Apply the text</button>
      {textError && <p role="alert" className="wb-error">{textError}</p>}
    </details>
  </section>;
}
