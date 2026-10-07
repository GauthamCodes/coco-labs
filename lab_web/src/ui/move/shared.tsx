// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState, type ReactNode } from 'react';

import { BundleError } from '../../bundle/errors';
import { arraysFileName } from '../../bundle/load';
import type { DriveEntry, ReplanEntry } from '../../move/catalog';
import {
  DRIVE_SCHEMA, loadDriveBytes, loadReplanBytes, parseMoveManifest, REPLAN_SCHEMA,
  type DecodedDriveBundle, type DecodedReplanBundle,
} from '../../move/decode';

const BASE = import.meta.env.BASE_URL;
export const DATA = `${BASE}generated/`;

async function fetchBytes(url: string): Promise<Uint8Array> {
  const r = await fetch(url, { credentials: 'omit', cache: 'no-cache' });
  if (!r.ok) throw new Error(`cannot fetch ${url}: HTTP ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

export interface Files { manifest: Uint8Array; arraysName: string; arraysFile: Uint8Array }

async function filesOf(path: string, schema: string): Promise<Files> {
  const manifest = await fetchBytes(`${DATA}${path}manifest.json`);
  const arraysName = arraysFileName(parseMoveManifest(manifest, schema).compression);
  return { manifest, arraysName, arraysFile: await fetchBytes(`${DATA}${path}${arraysName}`) };
}

/** Fetch, decode and check a catalog replan bundle (content hash = the catalog's). */
export async function loadReplanEntry(e: ReplanEntry): Promise<{ bundle: DecodedReplanBundle; files: Files }> {
  const files = await filesOf(e.path, REPLAN_SCHEMA);
  const bundle = await loadReplanBytes(files.manifest, files.arraysFile);
  if (bundle.contentHash !== e.content_hash) throw new BundleError('catalog_mismatch', `${e.id}: not the catalog's bundle`);
  return { bundle, files };
}

/** Fetch, decode and check a catalog drive bundle. */
export async function loadDriveEntry(e: DriveEntry): Promise<DecodedDriveBundle> {
  const files = await filesOf(e.path, DRIVE_SCHEMA);
  const bundle = await loadDriveBytes(files.manifest, files.arraysFile);
  if (bundle.contentHash !== e.content_hash) throw new BundleError('catalog_mismatch', `${e.id}: not the catalog's bundle`);
  return bundle;
}

/** Load a drive bundle by entry, with loading/error state. */
export function useDrive(entry: DriveEntry | undefined) {
  const [b, setB] = useState<DecodedDriveBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!entry) return undefined;
    let alive = true;
    setB(null);
    setError(null);
    loadDriveEntry(entry).then((x) => alive && setB(x))
      .catch((exc) => alive && setError(exc instanceof Error ? exc.message : String(exc)));
    return () => { alive = false; };
  }, [entry]);
  return { b, error };
}

/** Map-frame metres to SVG: x across, y up the page. */
export interface Frame { x0: number; x1: number; y0: number; y1: number; s: number }

export function frameOf(xs: number[], ys: number[], pad: number, s = 60): Frame {
  return { x0: Math.min(...xs) - pad, x1: Math.max(...xs) + pad, y0: Math.min(...ys) - pad, y1: Math.max(...ys) + pad, s };
}

export const X = (f: Frame, x: number) => (x - f.x0) * f.s;
export const Y = (f: Frame, y: number) => (f.y1 - y) * f.s;
export const pts = (f: Frame, p: Array<[number, number]> | number[][]) => p.map(([x, y]) => `${X(f, x).toFixed(1)},${Y(f, y).toFixed(1)}`).join(' ');

export function MapSvg({ f, label, children, testid }: { f: Frame; label: string; children: ReactNode; testid: string }) {
  const W = (f.x1 - f.x0) * f.s;
  const H = (f.y1 - f.y0) * f.s;
  return (
    <svg className="move-svg" viewBox={`0 0 ${W.toFixed(0)} ${H.toFixed(0)}`} role="img" aria-label={label}
      data-testid={testid}>
      <rect x={0} y={0} width={W} height={H} className="mv-floor" />
      {children}
    </svg>
  );
}

/** Boxes (cx, cy, sx, sy) that overlap the frame, drawn as walls. */
export function Walls({ f, boxes }: { f: Frame; boxes: number[][] }) {
  return (
    <g className="mv-walls">
      {boxes.filter(([cx, cy, sx, sy]) => cx + sx / 2 > f.x0 && cx - sx / 2 < f.x1 && cy + sy / 2 > f.y0 && cy - sy / 2 < f.y1)
        .map(([cx, cy, sx, sy], i) => (
          <rect key={i} className="mv-wall" x={X(f, cx - sx / 2)} y={Y(f, cy + sy / 2)} width={sx * f.s} height={sy * f.s} />))}
    </g>
  );
}

/** A time player over [t0, t1] in simulator seconds. */
export function useClock(t0: number, t1: number, reducedMotion: boolean) {
  const [t, setT] = useState(t0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { setT(t0); setPlaying(false); }, [t0, t1]);
  useEffect(() => {
    if (!playing) return undefined;
    if (t >= t1) { setPlaying(false); return undefined; }
    const id = window.setTimeout(() => setT((x) => Math.min(t1, x + (reducedMotion ? 2 : 0.25))), reducedMotion ? 400 : 50);
    return () => window.clearTimeout(id);
  }, [playing, t, t0, t1, reducedMotion]);
  return { t, setT, playing, setPlaying };
}

export function Clock({ t0, t1, t, setT, playing, setPlaying, prefix }: {
  t0: number; t1: number; t: number; setT: (v: number) => void; playing: boolean; setPlaying: (p: boolean) => void; prefix: string;
}) {
  return (
    <div className="player" role="group" aria-label="Time">
      <div className="player-buttons">
        <button type="button" className="play" data-testid={`${prefix}-play`}
          onClick={() => { if (!playing && t >= t1) setT(t0); setPlaying(!playing); }}>{playing ? 'Pause' : 'Play'}</button>
        <button type="button" onClick={() => { setPlaying(false); setT(t1); }} data-testid={`${prefix}-end`}>End</button>
      </div>
      <input className="scrub" type="range" min={t0} max={t1} step={0.05} value={t} aria-label="Simulator time"
        data-testid={`${prefix}-scrub`} onChange={(ev) => { setPlaying(false); setT(Number(ev.target.value)); }} />
      <div className="player-pos">t = {(t - t0).toFixed(1)} s of {(t1 - t0).toFixed(1)} s (simulator)</div>
    </div>
  );
}
