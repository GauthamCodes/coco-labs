// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * `?view=arena`: the Glass-box Arena (M1). The worker boots as soon as the
 * page opens; the renderer (Three.js, beside React) draws the world, the
 * robot and the planner's computation as it streams in; React draws only
 * panels. Timeline (M1.7) and experience (M1.8) build on this.
 */

import { useEffect, useRef, useState } from 'react';

import { ArenaClient, type PyodideSource } from './client';
import { PerfOverlay } from './PerfOverlay';
import { perf } from './perf';
import { wallMs, type InputRow, type PlanInfo, type Tick, type World } from './protocol';
import { currentTheme } from './render/palette';
import { PlanStore, type CellInfo } from './render/planStore';
import { ArenaRenderer, DEFAULT_LAYERS, type LayerVisibility } from './render/Renderer';

declare global {
  interface Window {
    /** Harness hooks (tools/perf): the client, the latest tick, an input queue, the renderer. */
    __cocoArena?: {
      client: ArenaClient; queue: Omit<InputRow, 'tick'>[]; last: Tick | null;
      renderer: ArenaRenderer | null; store: () => PlanStore | null; goal: (x: number, y: number) => void;
    };
  }
}

/** Reveal a search over about this many frames (the timeline makes it adjustable). */
const REVEAL_FRAMES = 90;

