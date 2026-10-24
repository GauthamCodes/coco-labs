// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * A view that fails (a 3D stage the browser gives no WebGL, a renderer that throws) shows its
 * fallback instead of taking the whole page down: with no boundary React unmounts the root and
 * the page goes blank (seen on the deployed site in Brave, 2026-10-24, when WebGL was refused).
 */
import { Component, type ErrorInfo, type ReactNode } from 'react';

const BASE = import.meta.env.BASE_URL;

/** Whether an error is the browser refusing WebGL (three.js's message names it). */
export const isWebGLError = (error: unknown) => /webgl/i.test(String((error as Error)?.message ?? error));

type Props = { fallback: (error: Error) => ReactNode; onError?: (error: Error) => void; children: ReactNode };

export class StageBoundary extends Component<Props, { error: Error | null }> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('COCO Lab: a view failed and was replaced by its fallback', error, info.componentStack);
    this.props.onError?.(error);
  }
  render() { return this.state.error ? this.props.fallback(this.state.error) : this.props.children; }
}

/** What to try when the browser gives no WebGL: plain text, the browser pages are not linkable. */
export function WebGLHelp() {
  return <ul style={{ margin: '8px 0', paddingLeft: 20, lineHeight: 1.5 }}>
    <li>Reload the page: browsers turn 3D off for a while after the graphics driver resets.</li>
    <li>Turn on hardware acceleration (Chrome, Brave, Edge: Settings › System › “Use graphics acceleration when available”), then relaunch the browser.</li>
    <li>Close other tabs that draw 3D; a browser keeps only a limited number of WebGL pages alive.</li>
    <li>Check chrome://gpu (brave://gpu in Brave): “WebGL” should read “Hardware accelerated”.</li>
  </ul>;
}

/** A whole page that failed: what happened, what to try, and a way back. Never a blank page. */
export function PageError({ error }: { error: Error }) {
  const gl = isWebGLError(error);
  return <main role="alert" data-testid="page-error" data-webgl={gl ? 'false' : undefined}
    style={{ maxWidth: 640, margin: '12vh auto', padding: '0 16px', color: '#E8EDF5', font: '500 15px/1.45 system-ui, sans-serif' }}>
    <h1 style={{ fontSize: 22, margin: '0 0 8px' }}>{gl ? 'This page needs 3D graphics (WebGL), and the browser did not provide it' : 'Something went wrong on this page'}</h1>
    {gl ? <WebGLHelp /> : <p>Reloading usually fixes it. If it keeps happening, the details below say what failed.</p>}
    <p style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
      <button onClick={() => window.location.reload()} style={{ font: 'inherit', padding: '8px 16px', borderRadius: 8, border: 0, background: '#FF7A1A', color: '#111', fontWeight: 700, cursor: 'pointer' }}>Reload</button>
      <a href={BASE} style={{ color: '#93C5FD' }}>COCO Lab title</a>
    </p>
    <details style={{ color: '#93A0B5' }}><summary>Details</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{error.message}</pre></details>
  </main>;
}
