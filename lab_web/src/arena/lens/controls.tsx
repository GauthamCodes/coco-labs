// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lens controls (M2.3+): each control sends a `config` input to the model
 * (coco_lab.arena: `key=value`), so every setting is in the run's input
 * log -- a shared link replays it, and the per-tick hashes see it. The
 * page never changes a filter itself.
 */

import { useState } from 'react';

export type Send = (choice: string) => void;

export function LocaliseControls({ send, live }: { send: Send; live: boolean }) {
  const [filter, setFilter] = useState('both');
  const [particles, setParticles] = useState(300);
  const [injection, setInjection] = useState('none');
  const [motion, setMotion] = useState(0.02);
  const [sensor, setSensor] = useState(0.02);
  const [slip, setSlip] = useState(false);
  if (!live) return <p className="lens-empty">The Localise lens runs on the live model: click the map to take over.</p>;
  return (
    <div className="lens-controls" data-testid="localise-controls" role="group" aria-label="Localisation settings">
      <label>filter <select value={filter} data-testid="loc-filter"
        onChange={(e) => { setFilter(e.target.value); send(`localise.filter=${e.target.value}`); }}>
        <option value="both">MCL and EKF</option><option value="mcl">MCL</option><option value="ekf">EKF</option><option value="off">off</option>
      </select></label>
      <label>particles <input type="number" min={10} max={2000} step={10} value={particles} data-testid="loc-particles"
        onChange={(e) => setParticles(Number(e.target.value))}
        onBlur={() => send(`localise.mcl.particles=${Math.max(10, Math.min(2000, Math.round(particles)))}`)} /></label>
      <label title="random particles put back in when the measurements fit worse than they used to (augmented MCL)">injection <select value={injection} data-testid="loc-injection"
        onChange={(e) => { setInjection(e.target.value); send(`localise.mcl.injection=${e.target.value}`); }}>
        <option value="none">none (COCO's AMCL)</option><option value="augmented">augmented</option><option value="fixed">fixed 5 %</option>
      </select></label>
      <label title="the odometry motion model's alpha1..alpha4, for the world and for both filters">motion noise
        <input type="range" min={0} max={0.2} step={0.01} value={motion} data-testid="loc-motion"
          onChange={(e) => setMotion(Number(e.target.value))}
          onPointerUp={() => { const a = [motion, motion, motion, motion].join(','); send(`arena.odom_alphas=${a}`); send(`localise.mcl.alphas=${a}`); send(`localise.ekf.alphas=${a}`); }} />
        {motion.toFixed(2)}</label>
      <label title="the LiDAR's Gaussian range noise (m)">sensor noise
        <input type="range" min={0} max={0.1} step={0.005} value={sensor} data-testid="loc-sensor"
          onChange={(e) => setSensor(Number(e.target.value))}
          onPointerUp={() => send(`arena.range_sigma=${sensor}`)} />{sensor.toFixed(3)} m</label>
      <label className="layer-toggle" title="MODEL OPTION: in turns the body rotates 0.775 of what the wheels report (Lab 2 measured COCO's wheel odometry at 72.5 rad of yaw against the truth's 56.2 on the recorded tour). Off by default.">
        <input type="checkbox" checked={slip} data-testid="loc-slip"
          onChange={(e) => { setSlip(e.target.checked); send(`arena.slip=${e.target.checked ? 'on' : 'off'}`); }} />wheel slip (model option)</label>
      <span className="lens-hint">Drag the robot to kidnap it: the filters are not told.</span>
    </div>
  );
}