export function ArenaApp() {
  const params = new URLSearchParams(window.location.search);
  const showPerf = params.has('perf');
  const source: PyodideSource = params.get('pyodide') === 'cdn' ? 'cdn' : 'self';
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [world, setWorld] = useState<World | null>(null);
  const [tick, setTick] = useState<Tick | null>(null);
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inspect, setInspect] = useState(false);
  const [picked, setPicked] = useState<CellInfo | null>(null);
  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);
  const [planner, setPlanner] = useState('astar');
  const queue = useRef<Omit<InputRow, 'tick'>[]>([]);
  const renderer = useRef<ArenaRenderer | null>(null);
  const store = useRef<PlanStore | null>(null);
  const inspectRef = useRef(false);
  inspectRef.current = inspect;

  useEffect(() => {
    const cv = canvas.current!;
    let r: ArenaRenderer | null = null;
    try {
      r = new ArenaRenderer(cv, currentTheme());
    } catch (e) {
      setError(`renderer: ${(e as Error).message}`);
    }
    renderer.current = r;
    let client: ArenaClient | null = null;
    let first = true;
    let frontierPending = false;
    r?.start();
    if (r) {
      r.onFrame = () => {
        const s = store.current;
        if (s && s.cursor < s.received) s.advance(s.cursor + Math.max(64, Math.ceil(s.received / REVEAL_FRAMES)));
      };
      r.onAfterRender = () => {
        if (first && client?.world) { first = false; perf.mark('first_frame', wallMs()); }
        if (frontierPending) {
          frontierPending = false;
          perf.mark('first_frontier_shown', wallMs());
          perf.frontierDrawn();
        }
      };
    }
    let outline: Promise<[number, number][]> = fetch(`${import.meta.env.BASE_URL}generated/arena/robot_outline.json`,
      { credentials: 'omit' }).then((x) => x.json()).then((j) => j.polygon);
    client = new ArenaClient({
      onWorld: (w, occ) => {
        setWorld(w);
        store.current = new PlanStore(w.width, w.height);
        void outline.then((poly) => { r?.setWorld(w, occ, poly); r?.setPlan(store.current); });
      },
      onPlanBatch: (meta, cols) => {
        const s = store.current;
        if (!s) return;
        if (meta.search_id !== s.searchId) { s.begin(meta.search_id, meta.planner); r?.setPlan(s); }
        s.append(cols, meta.final);
        if (s.cursor === 0) {
          s.advance(1); // the first frontier node shows on the very next frame
          frontierPending = true;
        }
      },
      onTick: (t, ranges) => {
        setTick(t);
        if (t.plans.length) setPlan(t.plans[t.plans.length - 1]);
        r?.setPose(t.pose);
        r?.setScan(t.pose, ranges);
        if (t.arrived || t.mode !== 'goal') r?.setGoal(null);
        if (window.__cocoArena) window.__cocoArena.last = t;
      },
      onError: (stage, message) => setError(`${stage}: ${message}`),
    }, { pyodide: source, seed: Number(params.get('seed') ?? 1) });
    outline = outline.catch(() => [[0.12, 0], [-0.12, 0.137], [-0.12, -0.137]]);

    const stepNow = () => client!.step(queue.current.splice(0));
    const goal = (x: number, y: number) => {
      perf.goalSent();
      queue.current.push({ kind: 'goal', x, y });
      r?.setGoal([x, y]);
      stepNow(); // the goal is planned at once, not at the next tick boundary
    };
    window.__cocoArena = { client, queue: queue.current, last: null, renderer: r, store: () => store.current, goal };
    let timer: ReturnType<typeof setInterval> | undefined;
    void client.whenReady().then((w) => {
      if (params.has('stress')) r?.addStress(50_000, 20_000);
      timer = setInterval(stepNow, w.dt * 1000);
    }, () => {});

    // a click (not a drag) sets a goal, or inspects a cell in inspect mode
    let down: [number, number] | null = null;
    const onDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6 || !r || !client?.world) return;
      down = null;
      const [x, y] = r.toWorld(e.clientX, e.clientY);
      const cell = r.cellAt(x, y);
      if (inspectRef.current) {
        r.showPick(cell);
        setPicked(cell && store.current ? store.current.info(cell[0], cell[1]) : null);
      } else if (cell) {
        goal(x, y);
      }
    };
    cv.addEventListener('pointerdown', onDown);
    cv.addEventListener('pointerup', onUp);
    return () => {
      clearInterval(timer);
      cv.removeEventListener('pointerdown', onDown);
      cv.removeEventListener('pointerup', onUp);
      client?.close();
      r?.dispose();
    };
    // the client and renderer live as long as the view
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { renderer.current?.setLayers(layers); }, [layers]);

  const toggle = (k: keyof LayerVisibility) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  const choosePlanner = (p: string) => { setPlanner(p); queue.current.push({ kind: 'planner', choice: p }); };

  return (
    <main className="arena" data-testid="arena">
      <header className="arena-head">
        <h1>COCO Arena</h1>
        <span className="evidence-badge model" data-testid="evidence-badge" title="A model in your browser: coco_lab, not the robot">MODEL</span>
        <a href={`${import.meta.env.BASE_URL}?view=plan`} data-testid="v1-labs-link">v1 labs</a>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="arena-stage">
        <canvas ref={canvas} className="arena-canvas" data-testid="arena-canvas"
          aria-label="The arena: click or tap to give COCO a goal" />
        {!world && <p className="arena-loading" data-testid="arena-status">Loading the model (Pyodide + coco_lab)…</p>}
      </div>
      <section className="arena-panels">
        <div className="arena-row" role="group" aria-label="Planner">
          {(world?.planners ?? []).map((p) => (
            <button key={p} type="button" className={p === planner ? 'seg-btn active' : 'seg-btn'}
              aria-pressed={p === planner} data-testid={`planner-${p}`} onClick={() => choosePlanner(p)}>{p}</button>
          ))}
          <button type="button" className={inspect ? 'seg-btn active' : 'seg-btn'} aria-pressed={inspect}
            data-testid="inspect-toggle" onClick={() => setInspect((v) => !v)}>Inspect a cell</button>
        </div>
        <div className="arena-row" role="group" aria-label="Layers">
          {(Object.keys(layers) as (keyof LayerVisibility)[]).map((k) => (
            <label key={k} className="layer-toggle"><input type="checkbox" checked={layers[k]} onChange={() => toggle(k)}
              data-testid={`layer-${k}`} />{k}</label>
          ))}
        </div>
        <p data-testid="arena-tick">
          {world ? `tick ${tick?.tick ?? 0} · t = ${(tick?.t_world ?? 0).toFixed(1)} s · ${tick?.mode ?? 'idle'}` : ''}
          {plan ? ` · ${plan.planner}: ${plan.status}, ${plan.summary.expansions} expansions` +
            (plan.summary.path_cost != null ? `, path cost ${Number(plan.summary.path_cost).toFixed(2)}` : '') : ''}
        </p>
        {picked && (
          <dl className="inspector" data-testid="inspector">
            <dt>cell</dt><dd>({picked.row}, {picked.col}) · {picked.state}</dd>
            <dt>expansion order</dt><dd data-testid="inspector-order">{picked.expansion ?? '—'}</dd>
            <dt>g</dt><dd data-testid="inspector-g">{picked.g?.toFixed(3) ?? '—'}</dd>
            <dt>h</dt><dd>{picked.h?.toFixed(3) ?? '—'}</dd>
            <dt>f</dt><dd>{picked.f?.toFixed(3) ?? '—'}</dd>
            <dt>parent</dt><dd>{picked.parent ? `(${picked.parent[0]}, ${picked.parent[1]})` : '—'}</dd>
            <dt>latest event</dt><dd>{picked.event != null ? `#${picked.event} ${picked.kind}` : '—'}</dd>
          </dl>
        )}
      </section>
      {showPerf && <PerfOverlay />}
    </main>
  );
}
