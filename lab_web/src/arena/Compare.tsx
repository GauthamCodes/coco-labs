// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Side-by-side compare (M1.8): two planners, the same map, start, goal and
 * seed, each drawn by its own renderer and revealed in step, with the
 * totals coco_lab reported. The model's run is not touched (the worker's
 * `compare` changes no state).
 */

import { useEffect, useRef } from 'react';

import type { CompareSide, World } from './protocol';
import { currentTheme } from './render/palette';
import type { PlanStore } from './render/planStore';
import { ArenaRenderer } from './render/Renderer';

export interface CompareState {
  goal: [number, number];
  start: [number, number, number];
  stores: { A: PlanStore; B: PlanStore };
  result: { A: CompareSide; B: CompareSide } | null;
}

function Pane({ side, state, world, occupancy, outline }: {
  side: 'A' | 'B'; state: CompareState; world: World; occupancy: Uint8Array; outline: [number, number][];
}) {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    const r = new ArenaRenderer(canvas.current!, currentTheme());
    r.setWorld(world, occupancy, outline);
    r.setLayers({ lidar: false });
    r.setPose(state.start);
    r.setGoal(state.goal);
    const store = state.stores[side];
    r.setPlan(store);
    // both panes reveal at the same rate: the bigger search sets the pace
    r.onFrame = () => {
      const both = [state.stores.A, state.stores.B];
      const n = Math.max(...both.map((s) => s.received));
      if (store.cursor < store.received) store.advance(store.cursor + Math.max(32, Math.ceil(n / 120)));
    };
    r.start();
    return () => r.dispose();
    // one renderer per pane for the life of the compare
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const res = state.result?.[side];
  const sm = res?.summary;
  return (
    <figure className="compare-pane" data-testid={`compare-${side}`}>
      <canvas ref={canvas} className="arena-canvas" aria-label={`Planner ${side}`} />
      <figcaption>
        <b>{state.stores[side].planner}</b>
        {sm ? (
          <span data-testid={`compare-${side}-totals`}> · {res!.status} · {Number(sm.expansions).toLocaleString()} expansions
            {sm.path_cost != null ? ` · path cost ${Number(sm.path_cost).toFixed(2)} · length ${(Number(sm.path_length) * res!.resolution).toFixed(2)} m` : ''}
          </span>
        ) : ' · computing…'}
      </figcaption>
    </figure>
  );
}

export function Compare(props: { state: CompareState; world: World; occupancy: Uint8Array; outline: [number, number][]; onClose(): void }) {
  return (
    <section className="compare" aria-label="Compare two planners" data-testid="compare">
      <div className="arena-row">
        <b>Same map, start, goal and seed</b>
        <button type="button" className="seg-btn" data-testid="compare-close" onClick={props.onClose}>Close compare</button>
      </div>
      <div className="compare-grid">
        <Pane side="A" {...props} />
        <Pane side="B" {...props} />
      </div>
    </section>
  );
}
