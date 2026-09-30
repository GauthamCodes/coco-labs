// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import type { DecodedBundle } from '../bundle/model';
import { drawScene, makeLayer, putRGBA } from '../render/draw';
import { buildMapRGBA, buildTraceRGBA, updateTraceRGBA } from '../render/layers';
import { recordingOverlays } from '../render/overlays';
import { pathCells, TraceCursor } from '../trace/cursor';
import { perfFrame } from './perf';

export interface MapViewProps {
  bundle: DecodedBundle;
  k: number;
  onHover: (cell: [number, number] | null) => void;
  hover: [number, number] | null;
  onCellClick?: (cell: [number, number]) => void;
  onDrawn?: (bundle: DecodedBundle) => void;
}

/** The map, the trace state at cursor `k`, the path and the recorded overlays. */
export function MapView({ bundle, k, onHover, hover, onCellClick, onDrawn }: MapViewProps) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [cssWidth, setCssWidth] = useState(0);
  const { width, height } = bundle.map;

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

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setCssWidth(el.clientWidth));
    ro.observe(el);
    setCssWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const cssScale = cssWidth > 0 ? cssWidth / width : 0;

  useEffect(() => {
    const cv = canvas.current;
    if (!cv || cssScale <= 0) return;
    const t0 = performance.now();
    const dpr = window.devicePixelRatio || 1;
    const scale = cssScale * dpr;
    const w = Math.round(width * scale);
    const h = Math.round(height * scale);
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
    }, scale);
    perfFrame(performance.now() - t0);
    onDrawn?.(bundle);
  }, [bundle, k, hover, layers, cssScale, width, height, onDrawn]);

  const cellFromEvent = (e: React.PointerEvent<HTMLCanvasElement>): [number, number] | null => {
    const rect = e.currentTarget.getBoundingClientRect();
    const col = Math.floor(((e.clientX - rect.left) / rect.width) * width);
    const row = Math.floor(((e.clientY - rect.top) / rect.height) * height);
    return row >= 0 && row < height && col >= 0 && col < width ? [row, col] : null;
  };

  return (
    <div className="map-wrap" ref={wrap}>
      <canvas
        ref={canvas}
        className={onCellClick ? 'map-canvas editable' : 'map-canvas'}
        data-testid="map-canvas"
        style={{ width: '100%', height: cssScale > 0 ? `${height * cssScale}px` : 'auto' }}
        onPointerMove={(e) => onHover(cellFromEvent(e))}
        onPointerLeave={() => onHover(null)}
        onPointerDown={(e) => {
          const cell = cellFromEvent(e);
          onHover(cell);
          if (cell && onCellClick && e.pointerType === 'mouse') onCellClick(cell);
        }}
        role="img"
        aria-label={`Map ${bundle.map.id || '(unnamed)'}, ${width} by ${height} cells, trace at event ${k}`}
      />
    </div>
  );
}
