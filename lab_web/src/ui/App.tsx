// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { BundleError } from '../bundle/errors';
import {
  fetchBundle, requireValidated, type BundleFiles, type Catalog, type CatalogEntry,
} from '../bundle/load';
import type { DecodedBundle, ValidatedBy } from '../bundle/model';
import { coversEndpoint, endpointRefusal, type Tool } from '../lab/brush';
import { sweptFootprint } from '../lab/footprint';
import { settingsLocked, settingsOf, toRun, type SearchSettings } from '../lab/settings';
import { HoverIndex } from '../trace/hover';
import { pathCells } from '../trace/cursor';
import type { Stroke } from '../worker/protocol';
import { LabStatusLine, useLab } from './Editor';
import { Ladder } from './Ladder';
import { MapView } from './MapView';
import { ModeBadge } from './ModeBadge';
import { HoverPanel, ProvenancePanel, RecordingPanel, SummaryPanel } from './panels';
import { perfMark } from './perf';
import { Player } from './Player';
import { RaceSetup, RaceView } from './Race';
import { SettingsPanel } from './SettingsPanel';
import { Tools } from './Tools';

const BASE = import.meta.env.BASE_URL; // from site.config.ts via vite.config.ts

// Panels whose props do not change with the playback cursor: memoised, so a
// playback tick re-renders only the map and the player (measured: without
// this, Part A dropped 1-2 frames per full-arena playback that 1D did not)
const LadderM = memo(Ladder);
const SettingsPanelM = memo(SettingsPanel);
const RaceSetupM = memo(RaceSetup);
const ToolsM = memo(Tools);
const DATA = `${BASE}generated/`;

/** A loaded bundle, and how we know it may be drawn. */
export interface Current {
  entry: CatalogEntry | null; // null for a bundle the worker just produced
  bundle: DecodedBundle;
  files: BundleFiles;
  validated: NonNullable<ValidatedBy>;
}

/** A catalog bundle, or one coco_lab just computed in the worker. */
export type BundleRef = { catalogId: string } | { worker: true };

type Tab = 'summary' | 'provenance' | 'recording' | 'hover';

function useReducedMotion(): boolean {
  const q = '(prefers-reduced-motion: reduce)';
  const [reduced, setReduced] = useState(() => window.matchMedia?.(q).matches ?? false);
  useEffect(() => {
    const m = window.matchMedia?.(q);
    if (!m) return;
    const on = () => setReduced(m.matches);
    m.addEventListener('change', on);
    return () => m.removeEventListener('change', on);
  }, []);
  return reduced;
}

