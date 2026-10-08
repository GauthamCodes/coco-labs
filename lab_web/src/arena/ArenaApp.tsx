// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * `?view=arena`: the Glass-box Arena (M1). This checkpoint (M1.5) is the
 * runtime: the worker boots as soon as the page opens, the Arena steps at
 * its fixed dt, and `?perf` shows the measured timings. The renderer (M1.6),
 * timeline (M1.7) and experience (M1.8) build on it.
 */

import { useEffect, useRef, useState } from 'react';

import { ArenaClient, type PyodideSource } from './client';
import { PerfOverlay } from './PerfOverlay';
import { perf } from './perf';
import { wallMs, type InputRow, type Tick, type World } from './protocol';

declare global {
  interface Window {
    /** Harness hooks (tools/perf): the client, the latest tick, and an input queue. */
    __cocoArena?: { client: ArenaClient; queue: Omit<InputRow, 'tick'>[]; last: Tick | null };
  }
}

export function ArenaApp() {
  const params = new URLSearchParams(window.location.search);
  const showPerf = params.has('perf');
  const source: PyodideSource = params.get('pyodide') === 'cdn' ? 'cdn' : 'self';
  const [world, setWorld] = useState<World | null>(null);
  const [tick, setTick] = useState<Tick | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queue = useRef<Omit<InputRow, 'tick'>[]>([]);

  useEffect(() => {
    const client = new ArenaClient({
      onWorld: (w) => setWorld(w),
      onTick: (t) => { setTick(t); if (window.__cocoArena) window.__cocoArena.last = t; },
      onError: (stage, message) => setError(`${stage}: ${message}`),
    }, { pyodide: source, seed: Number(params.get('seed') ?? 1) });
    window.__cocoArena = { client, queue: queue.current, last: null };
    let timer: ReturnType<typeof setInterval> | undefined;
    let stepping = false;
    void client.whenReady().then((w) => {
      requestAnimationFrame(() => perf.mark('first_frame', wallMs()));
      timer = setInterval(() => {
        if (stepping) return;
        stepping = true;
        client.step(queue.current.splice(0));
        stepping = false;
      }, w.dt * 1000);
    }, () => {});
    return () => { clearInterval(timer); client.close(); };
    // the client lives as long as the view
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="arena" data-testid="arena">
      <header className="arena-head">
        <h1>COCO Arena</h1>
        <span className="evidence-badge model" data-testid="evidence-badge" title="A model in your browser: coco_lab, not the robot">MODEL</span>
        <a href={`${import.meta.env.BASE_URL}?view=plan`} data-testid="v1-labs-link">v1 labs</a>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      <p data-testid="arena-status">
        {world ? `World ${world.id}: ${world.width} × ${world.height} cells at ${world.resolution} m; tick ${tick?.tick ?? 0}, ${tick?.mode ?? 'idle'}`
          : 'Loading the model (Pyodide + coco_lab)…'}
      </p>
      {showPerf && <PerfOverlay />}
    </main>
  );
}
