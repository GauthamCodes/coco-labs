// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The fetch mission's panel (M2.6): where the state machine is and why,
 * the robot's belief over the bays, the error it cannot see beside the one
 * it believes, and the arm in a side-view inset -- two links, two fingers
 * and the magnet, which is what holds. Everything is read from the
 * model's batches (coco.mission.v1, coco.decide.v1, coco.arm.v1,
 * coco.metrics.v1); the page computes no kinematics.
 */

import type { ArenaSession } from '../session';

type Num = ArrayLike<number>;
const S = 600; // px per metre in the inset

function ArmInset({ session, tick }: { session: ArenaSession; tick: number }) {
  const b = session.families.latest('coco.arm.state.v1', tick);
  const head = session.headers.get('coco.mission.fsm.header.v1');
  const params = (head?.params ?? {}) as Record<string, number>;
  const sx = Number(params['arm.shoulder_x'] ?? -0.075); const sz = Number(params['arm.shoulder_z'] ?? 0.1485);
  const tx = Number(params['arm.target_x'] ?? 0.152); const tz = Number(params['arm.target_z'] ?? 0.128);
  const g = (k: string, d = 0) => (b ? (b.columns[k] as Num)[0] : d);
  const ex = sx + g('elbow_x', 0.15); const ez = sz + g('elbow_z', 0);
  const px = sx + g('ee_x', 0.236); const pz = sz + g('ee_z', -0.002);
  const magnet = b ? Boolean((b.columns.magnet_on as ArrayLike<boolean | number>)[0]) : false;
  const holding = b ? Boolean((b.columns.holding as ArrayLike<boolean | number>)[0]) : false;
  const fingers = g('finger_left', 0.02);
  const X = (x: number) => 150 + x * S; const Z = (z: number) => 170 - z * S;
  // the fingers: two short strokes from the pinch, opened by the finger angle
  const f = 0.025;
  return (
    <svg className="arm-inset" data-testid="arm-inset" viewBox="0 0 320 190" role="img"
      aria-label={`arm, side view: ${b ? String((b.columns.phase as string[])[0]) : 'stowed'}; magnet ${magnet ? 'on' : 'off'}${holding ? ', holding the target' : ''}`}>
      <rect className="arm-chassis" x={X(-0.15)} y={Z(0.12)} width={0.3 * S} height={0.09 * S} />
      <line className="arm-ground" x1={0} y1={Z(0)} x2={320} y2={Z(0)} />
      {!holding && <rect className="arm-target" x={X(tx - 0.014)} y={Z(tz + 0.03)} width={0.028 * S} height={0.06 * S} />}
      {holding && <rect className="arm-target" x={X(px - 0.014)} y={Z(pz + 0.03)} width={0.028 * S} height={0.06 * S} />}
      <line className="arm-link" x1={X(sx)} y1={Z(sz)} x2={X(ex)} y2={Z(ez)} />
      <line className="arm-link" x1={X(ex)} y1={Z(ez)} x2={X(px)} y2={Z(pz)} />
      <line className="arm-finger" x1={X(px)} y1={Z(pz)} x2={X(px + f * Math.sin(fingers))} y2={Z(pz - f)} />
      <line className="arm-finger" x1={X(px)} y1={Z(pz)} x2={X(px - f * Math.sin(fingers))} y2={Z(pz - f)} />
      <circle className={magnet ? 'arm-magnet on' : 'arm-magnet'} cx={X(px)} cy={Z(pz)} r={5} />
      <circle className="arm-joint" cx={X(sx)} cy={Z(sz)} r={4} />
      <circle className="arm-joint" cx={X(ex)} cy={Z(ez)} r={3} />
      <text x={6} y={14}>side view · 2 joints · 2 fingers + magnet</text>
      <text x={6} y={184}>{magnet ? (holding ? 'magnet on — the magnet holds the target' : 'magnet on') : 'magnet off'}</text>
    </svg>
  );
}

export function MissionPanel({ session, tick }: { session: ArenaSession; tick: number }) {
  const tr = session.families.latest('coco.mission.fsm.transition.v1', tick);
  const bel = session.families.latest('coco.decide.search.belief.v1', tick);
  const head = session.headers.get('coco.decide.search.header.v1');
  const ids = (head?.region_ids as string[] | undefined) ?? [];
  const params = (head?.params ?? {}) as Record<string, unknown>;
  const err = session.families.series('loc_error', tick).at(-1)?.value;
  const sig = session.families.series('loc_sigma', tick).at(-1)?.value;
  if (!tr) return <p className="lens-empty" data-testid="mission-panel">No mission yet: choose a colour and start a fetch.</p>;
  const last = (k: string) => (tr.columns[k] as string[]).at(-1) ?? '';
  return (
    <div className="mission-panel" data-testid="mission-panel">
      <div className="mission-state" role="status" aria-live="polite">
        <strong data-testid="mission-state">{last('to_state').replace('_', ' ')}</strong>
        {last('result') && <span className="mission-result"> — {last('result')}</span>}
        <span className="mission-why"> {last('reason')}</span>
      </div>
      {bel && (
        <table className="mission-belief" data-testid="mission-belief">
          <caption>P(the target is in the bay) — d = {String(head?.detection)} is an {String(head?.detection_label)}</caption>
          <tbody>
            {Array.from(bel.columns.probability as Num, (p, i) => (
              <tr key={ids[i] ?? i}><th scope="row">{String(params[`${ids[i]}.label`] ?? ids[i])}</th>
                <td><span className="belief-bar" style={{ width: `${Math.round(100 * p)}%` }} /></td><td>{(100 * p).toFixed(1)} %</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <ArmInset session={session} tick={tick} />
      <p className="mission-loc" data-testid="mission-loc">
        where it is: true error {err === undefined ? '—' : `${err.toFixed(2)} m`} (you can see this; it cannot)
        {sig !== undefined && <> · its own uncertainty σ {sig.toFixed(2)} m</>}
      </p>
      <p className="lens-hint">SIMPLIFIED: the Arena is flat, so the ramp climb is not modelled — the robot looks and grasps from the bay's pre-ramp pose.</p>
    </div>
  );
}
