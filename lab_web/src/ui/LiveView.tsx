// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Live tab: the real robot, through coco.v1, in three modes.
 *
 * It renders what the server sends and sends intents; it decides nothing
 * about the robot (rule 8). Safety stays where it is enforced: the server
 * latches STOP and the arbiter lets teleop preempt. The page only makes
 * both visible.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { LiveClient, type ConnState } from '../live/client';
import { isZero, keysVelocity, KEYS, stickVelocity, type Velocity } from '../live/drive';
import { loadFrameDecoder, type DecodedFrame } from '../live/frame';
import {
  controlHolder, fallbackWarning, LANE_TOLD, liveLabel, localisationNote, overriding, sourceWords,
} from '../live/labels';
import { draw, gridImage, toCanvas, toMap, type View } from '../live/mapdraw';
import type { MapFrame, Telemetry, Welcome } from '../live/protocol';

const BASE = import.meta.env.BASE_URL;
export const DEFAULT_URL = 'ws://localhost:8080/ws';
type Panel = 'teleop' | 'nav2' | 'auto';

const COLOURS: Record<string, string> = { red: '#d62728', green: '#2ca02c', blue: '#1f77b4', yellow: '#e6c700' };

declare global {
  // Read-only hooks for the measurement harness (scripts/live_check): the
  // client's wall-clock send log, the latest telemetry, and map -> screen.
  interface Window {
    __cocoLive?: LiveClient;
    __cocoLiveTele?: Telemetry | null;
    __cocoLiveToScreen?: (x: number, y: number) => [number, number] | null;
  }
}

function initialUrl(): string {
  const q = new URLSearchParams(window.location.search).get('live');
  return q && /^wss?:\/\//.test(q) ? q : DEFAULT_URL;
}

