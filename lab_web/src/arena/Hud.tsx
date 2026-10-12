// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The head-up display (M4.5; README §5.3, §5.5): who the wheels obey (the
 * arbiter as a game mechanic), the latched STOP, the wheel-speed bars, the
 * evidence badge (MODEL · kinematic), and what the grasp last said. On a
 * touch screen: STOP, E, camera and autonomy buttons, and the optional tank
 * mode (a slider per side). Every value shown is the model's own tick.
 */

import type { Tick } from './protocol';

/** The command source, as the HUD names it. */
export const SOURCE_LABEL: Record<NonNullable<Tick['source']>, string> = {
  idle: 'Idle', stop: 'STOP', teleop: 'You are driving', mission: 'Autonomy · mission', planner: 'Autonomy · planner',
};

/** What the HUD reads of a shown tick (a live Tick or the session's record of one). */
export type HudTick = Pick<Tick, 'source' | 'wheels' | 'grasp'> & { blocked?: boolean };

export interface HudProps {
  tick: HudTick | null;
  latched: boolean;
  /** rad/s that fills a bar: the teleop maximum over the spec's wheel radius */
  fullWheel: number;
  showBars: boolean;
  camera: string;
  coarse: boolean;
  tank: boolean;
  onStop: () => void;
  onContext: () => void;
  onCamera: () => void;
  onAutonomy: () => void;
  onTank: (left: number, right: number) => void;
}

function Bar({ value, full, label }: { value: number; full: number; label: string }) {
  const f = Math.max(-1, Math.min(1, value / Math.max(full, 1e-6)));
  return (
    <div className="hud-bar" role="meter" aria-label={label} aria-valuemin={-full} aria-valuemax={full} aria-valuenow={value}
      title={`${label}: ${value.toFixed(1)} rad/s`}>
      <span style={{ height: `${Math.abs(f) * 50}%`, bottom: f >= 0 ? '50%' : `${50 - Math.abs(f) * 50}%` }}
        className={f >= 0 ? 'fwd' : 'rev'} />
    </div>
  );
}

export function Hud(p: HudProps) {
  const src = p.tick?.source ?? 'idle';
  const w = p.tick?.wheels ?? [0, 0];
  return (
    <div className="hud" data-testid="hud">
      <div className="hud-row">
        <span className={`hud-source src-${src}`} data-testid="hud-source" aria-live="polite">{SOURCE_LABEL[src]}</span>
        <span className="badge model" title="Everything here is computed by the browser model: kinematic, no physics">MODEL · kinematic</span>
        <span className="hud-camera">{p.camera.replace('_', '-')}</span>
      </div>
      {p.latched && <div className="hud-latched" role="status" data-testid="hud-latched">STOP latched · press R to release (hold R to reset home)</div>}
      {p.tick?.grasp?.reason && <div className="hud-note" data-testid="hud-grasp">{p.tick.grasp.reason}</div>}
      {p.tick?.blocked && <div className="hud-note" data-testid="hud-contact">Contact: stopped against a wall, a ledge or a person</div>}
      {p.showBars && (
        <div className="hud-bars" data-testid="hud-bars">
          <Bar value={w[0]} full={p.fullWheel} label="Left wheels" />
          <Bar value={w[1]} full={p.fullWheel} label="Right wheels" />
        </div>
      )}
      {p.coarse && (
        <div className="hud-buttons">
          <button type="button" className="hud-stop" onClick={p.onStop} data-testid="hud-stop-btn">STOP</button>
          <button type="button" onClick={p.onContext} aria-label="Grasp or release">E</button>
          <button type="button" onClick={p.onCamera} aria-label="Next camera">Camera</button>
          <button type="button" onClick={p.onAutonomy} aria-label="Hand back to autonomy">Auto</button>
        </div>
      )}
      {p.coarse && p.tank && <Tank onChange={p.onTank} />}
    </div>
  );
}

/** Tank mode: a slider per side, -1 (back) to 1 (forward); released, each springs to 0. */
function Tank({ onChange }: { onChange: (l: number, r: number) => void }) {
  const val = { l: 0, r: 0 };
  const set = (side: 'l' | 'r', v: number) => { val[side] = v; onChange(val.l, val.r); };
  const slider = (side: 'l' | 'r', label: string) => (
    <input type="range" min={-1} max={1} step={0.05} defaultValue={0} aria-label={label} className="tank-slider"
      onInput={(e) => set(side, Number((e.target as HTMLInputElement).value))}
      onPointerUp={(e) => { (e.target as HTMLInputElement).value = '0'; set(side, 0); }} />
  );
  return <div className="hud-tank" data-testid="hud-tank">{slider('l', 'Left wheels')}{slider('r', 'Right wheels')}</div>;
}
