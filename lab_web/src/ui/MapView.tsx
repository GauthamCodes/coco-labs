// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import type { DecodedBundle } from '../bundle/model';
import { StrokeBuilder, type Cell, type Tool } from '../lab/brush';
import type { Swept } from '../lab/footprint';
import { drawScene, makeLayer, putRGBA, renderSweepLayer, type Preview } from '../render/draw';
import { buildMapRGBA, buildTraceRGBA, updateTraceRGBA } from '../render/layers';
import { recordingOverlays } from '../render/overlays';
import { pathCells, TraceCursor } from '../trace/cursor';
import type { Stroke } from '../worker/protocol';
import { perfFrame } from './perf';

export interface MapViewProps {
  bundle: DecodedBundle;
  k: number;
  onHover: (cell: [number, number] | null) => void;
  hover: [number, number] | null;
  /** Painting: with a paint/erase tool, one drag becomes one stroke. */
  tool?: Tool;
  brush?: number;
  onStroke?: (s: Stroke) => void;
  /** The footprint swept along the path, when shown. */
  sweep?: Swept | null;
  onDrawn?: (bundle: DecodedBundle) => void;
}

/** The map, the trace state at cursor `k`, the path and the recorded overlays. */
export function MapView({ bundle, k, onHover, hover, tool = 'look', brush = 1, onStroke, sweep, onDrawn }: MapViewProps) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [cssWidth, setCssWidth] = useState(0);
  const [preview, setPreview] = useState<Preview | null>(null);
  const drag = useRef<{ b: StrokeBuilder; last: Cell } | null>(null);
  const { width, height } = bundle.map;
  const painting = !!onStroke && tool !== 'look';

  // per-bundle state: the cursor, the two 1-px layers, the overlays
  const layers = useMemo(() => {
    const cursor = new TraceCursor(bundle.trace.events, bundle.trace.n, width, height);
    const mapLayer = makeLayer(width, height);
    putRGBA(mapLayer, buildMapRGBA(bundle.map), width, height);
    const traceLayer = makeLayer(width, height);
    const traceRGBA = buildTraceRGBA(cursor.state);
    cursor.takeChanges();
    return { cursor, mapLayer, traceLayer, traceRGBA, overlays: recordingOverlays(bundle) };
  }, [bundle, width, height]);

  useEffect(() => setPreview(null), [bundle]);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setCssWidth(el.clientWidth));
    ro.observe(el);
    setCssWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const cssScale = cssWidth > 0 ? cssWidth / width : 0;
  const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
  const devW = Math.round(width * cssScale * dpr);
  const devH = Math.round(height * cssScale * dpr);
  // the swept footprint, rendered once per bundle, toggle and canvas size --
  // never inside a playback frame
  const sweepLayer = useMemo(() => (sweep && sweep.placed && devW > 0
    ? renderSweepLayer(sweep.polygons, cssScale * dpr, devW, devH) : null), [sweep, cssScale, dpr, devW, devH]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv || cssScale <= 0) return;
    const t0 = performance.now();
    const scale = cssScale * dpr;
    const w = devW;
    const h = devH;
    if (cv.width !== w || cv.height !== h) {
      cv.width = w;
      cv.height = h;
    }
    const { cursor, traceLayer, traceRGBA } = layers;
    cursor.seek(k);
    updateTraceRGBA(traceRGBA, cursor.state, cursor.takeChanges());
    putRGBA(traceLayer, traceRGBA, width, height);
    const ctx = cv.getContext('2d')!;
    drawScene(ctx, {
      bundle, mapLayer: layers.mapLayer, traceLayer, overlays: layers.overlays,
      path: pathCells(bundle.trace.events, k), hover,
      sweepLayer: k >= bundle.trace.n ? sweepLayer : null,
      preview,
    }, scale);
    perfFrame(performance.now() - t0);
    onDrawn?.(bundle);
  }, [bundle, k, hover, layers, cssScale, dpr, devW, devH, onDrawn, sweepLayer, preview]);

  const cellFromEvent = (e: React.PointerEvent<HTMLCanvasElement>): Cell | null => {
    const rect = e.currentTarget.getBoundingClientRect();
    const col = Math.floor(((e.clientX - rect.left) / rect.width) * width);
    const row = Math.floor(((e.clientY - rect.top) / rect.height) * height);
    return row >= 0 && row < height && col >= 0 && col < width ? [row, col] : null;
  };

  const finish = () => {
    const d = drag.current;
    drag.current = null;
    if (d && onStroke) onStroke(d.b.stroke());
  };

  return (
    <div className="map-wrap" ref={wrap}>
      <canvas
        ref={canvas}
        className={painting ? 'map-canvas editable' : 'map-canvas'}
        data-testid="map-canvas"
        style={{
          width: '100%', height: cssScale > 0 ? `${height * cssScale}px` : 'auto',
          touchAction: painting ? 'none' : undefined,
        }}
        onPointerMove={(e) => {
          const cell = cellFromEvent(e);
          onHover(cell);
          const d = drag.current;
          if (d && cell) {
            d.b.add(cell, d.last);
            d.last = cell;
            setPreview({ value: d.b.value, cells: d.b.cells.slice() });
          }
        }}
        onPointerLeave={() => onHover(null)}
        onPointerDown={(e) => {
          const cell = cellFromEvent(e);
          onHover(cell);
          if (!cell || !painting || e.button !== 0) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          const b = new StrokeBuilder(tool === 'paint' ? 'occupied' : 'free', brush, width, height);
          b.add(cell);
          drag.current = { b, last: cell };
          setPreview({ value: b.value, cells: b.cells.slice() });
        }}
        onPointerUp={finish}
        onPointerCancel={() => {
          drag.current = null;
          setPreview(null);
        }}
        role="img"
        aria-label={`Map ${bundle.map.id || '(unnamed)'}, ${width} by ${height} cells, trace at event ${k}`}
      />
    </div>
  );
}