export function LiveView({ onLabel }: { onLabel(text: string): void }) {
  const [url, setUrl] = useState(initialUrl);
  const [draftUrl, setDraftUrl] = useState(url);
  const [conn, setConn] = useState<ConnState>('closed');
  const [welcome, setWelcome] = useState<Welcome | null>(null);
  const [tele, setTele] = useState<Telemetry | null>(null);
  const [map, setMap] = useState<MapFrame | null>(null);
  const [panel, setPanel] = useState<Panel>('teleop');
  const [showTruth, setShowTruth] = useState(false);
  const [colour, setColour] = useState<string | null>(null);
  const [note, setNote] = useState<{ text: string; bad: boolean } | null>(null);
  const [timeline, setTimeline] = useState<{ state: string; words: string | null; at: number }[]>([]);
  const [frameErr, setFrameErr] = useState<string | null>(null);
  const [rate, setRate] = useState(0);
  const client = useRef<LiveClient | null>(null);
  const camera = useRef<HTMLCanvasElement | null>(null);
  const uiMode = useRef<'teleop' | 'auto' | 'stop' | null>(null);

  useEffect(() => { onLabel(liveLabel(url)); }, [url, onLabel]);

  // ── connection ───────────────────────────────────────────────────────
  useEffect(() => {
    let alive = true;
    let c: LiveClient | null = null;
    loadFrameDecoder(BASE).catch((e: Error) => setFrameErr(e.message)).finally(() => {
      if (!alive) return;
      c = new LiveClient(url, {
        onState: setConn,
        onWelcome: (w) => {
          setWelcome(w);
          c?.send({ type: 'subscribe', streams: ['camera'] });
        },
        onTelemetry: (t) => { window.__cocoLiveTele = t; setTele(t); },
        onMap: setMap,
        onSensor: (f) => { if (f.stream === 'camera') void paint(camera.current, f); },
        onError: (code, message) => setNote({ text: code === 'stopped' ? 'Stopped — pick a mode to move again.' : message, bad: code !== 'not_in_control' }),
      });
      client.current = c;
      window.__cocoLive = c;
      c.connect();
    });
    const t = setInterval(() => setRate(client.current?.telemetryRate() ?? 0), 1000);
    return () => { alive = false; clearInterval(t); c?.close(); client.current = null; };
  }, [url]);

  // ── mission timeline: states as the executive reports them ──────────
  useEffect(() => {
    const s = tele?.mission?.state;
    if (!s) return;
    setTimeline((tl) => (tl.length && tl[tl.length - 1].state === s ? tl
      : [...tl, { state: s, words: tele?.mission?.words ?? null, at: Date.now() }].slice(-40)));
  }, [tele?.mission?.state, tele?.mission?.words]);

  const send = useCallback((intent: Parameters<LiveClient['send']>[0]) => client.current?.send(intent) ?? null, []);
  const missionActive = !!tele?.mission?.active;
  const latched = !!tele?.platform.stop?.latched;

  /** Pick a mode explicitly (releases a latched STOP). Not mid-mission. */
  const pickMode = useCallback((m: 'teleop' | 'auto') => {
    if (missionActive) return;
    uiMode.current = m;
    send({ type: 'set_mode', mode: m });
  }, [missionActive, send]);

  // ── driving: one 10 Hz loop for stick and keys, 3 zeros on release ──
  const stick = useRef<Velocity>({ linear: 0, angular: 0 });
  const held = useRef(new Set<string>());
  const zeros = useRef(0);
  const limits = welcome?.limits ?? { linear: 0.5, angular: 1.2 };
  const startDriving = useCallback(() => {
    // Preempting a mission needs no mode change: teleop outranks every
    // mode in the arbiter. Otherwise driving IS the explicit choice.
    if (!missionActive && uiMode.current !== 'teleop') pickMode('teleop');
  }, [missionActive, pickMode]);
  useEffect(() => {
    const t = setInterval(() => {
      let v = stick.current;
      if (held.current.size) v = keysVelocity(held.current, limits);
      if (isZero(v)) {
        if (zeros.current <= 0) return;
        zeros.current--;
      } else {
        zeros.current = 3;
      }
      send({ type: 'drive', linear: v.linear, angular: v.angular });
    }, 100);
    return () => clearInterval(t);
  }, [limits, send]);

  const stop = useCallback(() => {
    held.current.clear();
    stick.current = { linear: 0, angular: 0 };
    zeros.current = 3;
    uiMode.current = 'stop';
    const sent = send({ type: 'stop' });
    setNote(sent !== null ? { text: 'STOP sent — latched until you pick a mode.', bad: false }
      : { text: 'Not connected — nothing was sent. The server stops COCO when its last page leaves.', bad: true });
  }, [send]);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.matches?.('input, textarea, select')) return;
      if (e.code === 'Space') { e.preventDefault(); stop(); return; }
      const k = KEYS[e.key];
      if (!k) return;
      e.preventDefault();
      if (e.repeat && !held.current.has(k)) return; // held through a STOP
      if (!held.current.size) startDriving();
      held.current.add(k);
    };
    const up = (e: KeyboardEvent) => { const k = KEYS[e.key]; if (k) held.current.delete(k); };
    const blur = () => { held.current.clear(); stick.current = { linear: 0, angular: 0 }; };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', blur);
    document.addEventListener('visibilitychange', blur);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      window.removeEventListener('blur', blur);
      document.removeEventListener('visibilitychange', blur);
    };
  }, [stop, startDriving]);

  // ── map ──────────────────────────────────────────────────────────────
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const view = useRef<View | null>(null);
  const dark = useMemo(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false, []);
  const grid = useMemo(() => {
    if (!map) return null;
    const c = document.createElement('canvas');
    c.width = map.width; c.height = map.height;
    c.getContext('2d')?.putImageData(gridImage(map, dark), 0, 0);
    return c;
  }, [map, dark]);
  useEffect(() => {
    const cv = canvas.current;
    const ctx = cv?.getContext('2d');
    if (!cv || !ctx) return;
    const ink = getComputedStyle(cv).color || '#888';
    view.current = draw(ctx, {
      map, grid, world: welcome?.world, path: tele?.nav.path ?? [], local: tele?.nav.local_path ?? [],
      pose: tele?.robot.pose ?? null, belief: tele?.robot.belief, truth: tele?.robot.truth, showTruth,
      goal: tele?.nav.goal, colours: COLOURS,
    }, cv.width, cv.height, ink);
  }, [map, grid, welcome, tele, showTruth]);

  useEffect(() => {
    window.__cocoLiveToScreen = (x, y) => {
      const cv = canvas.current;
      const v = view.current;
      if (!cv || !v) return null;
      const r = cv.getBoundingClientRect();
      const [px, py] = toCanvas(v, x, y);
      return [r.left + px * (r.width / cv.width), r.top + py * (r.height / cv.height)];
    };
    return () => { window.__cocoLiveToScreen = undefined; };
  }, []);

  const onMapClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (panel !== 'nav2') { setNote({ text: 'Switch to Nav2 to send COCO somewhere.', bad: false }); return; }
    if (missionActive) { setNote({ text: 'A mission is running; it owns Nav2.', bad: true }); return; }
    const cv = canvas.current!;
    const r = cv.getBoundingClientRect();
    if (!view.current) return;
    const [x, y] = toMap(view.current, (e.clientX - r.left) * (cv.width / r.width), (e.clientY - r.top) * (cv.height / r.height));
    if (uiMode.current !== 'auto') pickMode('auto');
    send({ type: 'nav_goal', x, y });
    setNote({ text: `Goal sent: (${x.toFixed(2)}, ${y.toFixed(2)})`, bad: false });
  };

  // ── render ───────────────────────────────────────────────────────────
  const warning = fallbackWarning(welcome);
  const holder = controlHolder(tele, welcome?.you);
  const locNote = localisationNote(tele);
  const goal = tele?.nav.goal;
  const m = tele?.mission;
  return (
    <section className="live" data-testid="live">
      <div className="live-bar">
        <form onSubmit={(e) => { e.preventDefault(); setUrl(draftUrl.trim()); }}>
          <label>Server <input value={draftUrl} onChange={(e) => setDraftUrl(e.target.value)} data-testid="live-url"
            spellCheck={false} /></label>
          <button type="submit" className="seg-btn">Connect</button>
        </form>
        <span className={`conn conn-${conn}`} data-testid="live-conn">{conn === 'open' ? 'connected' : conn}</span>
        <span className="muted">to <code>{url}</code></span>
        <span className="muted" data-testid="live-rate">telemetry {rate.toFixed(1)} Hz (measured here)</span>
        {client.current?.rttMs != null && <span className="muted">RTT {client.current.rttMs.toFixed(0)} ms</span>}
      </div>
      {frameErr && <div className="error" role="alert">Sensor decoder unavailable: {frameErr}</div>}
      {warning && <div className="error" role="alert" data-testid="live-fallback">{warning}</div>}
      {latched && <div className="banner stop-banner" data-testid="live-latched">STOPPED (latched). Pick a mode, or start a mission, to move again.</div>}
      {overriding(tele) && <div className="banner override" data-testid="live-override">You are overriding the mission: your stick outranks it. Let go and the mission resumes.</div>}

      <div className="seg" role="tablist" aria-label="Live mode">
        {(['teleop', 'nav2', 'auto'] as Panel[]).map((p) => (
          <button key={p} type="button" role="tab" aria-selected={panel === p}
            className={panel === p ? 'seg-btn active' : 'seg-btn'} data-testid={`live-panel-${p}`}
            onClick={() => { setPanel(p); if (p === 'teleop') pickMode('teleop'); if (p === 'nav2') pickMode('auto'); }}>
            {p === 'teleop' ? 'Teleop' : p === 'nav2' ? 'Nav2' : 'Autonomous'}
          </button>
        ))}
      </div>

      <div className="live-grid">
        <div className="live-map">
          <canvas ref={canvas} width={720} height={540} onClick={onMapClick} data-testid="live-map"
            aria-label="Arena map: click a goal in Nav2 mode" className={panel === 'nav2' ? 'clickable' : ''} />
          <div className="live-legend">
            <label><input type="checkbox" checked={showTruth} onChange={(e) => setShowTruth(e.target.checked)}
              data-testid="live-truth" /> show simulator ground truth (dashed green; display only, never sent to the robot)</label>
            <span><i className="sw belief" />belief (AMCL, 2σ)</span>
            <span><i className="sw plan" />global plan</span>
            <span><i className="sw local" />local trajectory</span>
          </div>
          {locNote && <p className="muted" data-testid="live-localised">{locNote}</p>}
        </div>
        <aside className="live-side">
          <dl className="live-status">
            <dt>Mode</dt><dd data-testid="live-mode">{tele?.platform.arbiter?.mode ?? '—'}</dd>
            <dt>Wheels driven by</dt><dd data-testid="live-source">{sourceWords(tele?.nav.active_source)}</dd>
            <dt>Who holds control</dt><dd data-testid="live-holder">{holder}</dd>
            <dt>Health</dt><dd>{tele?.platform.health ?? '—'}</dd>
          </dl>
          <canvas ref={camera} width={320} height={240} className="live-camera" aria-label="Robot camera" />

          {panel === 'teleop' && (
            <div className="live-panel">
              <Joystick onMove={(dx, dy) => { if (isZero(stick.current)) startDriving(); stick.current = stickVelocity(dx, dy, limits); }}
                onEnd={() => { stick.current = { linear: 0, angular: 0 }; }} />
              <p className="muted">Drag the stick, or hold W A S D / arrows. Space is STOP. Driving during a mission preempts it.</p>
            </div>
          )}
          {panel === 'nav2' && (
            <div className="live-panel">
              <p>Click the map to send a goal. Nav2 plans (blue) and the controller follows its local trajectory (orange).</p>
              {goal && <p data-testid="live-goal">Goal ({goal.x.toFixed(2)}, {goal.y.toFixed(2)}): <b>{goal.status}</b></p>}
            </div>
          )}
          {panel === 'auto' && (
            <div className="live-panel">
              <div className="live-colours">
                {(welcome?.limits.colours ?? []).map((c) => (
                  <button key={c} type="button" className={colour === c ? 'seg-btn active' : 'seg-btn'} data-testid={`live-colour-${c}`}
                    onClick={() => { setColour(c); send({ type: 'select_target', colour: c }); }}>{c}</button>
                ))}
              </div>
              <div className="live-actions">
                <button type="button" className="seg-btn" disabled={!colour || missionActive} data-testid="live-start"
                  onClick={() => send({ type: 'mission', action: 'start' })}>Start</button>
                <button type="button" className="seg-btn" disabled={!missionActive} data-testid="live-abort"
                  onClick={() => send({ type: 'mission', action: 'abort' })}>Abort</button>
              </div>
              <p className="honest" data-testid="live-lane-told">{LANE_TOLD}</p>
              {m && <p data-testid="live-mission">{m.state}{m.step && m.steps ? ` — step ${m.step} of ${m.steps}` : ''}
                {m.words ? `: ${m.words}` : ''}{m.reason ? ` (${m.reason_words ?? m.reason})` : ''}{m.result ? ` — result: ${m.result}` : ''}</p>}
              <ol className="live-timeline" data-testid="live-timeline">
                {timeline.map((s, i) => <li key={`${s.state}-${i}`} className={i === timeline.length - 1 ? 'now' : ''}>{s.state}{s.words ? ` — ${s.words}` : ''}</li>)}
              </ol>
            </div>
          )}
          {note && <p className={note.bad ? 'note bad' : 'note'} role="status">{note.text}</p>}
        </aside>
      </div>
      <button type="button" className="live-stop" onClick={stop} data-testid="live-stop">STOP</button>
    </section>
  );
}

