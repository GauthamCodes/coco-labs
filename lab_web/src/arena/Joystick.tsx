// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** An on-screen joystick for teleop (M1.8): mouse, pen and touch. */

import { useRef, useState } from 'react';

/** dx, dy in [-1, 1]: up is forward, right turns right. Released: (0, 0). */
export function Joystick({ onChange }: { onChange(dx: number, dy: number): void }) {
  const pad = useRef<HTMLDivElement | null>(null);
  const [knob, setKnob] = useState<[number, number]>([0, 0]);
  const at = (e: React.PointerEvent) => {
    const r = pad.current!.getBoundingClientRect();
    const rad = r.width / 2;
    let dx = (e.clientX - (r.left + rad)) / rad;
    let dy = -(e.clientY - (r.top + rad)) / rad;
    const n = Math.hypot(dx, dy);
    if (n > 1) { dx /= n; dy /= n; }
    setKnob([dx, dy]);
    onChange(dx, dy);
  };
  const end = () => { setKnob([0, 0]); onChange(0, 0); };
  return (
    <div ref={pad} className="joystick" data-testid="arena-joystick" role="application" aria-label="Drive COCO (joystick)"
      onPointerDown={(e) => { pad.current!.setPointerCapture(e.pointerId); at(e); }}
      onPointerMove={(e) => { if (e.buttons || e.pointerType === 'touch') at(e); }}
      onPointerUp={end} onPointerCancel={end} onLostPointerCapture={end}>
      <div className="knob" style={{ transform: `translate(${knob[0] * 50}%, ${-knob[1] * 50}%)` }} />
    </div>
  );
}
