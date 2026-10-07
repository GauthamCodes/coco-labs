// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { lazy, memo, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { BundleError } from '../bundle/errors';
import {
  fetchBundle, requireValidated, type BundleFiles, type Catalog, type CatalogEntry,
} from '../bundle/load';
import type { DecodedBundle, ValidatedBy } from '../bundle/model';
import { coversEndpoint, endpointRefusal, type Tool } from '../lab/brush';
import { sweptFootprint } from '../lab/footprint';
import { revealCost, revealFewest, type Reveal } from '../lab/predict';
import { diffRuns, parseShare, runsToStrokes, shareQuery, traceDigest } from '../lab/share';
import { ALGORITHM_NAMES, settingsLocked, settingsOf, toRun, type SearchSettings } from '../lab/settings';
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
import { RevealNote } from './Predict';
import { ShareBox } from './ShareBox';
import { RaceSetup, RaceView } from './Race';
import { SettingsPanel } from './SettingsPanel';
import { Exhibit } from './Exhibit';
import { LiveView } from './LiveView';
import { Tools } from './Tools';
import { TrackingPlot } from './TrackingPlot';

const BASE = import.meta.env.BASE_URL; // from site.config.ts via vite.config.ts

// Panels whose props do not change with the playback cursor: memoised, so a
// playback tick re-renders only the map and the player (measured: without
// this, Part A dropped 1-2 frames per full-arena playback that 1D did not)
const LadderM = memo(Ladder);
const SettingsPanelM = memo(SettingsPanel);
const RaceSetupM = memo(RaceSetup);
const ToolsM = memo(Tools);
const DATA = `${BASE}generated/`;
// Lab 2 is fetched only when its view is opened: Lab 1's first load does not pay for it
const Localise = lazy(() => import('./loc/Localise').then((m) => ({ default: m.Localise })));
// Lab 3 likewise: fetched only when its view is opened
const MapLab = lazy(() => import('./map/MapLab').then((m) => ({ default: m.MapLab })));
const SearchLab = lazy(() => import('./search/SearchLab').then((m) => ({ default: m.SearchLab })));
const MoveLab = lazy(() => import('./move/MoveLab').then((m) => ({ default: m.MoveLab })));

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
  const [race, setRace] = useState<{ entrants: Current[]; optimalCost: number | null; reveal: Reveal | null } | null>(null);
  // the catalog bundle the current view was derived from (share links diff against it)
  const [base, setBase] = useState<Current | null>(null);
  const [costPrediction, setCostPrediction] = useState<string | null>(null);
  const [racePrediction, setRacePrediction] = useState<string | null>(null);
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const [shareVerdict, setShareVerdict] = useState<{ ok: boolean | null; message: string } | null>(null);
  const pendingShare = useRef<string | null>(null);
  const [view, setView] = useState<'lab' | 'exhibit' | 'live' | 'localise' | 'map' | 'search' | 'move'>(() => {
    const v = new URLSearchParams(window.location.search).get('view');
    return v === 'live' ? 'live' : v === 'localise' ? 'localise' : v === 'map' ? 'map'
      : v === 'search' ? 'search' : v === 'move' ? 'move' : 'lab';
  });
  const [liveText, setLiveText] = useState('Live — local stack');
  const dataUrl = useCallback((p: string) => `${DATA}${p}`, []);
  const openFromExhibit = useCallback((id: string) => {
    setView('lab');
    setSelection([{ catalogId: id }]);
  }, []);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    perfMark('app-start');
    fetch(`${DATA}catalog.json`, { credentials: 'omit', cache: 'no-cache' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((c: Catalog) => {
        setCatalog(c);
        const params = new URLSearchParams(window.location.search);
        if (params.has('v')) pendingShare.current = window.location.search; // a share link: applied once loaded
        if (params.get('view') === 'exhibit' && c.exhibit) setView('exhibit'); // the README links here
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
    setReveal(null);
    const r = await run(current, { strokes: [stroke], connectivity: null, runs: null, optimal: false },
      stroke.value === 'occupied' ? 'painting and searching again' : 'erasing and searching again');
    if (r) showEdited(r.bundles[0]);
  }, [current, run, setEditStatus, showEdited]);

  const onRunSettings = useCallback(async () => {
    if (!current || !settings) return;
    const predicted = costPrediction;
    const before = current.bundle.trace.summary;
    setReveal(null);
    const r = await run(current, { strokes: [], connectivity: settings.connectivity, runs: [toRun(settings)], optimal: false },
      'searching with your settings');
    if (r) {
      showEdited(r.bundles[0]);
      setReveal(revealCost(predicted, before, r.bundles[0].bundle.trace.summary, (x) => x.toFixed(3)));
      setCostPrediction(null);
    }
  }, [current, settings, costPrediction, run, showEdited]);

  const onRace = useCallback(async () => {
    if (!current || !settings) return;
    const runs = raceChosen.map((a) => toRun({ ...settings, algorithm: a }));
    const r = await run(current, { strokes: [], connectivity: settings.connectivity, runs, optimal: true },
      `racing ${runs.length} algorithms on identical inputs`);
    if (r) {
      setPlaying(false);
      const rows = r.bundles.map((b) => ({
        algorithm: b.bundle.trace.header.algorithm, expansions: b.bundle.trace.summary.expansions }));
      const predicted = racePrediction !== null && raceChosen.includes(racePrediction) ? racePrediction : null;
      setRace({ entrants: r.bundles, optimalCost: r.optimalCost,
        reveal: revealFewest(predicted, rows, (a) => ALGORITHM_NAMES[a] ?? a) });
      setRacePrediction(null);
    }
  }, [current, settings, raceChosen, racePrediction, run]);

  // a share link: rerun coco_lab on the link's inputs, then compare digests
  useEffect(() => {
    const search = pendingShare.current;
    if (!search || !base || !catalog || !base.entry) return;
    pendingShare.current = null;
    const w = base.bundle.map.width;
    let st;
    try {
      st = parseShare(search, catalog.settings,
        (id) => (id === base.entry!.id ? w * base.bundle.map.height : null));
    } catch (exc) {
      setShareVerdict({ ok: false, message: `This share link was refused: ${(exc as Error).message}` });
      return;
    }
    if (!st) return;
    if (!st.settings && st.runs.length === 0) {
      setShareVerdict({ ok: null, message: 'This link shows the bundle as published.' });
      return;
    }
    const editableBase = base.bundle.provenance.source_kind === 'glass-box' && !!base.entry.editable;
    if (!editableBase || (st.settings && settingsLocked(base.bundle))) {
      setShareVerdict({ ok: false, message: 'This share link changes a bundle that cannot be changed; it is shown as published.' });
      return;
    }
    const share = st;
    void (async () => {
      const r = await run(base, {
        strokes: runsToStrokes(share.runs, w), connectivity: share.settings?.connectivity ?? null,
        runs: share.settings ? [toRun(share.settings)] : null, optimal: false,
      }, 'reproducing the shared view');
      if (!r) {
        setShareVerdict({ ok: false, message: 'coco_lab could not reproduce this link; the reason is below.' });
        return;
      }
      showEdited(r.bundles[0]);
      const d = (await traceDigest(r.bundles[0].bundle)).slice(0, 12);
      setShareVerdict(share.digest === null
        ? { ok: null, message: `Recomputed from the link by coco_lab in your browser (trace sha256 ${d}…); the link carried no digest to compare.` }
        : d === share.digest
          ? { ok: true, message: `This link reproduced the exact trace: sha256 ${d}…, recomputed in your browser by coco_lab.` }
          : { ok: false, message: `This link did NOT reproduce the same trace: the link says ${share.digest}…, coco_lab computed ${d}….` });
    })();
  }, [base, catalog, run, showEdited]);

  const makeLink = useCallback(async () => {
    if (!current || !current.entry) throw new Error('nothing is shown');
    const url = new URL(window.location.href);
    if (current.validated.by === 'catalog' || !base) {
      url.search = `?bundle=${encodeURIComponent(current.entry.id)}`;
      return url.href;
    }
    const runs = diffRuns(base.bundle.map.occupancy, current.bundle.map.occupancy);
    const grid = settingsLocked(current.bundle) === null;
    url.search = shareQuery({
      bundle: current.entry.id, settings: grid ? settingsOf(current.bundle) : null, runs,
      digest: (await traceDigest(current.bundle)).slice(0, 12),
    }, catalog?.settings);
    return url.href;
  }, [current, base, catalog]);

  useEffect(() => {
    const ref = selection[0];
    if (!catalog || !ref || !('catalogId' in ref)) return;
    const entry = catalog.bundles.find((b) => b.id === ref.catalogId);
    if (!entry) return;
    let cancelled = false;
    setLoading(true);
    setCurrent(null);
    setRace(null);
    if (!pendingShare.current) setShareVerdict(null); // it described the previous view
    setEditStatus({ state: 'idle' });
    perfMark('bundle-fetch-start');
    fetchBundle(`${DATA}${entry.path}`)
      .then(({ bundle, files }) => {
        const validated = requireValidated(bundle, entry)!; // throws catalog_mismatch
        if (!cancelled) {
          perfMark('bundle-decoded');
          const c = { entry, bundle, files, validated };
          setReveal(null);
          show(c);
          setBase(c);
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
        <h1>COCO Lab <span className="sub">{view === 'localise' ? 'localisation, from evidence'
          : view === 'map' ? 'mapping, from evidence'
            : view === 'search' ? 'finding the target, from evidence'
              : view === 'move' ? 'moving along a path, from evidence' : 'search, replayed from evidence'}</span></h1>
        <nav className="views" aria-label="Views">
          <button type="button" className={view === 'lab' ? 'seg-btn active' : 'seg-btn'} aria-pressed={view === 'lab'}
            onClick={() => setView('lab')} data-testid="view-lab">Lab 1 · Plan</button>
          <button type="button" className={view === 'exhibit' ? 'seg-btn active' : 'seg-btn'} aria-pressed={view === 'exhibit'}
            onClick={() => setView('exhibit')} data-testid="view-exhibit" disabled={!catalog?.exhibit}>The A* myth, twice</button>
          <button type="button" className={view === 'localise' ? 'seg-btn active' : 'seg-btn'}
            aria-pressed={view === 'localise'} onClick={() => setView('localise')} data-testid="view-localise"
            disabled={!(catalog as { localise?: unknown } | null)?.localise}>Lab 2 · Localise</button>
          <button type="button" className={view === 'map' ? 'seg-btn active' : 'seg-btn'}
            aria-pressed={view === 'map'} onClick={() => setView('map')} data-testid="view-map"
            disabled={!(catalog as { map?: unknown } | null)?.map}>Lab 3 · Map</button>
          <button type="button" className={view === 'search' ? 'seg-btn active' : 'seg-btn'}
            aria-pressed={view === 'search'} onClick={() => setView('search')} data-testid="view-search"
            disabled={!(catalog as { search?: unknown } | null)?.search}>Lab 4 · Search</button>
          <button type="button" className={view === 'move' ? 'seg-btn active' : 'seg-btn'}
            aria-pressed={view === 'move'} onClick={() => setView('move')} data-testid="view-move"
            disabled={!(catalog as { move?: unknown } | null)?.move}>Lab 5 · Move</button>
          <button type="button" className={view === 'live' ? 'seg-btn active' : 'seg-btn'} aria-pressed={view === 'live'}
            onClick={() => setView('live')} data-testid="view-live">Live</button>
        </nav>
        {view === 'live'
          ? <span className="mode-badge mode-live" data-testid="mode-badge">{liveText}</span>
          : view === 'localise'
            ? <span className="mode-badge mode-sketch" data-testid="mode-badge">Sketch — a model, not the robot</span>
            : view === 'map' || view === 'search' || view === 'move'
              ? <span className="mode-badge mode-sketch" data-testid="mode-badge">Sketch and Replay — each labelled below</span>
            : <ModeBadge provenance={current?.bundle.provenance ?? null} />}
      </header>
      {view === 'live' && <LiveView onLabel={setLiveText} />}
      {view === 'localise' && catalog && (
        <Suspense fallback={<p className="loading">Loading Lab 2…</p>}>
          <Localise catalog={catalog} reducedMotion={reducedMotion} />
        </Suspense>
      )}
      {view === 'map' && catalog && (
        <Suspense fallback={<p className="loading">Loading Lab 3…</p>}>
          <MapLab catalog={catalog} reducedMotion={reducedMotion} />
        </Suspense>
      )}
      {view === 'search' && catalog && (
        <Suspense fallback={<p className="loading">Loading Lab 4…</p>}>
          <SearchLab catalog={catalog} reducedMotion={reducedMotion} />
        </Suspense>
      )}
      {view === 'move' && catalog && (
        <Suspense fallback={<p className="loading">Loading Lab 5…</p>}>
          <MoveLab catalog={catalog} reducedMotion={reducedMotion} />
        </Suspense>
      )}
      {view === 'exhibit' && catalog && (
        <>
          <Exhibit catalog={catalog} dataUrl={dataUrl} run={run} busy={busy} reducedMotion={reducedMotion}
            onOpenBundle={openFromExhibit} />
          <LabStatusLine status={editStatus} />
        </>
      )}
      {view === 'lab' && (<>

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
                onClose={() => setRace(null)} reveal={race.reveal} />
            ) : (
              <>
                <MapView bundle={current.bundle} k={k} hover={hover} onHover={setHover} onDrawn={onDrawn}
                  tool={editable ? tool : 'look'} brush={brush} onStroke={editable ? onStroke : undefined}
                  sweep={swept} />
                <Legend recorded={!!current.bundle.recording} sweep={!!swept?.placed} />
                <Player n={current.bundle.trace.n} k={k} playing={playing} speed={speed}
                  reducedMotion={reducedMotion} onSeek={setK} onPlaying={setPlaying} onSpeed={setSpeed} />
                {current.entry?.tracking && current.bundle.recording && current.validated.by === 'catalog' && (
                  <TrackingPlot entry={current.entry} bundle={current.bundle} dataUrl={`${DATA}${current.entry.tracking}`} />
                )}
                <ToolsM editable={editable} tool={tool} brush={brush} onTool={setTool} onBrush={setBrush} />
                <ShareBox makeLink={makeLink} verdict={shareVerdict} />
              </>
            )}
            <LabStatusLine status={editStatus} />
            {!race && reveal && <RevealNote reveal={reveal} />}
          </div>
          <aside className="side">
            {catalog?.ladder && (
              <LadderM ladder={catalog.ladder} currentId={currentId} onRung={onRung}
                sweep={sweep} onSweep={setSweep} footprint={catalog.footprint} swept={swept} />
            )}
            {catalog?.settings && settings && (
              <SettingsPanelM analysis={catalog.settings} bundle={current.bundle} value={settings}
                onChange={setSettings} onRun={onRunSettings} locked={locked} busy={busy}
                prediction={costPrediction} onPrediction={setCostPrediction} />
            )}
            {catalog?.settings && (
              <RaceSetupM algorithms={catalog.settings.algorithms} chosen={raceChosen} onChosen={setRaceChosen}
                onStart={onRace} disabled={locked} busy={busy}
                prediction={racePrediction} onPrediction={setRacePrediction} />
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
      </>)}

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
