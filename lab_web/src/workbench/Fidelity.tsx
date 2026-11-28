// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R6.B1: the fidelity knobs in the experiment builder, and their words on every result. Each knob is off
 * unless set; setting one changes the experiment's spec (its id and every run's chain), and the results name
 * them (coco_lab.experiments.fidelity_config validates; the Arena applies them: docs/v2/r6/R6_STATUS.md).
 */
import type { ExperimentSpec, Fidelity } from './spec';

export const ODOM_PRESETS: { id: string; label: string }[] = [
  { id: 'stack_uncalibrated', label: 'Gazebo, uncalibrated (turns 1.2029x, distance 0.9909x; G2.9, 40 runs)' },
  { id: 'stack_calibrated', label: 'Gazebo, calibrated (turns 0.9986x, distance 0.9913x; G2.9)' },
  { id: 'lab2_fit', label: "Lab 2's slip fit (the body turns 0.775 of the command)" },
];

const LABELS: Record<keyof Fidelity, string> = {
  lidar_dropout: 'LiDAR dropout', range_sigma: 'LiDAR range noise σ', odom_preset: 'odometry',
  cmd_latency: 'command latency', linear_accel: 'linear accel', angular_accel: 'angular accel',
};
const UNITS: Partial<Record<keyof Fidelity, string>> = {
  range_sigma: ' m', cmd_latency: ' ticks', linear_accel: ' m/s²', angular_accel: ' rad/s²',
};

/** Set one knob (undefined clears it); no knob left = no `fidelity` at all (the spec as it was). */
export function setKnob(spec: ExperimentSpec, k: keyof Fidelity, v: number | string | undefined): ExperimentSpec {
  const f: Fidelity = { ...(spec.fidelity ?? {}) };
  if (v === undefined || v === '' || (typeof v === 'number' && !Number.isFinite(v))) delete f[k];
  else (f as Record<string, number | string>)[k] = v;
  const next = { ...spec };
  if (Object.keys(f).length) next.fidelity = f; else delete next.fidelity;
  return next;
}

/** The knobs in words, sorted by key ('' when none): shown on every result. */
export function fidelityText(f: Fidelity | undefined | null): string {
  if (!f) return '';
  return (Object.keys(f) as (keyof Fidelity)[]).sort()
    .map((k) => `${LABELS[k] ?? k} ${f[k]}${UNITS[k] ?? ''}`).join(' · ');
}

const num = (s: string): number | undefined => (s.trim() === '' ? undefined : Number(s));

export function FidelityEditor({ spec, onSpec }: { spec: ExperimentSpec; onSpec: (s: ExperimentSpec) => void }) {
  const f = spec.fidelity ?? {};
  const field = (k: keyof Fidelity, label: string, hint: string, int = false) =>
    <label>{label}<input inputMode={int ? 'numeric' : 'decimal'} placeholder="off" value={f[k] ?? ''} aria-describedby={`fid-${k}`}
      data-testid={`fid-${k}`} onChange={(e) => onSpec(setKnob(spec, k, int ? num(e.target.value) : num(e.target.value)))} />
      <small id={`fid-${k}`}>{hint}</small></label>;
  return <fieldset className="wb-fidelity" data-testid="wb-fidelity">
    <legend>Fidelity (optional; every knob off unless set)</legend>
    <div className="wb-row">
      {field('lidar_dropout', 'LiDAR dropout', 'probability a beam returns no echo, 0 to 0.99')}
      {field('range_sigma', 'LiDAR range noise σ (m)', 'Gaussian, 0 to 1')}
      {field('cmd_latency', 'Command latency (ticks of 0.1 s)', 'the wheels get each command this late, 0 to 50', true)}
    </div>
    <div className="wb-row">
      {field('linear_accel', 'Linear acceleration (m/s²)', "empty = the robot's own limit")}
      {field('angular_accel', 'Angular acceleration (rad/s²)', "empty = the robot's own limit")}
      <label>Odometry<select data-testid="fid-odom_preset" value={f.odom_preset ?? ''} onChange={(e) => onSpec(setKnob(spec, 'odom_preset', e.target.value || undefined))}>
        <option value="">exact (off)</option>
        {ODOM_PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
      </select></label>
    </div>
  </fieldset>;
}
