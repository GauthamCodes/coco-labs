// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.3: telemetry, everywhere -- all MODEL values, by the M6F.7 topic names:
 * - TelemetryStrip: /cmd_vel · /odom · sim time, under the speed gauge, always on;
 * - GazeboBar: Sim time · Real time · RTF · Iterations (desktop, SIM view);
 * - RosoutConsole: the model's events as ROS 2 log lines (src/ros/rosout.ts), bottom-left;
 *   one line until tapped.
 */

import { useLayoutEffect, useRef, useState } from 'react';
import { formatLine, type LogLine } from '../../ros/rosout';
import { clockText, stripText, type SimClock, type Strip } from '../../ros/telemetry';

export function TelemetryStrip({ s }: { s: Strip | null }) {
  return <p className="g2-telemetry" data-testid="g2-telemetry" aria-label="Telemetry (model): the command, odometry and sim time">
    {s ? stripText(s) : '/cmd_vel · /odom · sim — waiting for the model'}</p>;
}

export function GazeboBar({ clock, now }: { clock: SimClock; now: number }) {
  const rtf = clock.rtf();
  return <p className="g2-gazebo g1-glass" data-testid="g2-gazebo" aria-label="Simulation clock (model)">
    <span><b>Sim time</b> {clockText(clock.sim)}</span>
    <span><b>Real time</b> {clockText(clock.real(now))}</span>
    <span><b>RTF</b> {rtf === null ? '—' : rtf.toFixed(2)}</span>
    <span title="the model's ticks, 0.1 s of sim time each"><b>Iterations</b> {clock.iterations}</span>
  </p>;
}

const LEVEL_CLASS: Record<string, string> = { INFO: 'i', WARN: 'w', ERROR: 'e', DEBUG: 'd' };

/** Room left of the telemetry strip for the collapsed console, px (null: no strip, use the CSS cap). */
export const roomBeforeStrip = (consoleLeft: number, stripLeft: number | null, gap = 8) =>
  stripLeft === null ? null : Math.max(96, Math.floor(stripLeft - consoleLeft - gap));

export function RosoutConsole({ lines }: { lines: LogLine[] }) {
  const [open, setOpen] = useState(false);
  const last = lines[lines.length - 1];
  // collapsed, it never reaches the telemetry strip beside it: its two lines end where the strip begins
  // (the real phone, 803 x 361: a long WARN ran under the fixed-width strip, G2.8)
  const box = useRef<HTMLElement>(null);
  const [room, setRoom] = useState<number | null>(null);
  useLayoutEffect(() => {
    const el = box.current, strip = document.querySelector<HTMLElement>('[data-testid="g2-telemetry"]');
    if (!el || !strip) return;
    const measure = () => setRoom(roomBeforeStrip(el.getBoundingClientRect().left, strip.getBoundingClientRect().left));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(strip); ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, []);
  return <section ref={box} className={`g2-rosout g1-glass ${open ? 'is-open' : ''}`} data-testid="g2-rosout" aria-label="/rosout (model events)"
    style={!open && room !== null ? { maxWidth: room } : undefined}>
    <button className="head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
      {open ? <span className="title">/rosout · model events · tap to close</span>
        // collapsed: level, node and message only (the stamp and brackets are in the open log), up to two lines
        : last ? <span className={`line ${LEVEL_CLASS[last.level]}`} title={formatLine(last)}>{last.level} {last.node}: {last.msg}</span> : <span className="title">/rosout · no events yet</span>}
    </button>
    {open && <ol className="lines" role="log">{lines.slice(-60).map((l, k) => <li key={`${l.tick}-${k}`} className={LEVEL_CLASS[l.level]}>{formatLine(l)}</li>)}</ol>}
  </section>;
}
