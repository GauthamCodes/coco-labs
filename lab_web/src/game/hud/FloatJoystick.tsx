// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.3: the floating joystick (PUBG-style). It appears where the left thumb
 * lands anywhere in the left half below the top quarter, rests as a ghost at
 * bottom-left, travels 60 px with an 8 % dead zone. Dragging past the ring
 * "nudges" the base along, so the thumb never runs off its stick.
 *
 * It reports (forward, turn) in [-1, 1]; the session scales them to the
 * robot's real limits (it turns in place, never strafes).
 */

import { useEffect, useRef, useState } from 'react';

export const JOY = { size: 130, travel: 60, dead: 0.08 };

export function FloatJoystick({ onChange, enabled, hint }: { onChange: (forward: number, turn: number) => void; enabled: boolean; hint?: string }) {
  const zone = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<{ id: number; bx: number; by: number; kx: number; ky: number } | null>(null);
  const s = useRef(state);
  s.current = state;
  const emit = (dx: number, dy: number) => {
    const m = Math.hypot(dx, dy) / JOY.travel;
    if (m < JOY.dead) { onChange(0, 0); return; }
    const k = Math.min(1, (m - JOY.dead) / (1 - JOY.dead)) / m;
    onChange(Math.max(-1, Math.min(1, (-dy / JOY.travel) * k)), Math.max(-1, Math.min(1, (-dx / JOY.travel) * k)));
  };
  useEffect(() => { if (!enabled && s.current) { setState(null); onChange(0, 0); } }, [enabled]); // eslint-disable-line react-hooks/exhaustive-deps
  const down = (e: React.PointerEvent) => {
    if (!enabled || s.current) return;
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    const r = zone.current!.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    zone.current!.setPointerCapture(e.pointerId);
    setState({ id: e.pointerId, bx: x, by: y, kx: x, ky: y });
    e.preventDefault();
  };
  const move = (e: React.PointerEvent) => {
    const st = s.current;
    if (!st || e.pointerId !== st.id) return;
    const r = zone.current!.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    let bx = st.bx, by = st.by;
    const dx = x - bx, dy = y - by, d = Math.hypot(dx, dy);
    if (d > JOY.travel) { bx += (dx / d) * (d - JOY.travel); by += (dy / d) * (d - JOY.travel); } // nudge the base along
    setState({ ...st, bx, by, kx: x, ky: y });
    emit(x - bx, y - by);
  };
  const up = (e: React.PointerEvent) => {
    const st = s.current;
    if (!st || e.pointerId !== st.id) return;
    setState(null);
    onChange(0, 0);
  };
  return <div ref={zone} className="g1-joyzone" data-testid="joystick-zone" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
    role="application" aria-label="Drive: drag anywhere on the left half">
    {state
      ? <div className="g1-joy is-active" style={{ left: state.bx, top: state.by }}><i style={{ transform: `translate(${state.kx - state.bx}px, ${state.ky - state.by}px)` }} /></div>
      : <div className="g1-joy is-ghost">{hint && <span className="g1-joy-hint">{hint}</span>}<i /></div>}
  </div>;
}