/** A pointer-events joystick: mouse, pen and touch alike. */
function Joystick({ onMove, onEnd }: { onMove(dx: number, dy: number): void; onEnd(): void }) {
  const pad = useRef<HTMLDivElement | null>(null);
  const [knob, setKnob] = useState<[number, number]>([0, 0]);
  const at = (e: React.PointerEvent) => {
    const r = pad.current!.getBoundingClientRect();
    const rad = r.width / 2;
    const dx = (e.clientX - (r.left + rad)) / rad;
    const dy = -(e.clientY - (r.top + rad)) / rad;
    const n = Math.hypot(dx, dy);
    const k = n > 1 ? 1 / n : 1;
    setKnob([dx * k, dy * k]);
    onMove(dx, dy);
  };
  const end = () => { setKnob([0, 0]); onEnd(); };
  return (
    <div ref={pad} className="joystick" data-testid="live-joystick" role="application" aria-label="Drive joystick"
      onPointerDown={(e) => { pad.current!.setPointerCapture(e.pointerId); at(e); }}
      onPointerMove={(e) => { if (e.buttons || e.pointerType === 'touch') at(e); }}
      onPointerUp={end} onPointerCancel={end} onLostPointerCapture={end}>
      <div className="knob" style={{ transform: `translate(${knob[0] * 50}%, ${-knob[1] * 50}%)` }} />
    </div>
  );
}

async function paint(cv: HTMLCanvasElement | null, f: DecodedFrame) {
  if (!cv) return;
  const bmp = await createImageBitmap(new Blob([f.payload], { type: 'image/jpeg' }));
  const ctx = cv.getContext('2d');
  if (!ctx) return;
  if (cv.width !== bmp.width) { cv.width = bmp.width; cv.height = bmp.height; }
  ctx.drawImage(bmp, 0, 0);
  bmp.close();
}