export function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selection, setSelection] = useState<BundleRef[]>([]);
  const [current, setCurrent] = useState<Current | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [k, setK] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(100);
  const [hover, setHover] = useState<[number, number] | null>(null);
  const [tab, setTab] = useState<Tab>('summary');
  const [settings, setSettings] = useState<SearchSettings | null>(null);
  const [tool, setTool] = useState<Tool>('look');
  const [brush, setBrush] = useState(1);
  const [sweep, setSweep] = useState(true);
  const [raceChosen, setRaceChosen] = useState<string[]>(['dijkstra', 'astar']);
  const [race, setRace] = useState<{ entrants: Current[]; optimalCost: number | null } | null>(null);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    perfMark('app-start');
    fetch(`${DATA}catalog.json`, { credentials: 'omit', cache: 'no-cache' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((c: Catalog) => {
        setCatalog(c);
        const params = new URLSearchParams(window.location.search);
        const first = c.bundles.find((b) => b.id === params.get('bundle')) ?? c.bundles[0];
        if (first) setSelection([{ catalogId: first.id }]);
      })
      .catch((exc: Error) => setError({ code: 'fetch', message: `cannot load the catalog: ${exc.message}` }));
  }, []);

  const show = useCallback((c: Current) => {
    setCurrent(c);
    setError(null);
    setPlaying(false);
    setHover(null);
    setK(c.bundle.trace.n); // show the finished search; play restarts from 0
    setSettings(settingsOf(c.bundle));
  }, []);
  // after an edit the drawn bundle is no catalog entry: say so in the picker
  const showEdited = useCallback((c: Current) => {
    setSelection([{ worker: true }]);
    setRace(null);
    show(c);
  }, [show]);
  const { status: editStatus, setStatus: setEditStatus, run } = useLab(catalog);

  const onStroke = useCallback(async (stroke: Stroke) => {
    if (!current) return;
    const hit = coversEndpoint(stroke, current.bundle.run.start, current.bundle.run.goal);
    if (hit) {
      setEditStatus({ state: 'error', refused: true, message: `Not applied: ${endpointRefusal(hit.what, hit.cell)}` });
      return;
    }
    const r = await run(current, { strokes: [stroke], connectivity: null, runs: null, optimal: false },
      stroke.value === 'occupied' ? 'painting and searching again' : 'erasing and searching again');
    if (r) showEdited(r.bundles[0]);
  }, [current, run, setEditStatus, showEdited]);

  const onRunSettings = useCallback(async () => {
    if (!current || !settings) return;
    const r = await run(current, { strokes: [], connectivity: settings.connectivity, runs: [toRun(settings)], optimal: false },
      'searching with your settings');
    if (r) showEdited(r.bundles[0]);
  }, [current, settings, run, showEdited]);

  const onRace = useCallback(async () => {
    if (!current || !settings) return;
    const runs = raceChosen.map((a) => toRun({ ...settings, algorithm: a }));
    const r = await run(current, { strokes: [], connectivity: settings.connectivity, runs, optimal: true },
      `racing ${runs.length} algorithms on identical inputs`);
    if (r) {
      setPlaying(false);
      setRace({ entrants: r.bundles, optimalCost: r.optimalCost });
    }
  }, [current, settings, raceChosen, run]);

  useEffect(() => {
    const ref = selection[0];
    if (!catalog || !ref || !('catalogId' in ref)) return;
    const entry = catalog.bundles.find((b) => b.id === ref.catalogId);
    if (!entry) return;
    let cancelled = false;
    setLoading(true);
    setCurrent(null);
    setRace(null);
    setEditStatus({ state: 'idle' });
    perfMark('bundle-fetch-start');
    fetchBundle(`${DATA}${entry.path}`)
      .then(({ bundle, files }) => {
        const validated = requireValidated(bundle, entry)!; // throws catalog_mismatch
        if (!cancelled) {
          perfMark('bundle-decoded');
          show({ entry, bundle, files, validated });
        }
      })
      .catch((exc: unknown) => {
        if (cancelled) return;
        setCurrent(null); // never draw a bundle that failed
        setError(exc instanceof BundleError ? { code: exc.code, message: exc.message }
          : { code: 'error', message: String(exc) });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [catalog, selection, show, setEditStatus]);

  const hoverIndex = useMemo(() => current && new HoverIndex(
    current.bundle.trace.events, current.bundle.trace.n, current.bundle.map.width, current.bundle.map.height,
  ), [current]);
  const hoverStates = hover && hoverIndex ? hoverIndex.at(hover[0], hover[1], k) : [];

  const groups = useMemo(() => {
    const g = new Map<string, CatalogEntry[]>();
    for (const e of catalog?.bundles ?? []) g.set(e.group, [...(g.get(e.group) ?? []), e]);
    return [...g.entries()];
  }, [catalog]);

  const editable = !!current && !!catalog?.wheel && (current.entry?.editable ?? false) &&
    current.bundle.provenance.source_kind === 'glass-box';
  const locked = current ? (editable ? settingsLocked(current.bundle)
    : settingsLocked(current.bundle) ?? 'This bundle is not editable.') : null;
  const busy = editStatus.state === 'busy';
  const swept = useMemo(() => (current && sweep
    ? sweptFootprint(pathCells(current.bundle.trace.events, current.bundle.trace.n), current.bundle.map.geo, catalog?.footprint)
    : null), [current, sweep, catalog]);
  const currentId = selection[0] && 'catalogId' in selection[0] ? selection[0].catalogId : null;
  const onRung = useCallback((id: string) => setSelection([{ catalogId: id }]), []);
  const marked = useRef<DecodedBundle | null>(null);
  const onDrawn = useCallback((b: DecodedBundle) => {
    if (marked.current === b) return;
    marked.current = b;
    if (current?.bundle === b && current.validated.by === 'pyodide') perfMark('edit-first-frame');
    else perfMark('bundle-first-frame');
  }, [current]);

  return (
    <div className="app">
      <header className="top">
        <h1>COCO Lab <span className="sub">search, replayed from evidence</span></h1>
        <ModeBadge provenance={current?.bundle.provenance ?? null} />
      </header>

      <div className="picker">
        <label>
          <span>Bundle</span>
          <select data-testid="picker" value={(selection[0] && 'catalogId' in selection[0]) ? selection[0].catalogId : ''}
            onChange={(e) => setSelection([{ catalogId: e.target.value }])} disabled={!catalog}>
            {(!selection[0] || !('catalogId' in selection[0])) && (
              <option value="">
                {current?.entry ? `Your edit of “${current.entry.title}” — computed in your browser by coco_lab`
                  : '(choose a bundle)'}
              </option>
            )}
            {groups.map(([name, entries]) => (
              <optgroup key={name} label={name}>
                {entries.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
              </optgroup>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <div className="error" role="alert" data-testid="error">
          <strong>Refused ({error.code}).</strong> {error.message} Nothing from this bundle is drawn.
        </div>
      )}
      {loading && <p className="loading">Loading and checking the bundle…</p>}

      {current && (
        <main className="stage">
          <div className="canvas-col">
            {race ? (
              <RaceView entrants={race.entrants} optimalCost={race.optimalCost} reducedMotion={reducedMotion}
                onClose={() => setRace(null)} />
            ) : (
              <>
                <MapView bundle={current.bundle} k={k} hover={hover} onHover={setHover} onDrawn={onDrawn}
                  tool={editable ? tool : 'look'} brush={brush} onStroke={editable ? onStroke : undefined}
                  sweep={swept} />
                <Legend recorded={!!current.bundle.recording} sweep={!!swept?.placed} />
                <Player n={current.bundle.trace.n} k={k} playing={playing} speed={speed}
                  reducedMotion={reducedMotion} onSeek={setK} onPlaying={setPlaying} onSpeed={setSpeed} />
                <ToolsM editable={editable} tool={tool} brush={brush} onTool={setTool} onBrush={setBrush} />
              </>
            )}
            <LabStatusLine status={editStatus} />
          </div>
          <aside className="side">
            {catalog?.ladder && (
              <LadderM ladder={catalog.ladder} currentId={currentId} onRung={onRung}
                sweep={sweep} onSweep={setSweep} footprint={catalog.footprint} swept={swept} />
            )}
            {catalog?.settings && settings && (
              <SettingsPanelM analysis={catalog.settings} bundle={current.bundle} value={settings}
                onChange={setSettings} onRun={onRunSettings} locked={locked} busy={busy} />
            )}
            {catalog?.settings && (
              <RaceSetupM algorithms={catalog.settings.algorithms} chosen={raceChosen} onChosen={setRaceChosen}
                onStart={onRace} disabled={locked} busy={busy} />
            )}
            <div className="tabs" role="tablist">
              {(['summary', 'provenance', 'recording', 'hover'] as Tab[]).map((t) => (
                <button key={t} type="button" role="tab" aria-selected={tab === t}
                  className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
              ))}
            </div>
            {tab === 'summary' && <SummaryPanel b={current.bundle} />}
            {tab === 'provenance' && <ProvenancePanel b={current.bundle} entry={current.entry} validated={current.validated} />}
            {tab === 'recording' && <RecordingPanel b={current.bundle} />}
            {tab === 'hover' && <HoverPanel b={current.bundle} cell={hover} states={hoverStates} />}
            {tab !== 'hover' && hover && (
              <HoverPanel b={current.bundle} cell={hover} states={hoverStates} />
            )}
          </aside>
        </main>
      )}

      <footer className="foot">
        <span>Built from {__BUILD_COMMIT__}.</span>{' '}
        <span>No analytics, no cookies. The only third-party request is Pyodide {__PYODIDE_VERSION__}, and only after you paint, change a setting or start a race.</span>
      </footer>
    </div>
  );
}

function Legend({ recorded, sweep }: { recorded: boolean; sweep: boolean }) {
  return (
    <ul className="legend" aria-label="Legend">
      <li><i className="sw open" />open</li>
      <li><i className="sw closed" />closed</li>
      <li><i className="sw path" />path</li>
      <li><i className="sw start" />start</li>
      <li><i className="sw goal" />goal</li>
      {recorded && <li><i className="sw gt" />ground truth</li>}
      {recorded && <li><i className="sw amcl" />AMCL belief</li>}
      {recorded && <li><i className="sw plan" />published plan</li>}
      {sweep && <li><i className="sw sweep" />COCO's footprint, swept</li>}
    </ul>
  );
}
